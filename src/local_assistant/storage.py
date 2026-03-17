from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .config import (
    DEFAULT_COMMAND_ALLOWLIST,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER_ID,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
)
from .exceptions import StorageError
from .models import AppSettings, AssistantAction, ConversationSummary, InstalledLocalModel, MessageRecord


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc
        finally:
            if connection is not None:
                connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_override TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at
                    ON messages(conversation_id, created_at);

                CREATE TABLE IF NOT EXISTS actions (
                    action_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    assistant_message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    target TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_text TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conversation_columns = {row[1] for row in connection.execute("PRAGMA table_info(conversations)").fetchall()}
            if "source_override" not in conversation_columns:
                connection.execute("ALTER TABLE conversations ADD COLUMN source_override TEXT")
            message_columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)").fetchall()}
            if "metadata_json" not in message_columns:
                connection.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")

    def load_settings(self) -> AppSettings:
        defaults = AppSettings(
            provider_id=DEFAULT_PROVIDER_ID,
            model=DEFAULT_MODEL,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            default_source="local",
            api_model="",
            reasoning_enabled=False,
            language=DEFAULT_LANGUAGE,
            provider_configs={"local_llama": {}},
            command_allowlist=list(DEFAULT_COMMAND_ALLOWLIST),
        )

        with self.connect() as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()

        settings_map = {row["key"]: json.loads(row["value"]) for row in rows}
        provider_configs = settings_map.get("provider_configs", defaults.provider_configs)
        provider_configs = {
            provider_id: dict(value)
            for provider_id, value in provider_configs.items()
            if provider_id == "local_llama"
        }
        provider_configs.setdefault("local_llama", {})

        stored_provider_id = str(settings_map.get("provider_id", "")).strip()
        legacy_model = str(settings_map.get("model", "")).strip()
        if legacy_model in {"qwen2.5:7b", "qwen2.5:7b-instruct", "hf.co/Qwen/Qwen3-4B-GGUF:Q4_K_M", "hf.co/Qwen/Qwen3-8B-GGUF:Q4_K_M"}:
            legacy_model = ""
        generation_settings = self._normalize_generation_settings(settings_map)

        selected_model = str(settings_map.get("model", defaults.model)).strip() or defaults.model
        if stored_provider_id == "openai_compatible" and selected_model and not self.get_installed_model(selected_model):
            selected_model = defaults.model

        return AppSettings(
            provider_id="local_llama",
            model=selected_model,
            system_prompt=settings_map.get("system_prompt", defaults.system_prompt),
            default_source="local",
            api_model="",
            reasoning_enabled=False,
            language=settings_map.get("language", defaults.language),
            theme=settings_map.get("theme", defaults.theme),
            temperature=generation_settings["temperature"],
            top_p=generation_settings["top_p"],
            max_tokens=generation_settings["max_tokens"],
            last_conversation_id=settings_map.get("last_conversation_id", defaults.last_conversation_id),
            provider_configs=provider_configs,
            web_enabled=bool(settings_map.get("web_enabled", defaults.web_enabled)),
            files_enabled=bool(settings_map.get("files_enabled", defaults.files_enabled)),
            commands_enabled=bool(settings_map.get("commands_enabled", defaults.commands_enabled)),
            require_confirmation=bool(settings_map.get("require_confirmation", defaults.require_confirmation)),
            command_allowlist=list(settings_map.get("command_allowlist", defaults.command_allowlist)),
        )

    def save_settings(self, settings: AppSettings) -> None:
        generation_settings = self._normalize_generation_settings(
            {
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "max_tokens": settings.max_tokens,
            }
        )
        provider_configs = {"local_llama": dict(settings.provider_configs.get("local_llama", {}))}
        payload = {
            "provider_id": "local_llama",
            "model": settings.model,
            "system_prompt": settings.system_prompt,
            "default_source": "local",
            "api_model": "",
            "reasoning_enabled": False,
            "language": settings.language,
            "theme": settings.theme,
            "temperature": generation_settings["temperature"],
            "top_p": generation_settings["top_p"],
            "max_tokens": generation_settings["max_tokens"],
            "last_conversation_id": settings.last_conversation_id,
            "provider_configs": provider_configs,
            "web_enabled": settings.web_enabled,
            "files_enabled": settings.files_enabled,
            "commands_enabled": settings.commands_enabled,
            "require_confirmation": settings.require_confirmation,
            "command_allowlist": settings.command_allowlist,
        }
        with self.connect() as connection:
            for key, value in payload.items():
                connection.execute(
                    """
                    INSERT INTO settings(key, value)
                    VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, json.dumps(value)),
                )

    def get_runtime_setting(self, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT value
                FROM settings
                WHERE key = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return default

    def set_runtime_setting(self, key: str, value: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, json.dumps(value)),
            )

    def delete_runtime_setting(self, key: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM settings
                WHERE key = ?
                """,
                (key,),
            )

    def load_release_state(self) -> dict[str, Any]:
        return {
            "latest_version": str(self.get_runtime_setting("runtime.release.latest_version", "") or ""),
            "release_url": str(self.get_runtime_setting("runtime.release.url", "") or ""),
            "installer_url": str(self.get_runtime_setting("runtime.release.installer_url", "") or ""),
            "patch_url": str(self.get_runtime_setting("runtime.release.patch_url", "") or ""),
            "manifest_url": str(self.get_runtime_setting("runtime.release.manifest_url", "") or ""),
            "installer_available": bool(self.get_runtime_setting("runtime.release.installer_available", False)),
            "patch_available": bool(self.get_runtime_setting("runtime.release.patch_available", False)),
            "update_kind": str(self.get_runtime_setting("runtime.release.update_kind", "installer") or "installer"),
            "last_check_status": str(self.get_runtime_setting("runtime.release.status", "idle") or "idle"),
            "last_check_error": str(self.get_runtime_setting("runtime.release.error", "") or ""),
            "last_checked_at": str(self.get_runtime_setting("runtime.release.checked_at", "") or ""),
            "update_available": bool(self.get_runtime_setting("runtime.release.update_available", False)),
            "repair_required": bool(self.get_runtime_setting("runtime.release.repair_required", False)),
            "repair_reason": str(self.get_runtime_setting("runtime.release.repair_reason", "") or ""),
        }

    def save_release_state(self, state: dict[str, Any]) -> None:
        mapping = {
            "runtime.release.latest_version": state.get("latest_version", ""),
            "runtime.release.url": state.get("release_url", ""),
            "runtime.release.installer_url": state.get("installer_url", ""),
            "runtime.release.patch_url": state.get("patch_url", ""),
            "runtime.release.manifest_url": state.get("manifest_url", ""),
            "runtime.release.installer_available": bool(state.get("installer_available", False)),
            "runtime.release.patch_available": bool(state.get("patch_available", False)),
            "runtime.release.update_kind": state.get("update_kind", "installer"),
            "runtime.release.status": state.get("last_check_status", "idle"),
            "runtime.release.error": state.get("last_check_error", ""),
            "runtime.release.checked_at": state.get("last_checked_at", ""),
            "runtime.release.update_available": bool(state.get("update_available", False)),
            "runtime.release.repair_required": bool(state.get("repair_required", False)),
            "runtime.release.repair_reason": state.get("repair_reason", ""),
        }
        for key, value in mapping.items():
            self.set_runtime_setting(key, value)

    def list_installed_models(self) -> list[InstalledLocalModel]:
        payload = self.get_runtime_setting("runtime.local_models", [])
        if not isinstance(payload, list):
            return []
        models: list[InstalledLocalModel] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("model_id", "")).strip()
            file_path = str(item.get("file_path", "")).strip()
            if not model_id or not file_path:
                continue
            models.append(
                InstalledLocalModel(
                    model_id=model_id,
                    file_path=file_path,
                    file_name=str(item.get("file_name", "")).strip(),
                    source=str(item.get("source", "")).strip(),
                    downloaded_at=str(item.get("downloaded_at", "")).strip(),
                    size_bytes=int(item.get("size_bytes", 0) or 0),
                )
            )
        return models

    def get_installed_model(self, model_id: str) -> InstalledLocalModel | None:
        for item in self.list_installed_models():
            if item.model_id == model_id:
                return item
        return None

    def save_installed_model(self, installed_model: InstalledLocalModel) -> None:
        models = [item for item in self.list_installed_models() if item.model_id != installed_model.model_id]
        models.append(installed_model)
        payload = [
            {
                "model_id": item.model_id,
                "file_path": item.file_path,
                "file_name": item.file_name,
                "source": item.source,
                "downloaded_at": item.downloaded_at,
                "size_bytes": item.size_bytes,
            }
            for item in models
        ]
        self.set_runtime_setting("runtime.local_models", payload)

    def remove_installed_model(self, model_id: str) -> InstalledLocalModel | None:
        removed = None
        remaining: list[InstalledLocalModel] = []
        for item in self.list_installed_models():
            if item.model_id == model_id:
                removed = item
            else:
                remaining.append(item)
        self.set_runtime_setting(
            "runtime.local_models",
            [
                {
                    "model_id": item.model_id,
                    "file_path": item.file_path,
                    "file_name": item.file_name,
                    "source": item.source,
                    "downloaded_at": item.downloaded_at,
                    "size_bytes": item.size_bytes,
                }
                for item in remaining
            ],
        )
        return removed

    @staticmethod
    def _normalize_generation_settings(settings_map: dict[str, Any]) -> dict[str, float | int]:
        _ = settings_map
        return {
            "temperature": DEFAULT_TEMPERATURE,
            "top_p": DEFAULT_TOP_P,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

    def list_conversations(self) -> list[ConversationSummary]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT conversation_id, title, source_override, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._row_to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> ConversationSummary | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT conversation_id, title, source_override, created_at, updated_at
                FROM conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return self._row_to_conversation(row) if row else None

    def create_conversation(self, title: str) -> ConversationSummary:
        conversation_id = str(uuid.uuid4())
        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations(conversation_id, title, source_override, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (conversation_id, title, None, timestamp, timestamp),
            )
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise StorageError("Conversation was not created.")
        return conversation

    def update_conversation_source(self, conversation_id: str, source_override: str | None) -> ConversationSummary:
        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE conversations
                SET source_override = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (source_override, timestamp, conversation_id),
            )
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise StorageError(f"Conversation {conversation_id} not found.")
        return conversation

    def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT message_id, conversation_id, role, content, status, error, metadata_json, created_at, updated_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def get_message(self, message_id: str) -> MessageRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT message_id, conversation_id, role, content, status, error, metadata_json, created_at, updated_at
                FROM messages
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        return self._row_to_message(row) if row else None

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        status: str = "completed",
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        message_id = str(uuid.uuid4())
        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(message_id, conversation_id, role, content, status, error, metadata_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, conversation_id, role, content, status, error, json.dumps(metadata or {}, ensure_ascii=False), timestamp, timestamp),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (timestamp, conversation_id),
            )
        message = self.get_message(message_id)
        if message is None:
            raise StorageError("Message was not created.")
        return message

    def update_message(
        self,
        message_id: str,
        *,
        content: str | None = None,
        status: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        existing = self.get_message(message_id)
        if existing is None:
            raise StorageError(f"Message {message_id} not found.")

        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = ?, status = ?, error = ?, metadata_json = ?, updated_at = ?
                WHERE message_id = ?
                """,
                (
                    content if content is not None else existing.content,
                    status if status is not None else existing.status,
                    error if error is not None else existing.error,
                    json.dumps(metadata if metadata is not None else existing.metadata, ensure_ascii=False),
                    timestamp,
                    message_id,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (timestamp, existing.conversation_id),
            )

    def delete_message(self, message_id: str) -> None:
        existing = self.get_message(message_id)
        if existing is None:
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (utcnow(), existing.conversation_id),
            )

    def create_action(
        self,
        conversation_id: str,
        assistant_message_id: str,
        kind: str,
        title: str,
        description: str,
        target: str,
        risk: str,
        payload: dict[str, Any],
    ) -> AssistantAction:
        action_id = str(uuid.uuid4())
        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO actions(
                    action_id, conversation_id, assistant_message_id, kind, title, description, target,
                    risk, payload_json, status, result_text, error, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    conversation_id,
                    assistant_message_id,
                    kind,
                    title,
                    description,
                    target,
                    risk,
                    json.dumps(payload),
                    "pending",
                    "",
                    None,
                    timestamp,
                    timestamp,
                ),
            )
        action = self.get_action(action_id)
        if action is None:
            raise StorageError("Action was not created.")
        return action

    def get_action(self, action_id: str) -> AssistantAction | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT action_id, conversation_id, assistant_message_id, kind, title, description, target,
                       risk, payload_json, status, result_text, error, created_at, updated_at
                FROM actions
                WHERE action_id = ?
                """,
                (action_id,),
            ).fetchone()
        return self._row_to_action(row) if row else None

    def update_action(
        self,
        action_id: str,
        *,
        status: str | None = None,
        result_text: str | None = None,
        error: str | None = None,
    ) -> AssistantAction:
        action = self.get_action(action_id)
        if action is None:
            raise StorageError(f"Action {action_id} not found.")
        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE actions
                SET status = ?, result_text = ?, error = ?, updated_at = ?
                WHERE action_id = ?
                """,
                (
                    status if status is not None else action.status,
                    result_text if result_text is not None else action.result_text,
                    error if error is not None else action.error,
                    timestamp,
                    action_id,
                ),
            )
        updated = self.get_action(action_id)
        if updated is None:
            raise StorageError(f"Action {action_id} was not updated.")
        return updated

    def _row_to_conversation(self, row: sqlite3.Row) -> ConversationSummary:
        return ConversationSummary(
            conversation_id=row["conversation_id"],
            title=row["title"],
            source_override=row["source_override"],
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> MessageRecord:
        return MessageRecord(
            message_id=row["message_id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            status=row["status"],
            error=row["error"],
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )

    def _row_to_action(self, row: sqlite3.Row) -> AssistantAction:
        return AssistantAction(
            action_id=row["action_id"],
            conversation_id=row["conversation_id"],
            assistant_message_id=row["assistant_message_id"],
            kind=row["kind"],
            title=row["title"],
            description=row["description"],
            target=row["target"],
            risk=row["risk"],
            payload=json.loads(row["payload_json"]),
            status=row["status"],
            result_text=row["result_text"],
            error=row["error"],
        )
