from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.actions import extract_action_request
from local_assistant.actions.executor import ActionExecutor
from local_assistant.exceptions import ActionError
from local_assistant.models import AppSettings, AssistantAction


class ActionTests(unittest.TestCase):
    def test_extract_action_request_parses_valid_block(self) -> None:
        parsed = extract_action_request(
            """
Check the page.
<ACTION_REQUEST>
{"kind":"web_fetch","title":"Fetch page","description":"Need source","target":"https://example.com","risk":"low","payload":{"url":"https://example.com"}}
</ACTION_REQUEST>
            """.strip(),
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        self.assertEqual(parsed.visible_text, "Check the page.")
        assert parsed.action is not None
        self.assertEqual(parsed.action.payload["url"], "https://example.com")

    def test_extract_action_request_rejects_missing_required_field(self) -> None:
        with self.assertRaises(ActionError):
            extract_action_request(
                '<ACTION_REQUEST>{"kind":"file_read","payload":{}}</ACTION_REQUEST>',
                conversation_id="conv-1",
                assistant_message_id="msg-1",
            )

    def test_command_action_rejects_shell_operators(self) -> None:
        executor = ActionExecutor()
        settings = AppSettings(
            provider_id="ollama",
            model="demo-model",
            system_prompt="Be safe.",
            command_allowlist=["echo"],
        )
        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="command_run",
            title="Bad command",
            description="Try chained command",
            target="echo hi && whoami",
            risk="high",
            payload={"command": "echo hi && whoami"},
        )

        with self.assertRaises(ActionError):
            executor.execute(action, settings)

    def test_file_write_action_writes_content(self) -> None:
        executor = ActionExecutor()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "note.txt"
            settings = AppSettings(
                provider_id="ollama",
                model="demo-model",
                system_prompt="Be safe.",
                command_allowlist=["echo"],
            )
            action = AssistantAction(
                action_id="a1",
                conversation_id="c1",
                assistant_message_id="m1",
                kind="file_write",
                title="Write file",
                description="Save note",
                target=str(target),
                risk="high",
                payload={"path": str(target), "content": "hello"},
            )

            result = executor.execute(action, settings)

            self.assertIn("Wrote 5 characters", result)
            self.assertEqual(target.read_text(encoding="utf-8"), "hello")


if __name__ == "__main__":
    unittest.main()
