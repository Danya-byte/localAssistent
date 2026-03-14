from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import ActionError
from ..models import AppSettings, AssistantAction


class ActionExecutor:
    def execute(self, action: AssistantAction, settings: AppSettings) -> str:
        if settings.require_confirmation is False:
            raise ActionError("Actions must require confirmation in this build.")

        if action.kind == "web_fetch":
            if not settings.web_enabled:
                raise ActionError("Web actions are disabled.")
            return self._fetch_web(action.payload["url"])

        if action.kind == "file_read":
            if not settings.files_enabled:
                raise ActionError("File actions are disabled.")
            return self._read_file(action.payload["path"])

        if action.kind == "file_write":
            if not settings.files_enabled:
                raise ActionError("File actions are disabled.")
            return self._write_file(action.payload["path"], action.payload["content"])

        if action.kind == "command_run":
            if not settings.commands_enabled:
                raise ActionError("Command actions are disabled.")
            return self._run_command(action.payload["command"], settings.command_allowlist)

        raise ActionError(f"Unsupported action kind: {action.kind}")

    def _fetch_web(self, url: str) -> str:
        request = Request(url=url, headers={"User-Agent": "LocalAssistant/0.2"})
        try:
            with urlopen(request, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "")
                content = response.read(12000).decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise ActionError(f"Web request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise ActionError(f"Web request failed: {exc.reason}") from exc
        return f"Content-Type: {content_type}\n\n{content.strip()}"

    def _read_file(self, raw_path: str) -> str:
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise ActionError(f"File not found: {path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def _write_file(self, raw_path: str, content: str) -> str:
        path = Path(raw_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}"

    def _run_command(self, command: str, allowlist: list[str]) -> str:
        disallowed_tokens = ["&&", "||", "|", ";", ">", "<", "\n", "\r"]
        if any(token in command for token in disallowed_tokens):
            raise ActionError("Command contains disallowed shell operators.")

        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            raise ActionError("Command could not be parsed.") from exc
        if not parts:
            raise ActionError("Command is empty.")

        executable = parts[0].strip().strip("\"").lower()
        normalized_allowlist = {item.lower().strip() for item in allowlist if item.strip()}
        if executable not in normalized_allowlist:
            raise ActionError(f"Command `{executable}` is not in the allowlist.")

        completed = subprocess.run(
            ["cmd", "/c", command],
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            raise ActionError(f"Command failed with exit code {completed.returncode}.\n{output.strip()}")
        return output.strip() or "Command completed with no output."
