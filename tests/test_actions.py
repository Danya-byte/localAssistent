from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.actions import extract_action_request
from local_assistant.actions.executor import ActionExecutor
from local_assistant.exceptions import ActionError
from local_assistant.models import AppSettings, AssistantAction


class ActionTests(unittest.TestCase):
    @staticmethod
    def _settings(**overrides) -> AppSettings:
        settings = AppSettings(
            provider_id="local_llama",
            model="qwen2.5-0.5b-instruct-q4-0",
            system_prompt="Be safe.",
            command_allowlist=["echo", "python"],
        )
        for key, value in overrides.items():
            setattr(settings, key, value)
        return settings

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

    def test_extract_action_request_returns_plain_text_without_action_block(self) -> None:
        parsed = extract_action_request("plain text", conversation_id="conv-1", assistant_message_id="msg-1")
        self.assertEqual(parsed.visible_text, "plain text")
        self.assertFalse(parsed.had_action_block)
        self.assertIsNone(parsed.action)

    def test_extract_action_request_ignores_invalid_schema(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"file_read","payload":{}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        self.assertIsNone(parsed.action)
        self.assertTrue(parsed.had_action_block)
        self.assertIn("required", parsed.action_parse_error)

    def test_extract_action_request_rejects_missing_kind_invalid_payload_and_invalid_risk(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"title":"No kind","payload":{}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
        self.assertIn("missing `kind`", parsed.action_parse_error)

        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"web_fetch","title":"x","description":"y","target":"https://example.com","payload":"oops"}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
        self.assertIn("must be an object", parsed.action_parse_error)

        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"command_run","title":"x","description":"y","target":"echo hi","risk":"severe","payload":{"command":"echo hi"}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
        self.assertIn("risk must be", parsed.action_parse_error)

    def test_extract_action_request_accepts_web_request_alias(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"web_request","title":"Fetch page","description":"Need source","target":"https://example.com","risk":"low","payload":{"url":"https://example.com"}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        assert parsed.action is not None
        self.assertEqual(parsed.action.kind, "web_fetch")

    def test_extract_action_request_autofixes_url_from_target(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"web_request","title":"Fetch page","description":"Need source","target":"https://example.com","payload":{}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        assert parsed.action is not None
        self.assertEqual(parsed.action.payload["url"], "https://example.com")
        self.assertEqual(parsed.action.risk, "low")
        self.assertTrue(parsed.action_autofixed)

    def test_extract_action_request_applies_default_targets_for_non_web_actions(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"file_read","title":"Read","description":"Read file","payload":{"path":"note.txt"}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
        self.assertEqual(parsed.action.target, "note.txt")  # type: ignore[union-attr]

        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"file_write","title":"Write","description":"Write file","payload":{"path":"note.txt","content":"hello"}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
        self.assertEqual(parsed.action.target, "note.txt")  # type: ignore[union-attr]

        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"command_run","title":"Run","description":"Run command","payload":{"command":"echo hi"}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
        self.assertEqual(parsed.action.target, "echo hi")  # type: ignore[union-attr]

    def test_extract_action_request_rejects_placeholder_target_with_empty_payload(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"web_request","title":"Привет","description":"Кто вы","target":"human-readable target","risk":"low","payload":{}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        self.assertIsNone(parsed.action)
        self.assertTrue(parsed.had_action_block)
        self.assertIn("url", parsed.action_parse_error.lower())

    def test_extract_action_request_rejects_localhost_web_fetch(self) -> None:
        parsed = extract_action_request(
            '<ACTION_REQUEST>{"kind":"web_fetch","title":"Open Telegram","description":"Need to interact with Telegram application","target":"http://127.0.0.1:1313","risk":"low","payload":{"url":"http://127.0.0.1:1313"}}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        self.assertIsNone(parsed.action)
        self.assertTrue(parsed.had_action_block)
        self.assertIn("localhost", parsed.action_parse_error.lower())

    def test_extract_action_request_keeps_visible_text_when_json_is_invalid(self) -> None:
        parsed = extract_action_request(
            'Обычный ответ.\n<ACTION_REQUEST>{"kind":"web_request","title":"Привет","description":"Приветствен!""}</ACTION_REQUEST>',
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )

        self.assertEqual(parsed.visible_text, "Обычный ответ.")
        self.assertIsNone(parsed.action)
        self.assertTrue(parsed.had_action_block)
        self.assertIn("Invalid action JSON", parsed.action_parse_error)

    def test_command_action_rejects_shell_operators(self) -> None:
        executor = ActionExecutor()
        settings = self._settings(command_allowlist=["echo"])
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

    def test_command_action_rejects_ampersand_injection(self) -> None:
        executor = ActionExecutor()
        settings = self._settings(command_allowlist=["echo"])
        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="command_run",
            title="Bad command",
            description="Try chained command",
            target="echo hi & whoami",
            risk="high",
            payload={"command": "echo hi & whoami"},
        )

        with self.assertRaises(ActionError):
            executor.execute(action, settings)

    def test_command_action_rejects_executable_paths(self) -> None:
        executor = ActionExecutor()
        settings = self._settings(command_allowlist=["python"])
        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="command_run",
            title="Bad command",
            description="Absolute executable path",
            target="C:\\Windows\\System32\\cmd.exe /c whoami",
            risk="high",
            payload={"command": "C:\\Windows\\System32\\cmd.exe /c whoami"},
        )

        with self.assertRaises(ActionError):
            executor.execute(action, settings)

    def test_file_write_action_writes_content(self) -> None:
        executor = ActionExecutor()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "note.txt"
            settings = self._settings(command_allowlist=["echo"])
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

    def test_file_read_blocks_sensitive_windows_paths(self) -> None:
        executor = ActionExecutor()
        settings = self._settings(command_allowlist=["echo"])
        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="file_read",
            title="Read system file",
            description="Blocked path",
            target="C:\\Windows\\System32\\drivers\\etc\\hosts",
            risk="high",
            payload={"path": "C:\\Windows\\System32\\drivers\\etc\\hosts"},
        )

        with self.assertRaises(ActionError):
            executor.execute(action, settings)

    def test_execute_requires_confirmation(self) -> None:
        executor = ActionExecutor()
        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="web_fetch",
            title="Fetch",
            description="Fetch",
            target="https://example.com",
            risk="low",
            payload={"url": "https://example.com"},
        )

        with self.assertRaisesRegex(ActionError, "require confirmation"):
            executor.execute(action, self._settings(require_confirmation=False))

    def test_execute_rejects_disabled_capabilities_and_unknown_kind(self) -> None:
        executor = ActionExecutor()
        with self.assertRaisesRegex(ActionError, "Web actions are disabled"):
            executor.execute(
                AssistantAction("a1", "c1", "m1", "web_fetch", "t", "d", "https://example.com", "low", {"url": "https://example.com"}),
                self._settings(web_enabled=False),
            )
        with self.assertRaisesRegex(ActionError, "File actions are disabled"):
            executor.execute(
                AssistantAction("a1", "c1", "m1", "file_read", "t", "d", "note", "medium", {"path": "note.txt"}),
                self._settings(files_enabled=False),
            )
        with self.assertRaisesRegex(ActionError, "Command actions are disabled"):
            executor.execute(
                AssistantAction("a1", "c1", "m1", "command_run", "t", "d", "echo hi", "high", {"command": "echo hi"}),
                self._settings(commands_enabled=False),
            )
        with self.assertRaisesRegex(ActionError, "Unsupported action kind"):
            executor.execute(
                AssistantAction("a1", "c1", "m1", "web_fetchx", "t", "d", "x", "low", {"url": "https://example.com"}),  # type: ignore[arg-type]
                self._settings(),
            )

    def test_fetch_web_success_and_failures(self) -> None:
        executor = ActionExecutor()

        class FakeResponse:
            headers = {"Content-Type": "text/plain"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, _size=None):
                return b"hello world"

        with patch("local_assistant.actions.executor.urlopen", return_value=FakeResponse()):
            result = executor._fetch_web("https://example.com")  # noqa: SLF001
        self.assertIn("Content-Type: text/plain", result)
        self.assertIn("hello world", result)

        request = Mock()
        with patch("local_assistant.actions.executor.urlopen", side_effect=HTTPError("https://example.com", 500, "boom", hdrs=None, fp=None)):
            with self.assertRaisesRegex(ActionError, "HTTP 500"):
                executor._fetch_web("https://example.com")  # noqa: SLF001
        with patch("local_assistant.actions.executor.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(ActionError, "offline"):
                executor._fetch_web("https://example.com")  # noqa: SLF001
        _ = request

    def test_read_file_missing_and_write_outside_workspace(self) -> None:
        executor = ActionExecutor()
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.txt"
            with self.assertRaisesRegex(ActionError, "File not found"):
                executor._read_file(str(missing))  # noqa: SLF001
        with self.assertRaisesRegex(ActionError, "outside the permitted workspace scope"):
            executor._write_file("Z:\\outside\\file.txt", "data")  # noqa: SLF001

    def test_run_command_parse_allowlist_failure_nonzero_and_empty_output(self) -> None:
        executor = ActionExecutor()
        with self.assertRaisesRegex(ActionError, "could not be parsed"):
            executor._run_command('"', ["echo"])  # noqa: SLF001
        with self.assertRaisesRegex(ActionError, "Command is empty"):
            executor._run_command("", ["echo"])  # noqa: SLF001
        with self.assertRaisesRegex(ActionError, "not in the allowlist"):
            executor._run_command("whoami", ["echo"])  # noqa: SLF001

        failed = Mock(returncode=1, stdout="oops", stderr="bad")
        with patch("local_assistant.actions.executor.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(ActionError, "exit code 1"):
                executor._run_command("echo hi", ["echo"])  # noqa: SLF001

        succeeded = Mock(returncode=0, stdout="", stderr="")
        with patch("local_assistant.actions.executor.subprocess.run", return_value=succeeded):
            result = executor._run_command("echo hi", ["echo"])  # noqa: SLF001
        self.assertIn("no output", result)

    def test_path_helpers_cover_allowed_roots_and_relative_checks(self) -> None:
        roots = ActionExecutor._allowed_roots()  # noqa: SLF001
        self.assertGreaterEqual(len(roots), 2)
        self.assertTrue(ActionExecutor._is_relative_to(Path.cwd(), Path.cwd()))  # noqa: SLF001
        self.assertFalse(ActionExecutor._is_relative_to(Path("C:/tmp"), Path("D:/tmp")))  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
