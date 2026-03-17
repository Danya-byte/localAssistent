from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.exceptions import StorageError
from local_assistant.models import AppSettings, InstalledLocalModel
from local_assistant.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE, DEFAULT_TOP_P
from local_assistant.storage import Storage, parse_datetime, utcnow


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.sqlite3"
        self.storage = Storage(self.db_path)
        self.storage.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_settings_roundtrip_preserves_local_preferences(self) -> None:
        settings = AppSettings(
            provider_id="local_llama",
            model="qwen2.5-0.5b-instruct-q4-0",
            system_prompt="Be precise.",
            language="en",
            theme="dark",
            temperature=0.3,
            top_p=0.8,
            max_tokens=2048,
            last_conversation_id="abc",
            provider_configs={"local_llama": {"context_length": "8192"}},
            web_enabled=True,
            files_enabled=False,
            commands_enabled=False,
            require_confirmation=True,
            command_allowlist=["echo", "dir"],
        )
        self.storage.save_settings(settings)

        loaded = self.storage.load_settings()

        self.assertEqual(loaded.provider_id, "local_llama")
        self.assertEqual(loaded.default_source, "local")
        self.assertEqual(loaded.api_model, "")
        self.assertFalse(loaded.reasoning_enabled)
        self.assertEqual(loaded.language, settings.language)
        self.assertEqual(loaded.theme, settings.theme)
        self.assertEqual(loaded.provider_configs["local_llama"]["context_length"], "8192")
        self.assertFalse(loaded.files_enabled)
        self.assertEqual(loaded.command_allowlist, ["echo", "dir"])
        self.assertEqual(loaded.temperature, DEFAULT_TEMPERATURE)
        self.assertEqual(loaded.top_p, DEFAULT_TOP_P)
        self.assertEqual(loaded.max_tokens, DEFAULT_MAX_TOKENS)

    def test_legacy_api_provider_is_migrated_to_local_defaults(self) -> None:
        with self.storage.connect() as connection:
            for key, value in {
                "provider_id": "openai_compatible",
                "model": "gpt-4o-mini",
                "system_prompt": "Be precise.",
                "provider_configs": {"openai_compatible": {"base_url": "https://openrouter.ai/api/v1", "api_key": "secret"}},
            }.items():
                connection.execute(
                    """
                    INSERT INTO settings(key, value)
                    VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, json.dumps(value)),
                )

        loaded = self.storage.load_settings()

        self.assertEqual(loaded.provider_id, "local_llama")
        self.assertEqual(loaded.default_source, "local")
        self.assertEqual(loaded.api_model, "")
        self.assertEqual(loaded.model, DEFAULT_MODEL)
        self.assertEqual(list(loaded.provider_configs.keys()), ["local_llama"])

    def test_runtime_helper_settings_are_stored_outside_app_settings(self) -> None:
        self.storage.set_runtime_setting("runtime.release.status", "ok")
        self.storage.save_release_state(
            {
                "latest_version": "0.2.0",
                "release_url": "https://example.com/release",
                "installer_url": "https://example.com/LocalAssistantSetup.exe",
                "installer_available": True,
                "last_check_status": "update_available",
                "last_check_error": "",
                "last_checked_at": "2026-03-16T10:00:00+00:00",
                "update_available": True,
                "repair_required": True,
                "repair_reason": "Bundled local runtime is incomplete or damaged.",
            }
        )

        loaded = self.storage.load_settings()
        release_state = self.storage.load_release_state()

        self.assertEqual(loaded.api_model, "")
        self.assertEqual(release_state["latest_version"], "0.2.0")
        self.assertTrue(release_state["update_available"])
        self.assertTrue(release_state["installer_available"])
        self.assertTrue(release_state["repair_required"])

    def test_runtime_settings_models_and_release_state_helpers(self) -> None:
        self.assertEqual(self.storage.get_runtime_setting("missing", "fallback"), "fallback")
        with self.storage.connect() as connection:
            connection.execute("INSERT INTO settings(key, value) VALUES(?, ?)", ("broken_json", "{oops"))
        self.assertEqual(self.storage.get_runtime_setting("broken_json", "fallback"), "fallback")
        self.storage.delete_runtime_setting("broken_json")
        self.assertEqual(self.storage.get_runtime_setting("broken_json", "gone"), "gone")

        model = InstalledLocalModel(
            model_id="demo",
            file_path="C:/models/demo.gguf",
            file_name="demo.gguf",
            source="hf",
            downloaded_at=utcnow(),
            size_bytes=123,
        )
        self.storage.save_installed_model(model)
        self.assertEqual(self.storage.get_installed_model("demo").file_name, "demo.gguf")  # type: ignore[union-attr]
        self.storage.set_runtime_setting("runtime.local_models", ["bad", {"model_id": "", "file_path": ""}])
        self.assertEqual(self.storage.list_installed_models(), [])
        self.storage.save_installed_model(model)
        removed = self.storage.remove_installed_model("demo")
        self.assertEqual(removed.model_id, "demo")  # type: ignore[union-attr]
        self.assertIsNone(self.storage.remove_installed_model("missing"))

        self.storage.save_release_state({})
        release_state = self.storage.load_release_state()
        self.assertEqual(release_state["update_kind"], "installer")
        self.assertFalse(release_state["installer_available"])

    def test_conversations_messages_and_actions_roundtrip(self) -> None:
        conversation = self.storage.create_conversation("New chat")
        self.assertEqual(self.storage.get_conversation(conversation.conversation_id).title, "New chat")  # type: ignore[union-attr]
        updated_conversation = self.storage.update_conversation_source(conversation.conversation_id, "local")
        self.assertEqual(updated_conversation.source_override, "local")
        self.assertEqual(self.storage.list_conversations()[0].conversation_id, conversation.conversation_id)
        with self.assertRaisesRegex(StorageError, "not found"):
            self.storage.update_conversation_source("missing", "local")

        message = self.storage.add_message(
            conversation.conversation_id,
            "assistant",
            "hello",
            status="streaming",
            metadata={"step": 1},
        )
        listed = self.storage.list_messages(conversation.conversation_id)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].metadata["step"], 1)
        self.storage.update_message(message.message_id, content="updated", status="completed", error="oops", metadata={"step": 2})
        updated = self.storage.get_message(message.message_id)
        self.assertEqual(updated.content, "updated")  # type: ignore[union-attr]
        self.assertEqual(updated.metadata["step"], 2)  # type: ignore[union-attr]
        with self.assertRaisesRegex(StorageError, "not found"):
            self.storage.update_message("missing", content="nope")
        self.storage.delete_message(message.message_id)
        self.assertIsNone(self.storage.get_message(message.message_id))
        self.storage.delete_message("missing")

        message = self.storage.add_message(conversation.conversation_id, "assistant", "for action")
        action = self.storage.create_action(
            conversation.conversation_id,
            message.message_id,
            "command_run",
            "Run",
            "Run command",
            "echo hi",
            "high",
            {"command": "echo hi"},
        )
        loaded_action = self.storage.get_action(action.action_id)
        self.assertEqual(loaded_action.payload["command"], "echo hi")  # type: ignore[union-attr]
        updated_action = self.storage.update_action(action.action_id, status="approved", result_text="done", error="warn")
        self.assertEqual(updated_action.status, "approved")
        self.assertEqual(updated_action.result_text, "done")
        self.assertEqual(updated_action.error, "warn")
        with self.assertRaisesRegex(StorageError, "not found"):
            self.storage.update_action("missing", status="failed")

    def test_storage_primitives_and_error_wrapping(self) -> None:
        now = utcnow()
        self.assertIsNotNone(parse_datetime(now))
        self.assertIn("T", now)

        bad_storage = Storage(Path(self.temp_dir.name) / "bad.sqlite3")
        original_connect = sqlite3.connect

        def boom(*args, **kwargs):
            raise sqlite3.Error("db failed")

        try:
            sqlite3.connect = boom  # type: ignore[assignment]
            with self.assertRaisesRegex(StorageError, "db failed"):
                with bad_storage.connect():
                    pass
        finally:
            sqlite3.connect = original_connect  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
