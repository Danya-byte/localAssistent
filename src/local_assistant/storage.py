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
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_PROVIDER_ID,
    DEFAULT_SYSTEM_PROMPT,
)
from .exceptions import StorageError
from .models import AppSettings, AssistantAction, ConversationSummary, MessageRecord


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

    def load_settings(self) -> AppSettings:
        defaults = AppSettings(
            provider_id=DEFAULT_PROVIDER_ID,
            model=DEFAULT_MODEL,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            language=DEFAULT_LANGUAGE,
            provider_configs={
                "ollama": {"base_url": DEFAULT_OLLAMA_BASE_URL},
                "openai_compatible": {"base_url": "", "api_key": ""},
            },
            command_allowlist=list(DEFAULT_COMMAND_ALLOWLIST),
        )

        with self.connect() as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()

        settings_map = {row["key"]: json.loads(row["value"]) for row in rows}
        provider_configs = settings_map.get("provider_configs", defaults.provider_configs)
        if "ollama" not in provider_configs:
            provider_configs["ollama"] = {"base_url": DEFAULT_OLLAMA_BASE_URL}
        if "openai_compatible" not in provider_configs:
            provider_configs["openai_compatible"] = {"base_url": "", "api_key": ""}

        return AppSettings(
            provider_id=settings_map.get("provider_id", defaults.provider_id),
            model=settings_map.get("model", defaults.model),
            system_prompt=settings_map.get("system_prompt", defaults.system_prompt),
            language=settings_map.get("language", defaults.language),
            temperature=float(settings_map.get("temperature", defaults.temperature)),
            top_p=float(settings_map.get("top_p", defaults.top_p)),
            max_tokens=int(settings_map.get("max_tokens", defaults.max_tokens)),
            last_conversation_id=settings_map.get("last_conversation_id", defaults.last_conversation_id),
            provider_configs=provider_configs,
            web_enabled=bool(settings_map.get("web_enabled", defaults.web_enabled)),
            files_enabled=bool(settings_map.get("files_enabled", defaults.files_enabled)),
            commands_enabled=bool(settings_map.get("commands_enabled", defaults.commands_enabled)),
            require_confirmation=bool(settings_map.get("require_confirmation", defaults.require_confirmation)),
            command_allowlist=list(settings_map.get("command_allowlist", defaults.command_allowlist)),
        )

    def save_settings(self, settings: AppSettings) -> None:
        payload = {
            "provider_id": settings.provider_id,
            "model": settings.model,
            "system_prompt": settings.system_prompt,
            "language": settings.language,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
            "last_conversation_id": settings.last_conversation_id,
            "provider_configs": settings.provider_configs,
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

    def list_conversations(self) -> list[ConversationSummary]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT conversation_id, title, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._row_to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> ConversationSummary | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT conversation_id, title, created_at, updated_at
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
                INSERT INTO conversations(conversation_id, title, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                """,
                (conversation_id, title, timestamp, timestamp),
            )
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise StorageError("Conversation was not created.")
        return conversation

    def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT message_id, conversation_id, role, content, status, error, created_at, updated_at
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
                SELECT message_id, conversation_id, role, content, status, error, created_at, updated_at
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
    ) -> MessageRecord:
        message_id = str(uuid.uuid4())
        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(message_id, conversation_id, role, content, status, error, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, conversation_id, role, content, status, error, timestamp, timestamp),
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
    ) -> None:
        existing = self.get_message(message_id)
        if existing is None:
            raise StorageError(f"Message {message_id} not found.")

        timestamp = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = ?, status = ?, error = ?, updated_at = ?
                WHERE message_id = ?
                """,
                (
                    content if content is not None else existing.content,
                    status if status is not None else existing.status,
                    error if error is not None else existing.error,
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
