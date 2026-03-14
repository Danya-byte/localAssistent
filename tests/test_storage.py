from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.models import AppSettings
from local_assistant.storage import Storage


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.sqlite3"
        self.storage = Storage(self.db_path)
        self.storage.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_settings_roundtrip_preserves_provider_language_and_permissions(self) -> None:
        settings = AppSettings(
            provider_id="openai_compatible",
            model="gpt-test",
            system_prompt="Be precise.",
            language="en",
            temperature=0.3,
            top_p=0.8,
            max_tokens=2048,
            last_conversation_id="abc",
            provider_configs={
                "ollama": {"base_url": "http://127.0.0.1:11434"},
                "openai_compatible": {"base_url": "https://api.example.com/v1", "api_key": "secret"},
            },
            web_enabled=True,
            files_enabled=False,
            commands_enabled=False,
            require_confirmation=True,
            command_allowlist=["echo", "dir"],
        )
        self.storage.save_settings(settings)

        loaded = self.storage.load_settings()

        self.assertEqual(loaded.provider_id, settings.provider_id)
        self.assertEqual(loaded.language, settings.language)
        self.assertEqual(loaded.provider_configs["openai_compatible"]["base_url"], "https://api.example.com/v1")
        self.assertFalse(loaded.files_enabled)
        self.assertEqual(loaded.command_allowlist, ["echo", "dir"])

    def test_messages_are_persisted_in_order(self) -> None:
        conversation = self.storage.create_conversation("Testing")
        first = self.storage.add_message(conversation.conversation_id, "user", "hello")
        second = self.storage.add_message(conversation.conversation_id, "assistant", "hi")

        messages = self.storage.list_messages(conversation.conversation_id)

        self.assertEqual([message.message_id for message in messages], [first.message_id, second.message_id])

    def test_action_lifecycle_roundtrip(self) -> None:
        conversation = self.storage.create_conversation("Actions")
        assistant = self.storage.add_message(conversation.conversation_id, "assistant", "Need action", status="completed")
        action = self.storage.create_action(
            conversation_id=conversation.conversation_id,
            assistant_message_id=assistant.message_id,
            kind="command_run",
            title="Run echo",
            description="Echo a value",
            target="echo test",
            risk="high",
            payload={"command": "echo test"},
        )

        updated = self.storage.update_action(action.action_id or "", status="executed", result_text="test", error=None)

        self.assertEqual(updated.status, "executed")
        self.assertEqual(updated.result_text, "test")
        loaded = self.storage.get_action(action.action_id or "")
        assert loaded is not None
        self.assertEqual(loaded.payload["command"], "echo test")


if __name__ == "__main__":
    unittest.main()
