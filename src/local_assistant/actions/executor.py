from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import ActionError
from ..models import AppSettings, AssistantAction


class ActionExecutor:
    DISALLOWED_COMMAND_TOKENS = ("&&", "||", "|", ";", ">", "<", "&", "\n", "\r", "^", "%", "!")

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
        path = self._resolve_permitted_path(raw_path, require_parent=False)
        if not path.exists():
            raise ActionError(f"File not found: {path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def _write_file(self, raw_path: str, content: str) -> str:
        path = self._resolve_permitted_path(raw_path, require_parent=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}"

    def _run_command(self, command: str, allowlist: list[str]) -> str:
        if any(token in command for token in self.DISALLOWED_COMMAND_TOKENS):
            raise ActionError("Command contains disallowed shell operators.")

        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            raise ActionError("Command could not be parsed.") from exc
        if not parts:
            raise ActionError("Command is empty.")

        executable = parts[0].strip().strip("\"")
        if "\\" in executable or "/" in executable or ":" in executable:
            raise ActionError("Commands must use an allowlisted executable name only.")
        normalized_executable = executable.lower()
        normalized_allowlist = {item.lower().strip() for item in allowlist if item.strip()}
        if normalized_executable not in normalized_allowlist:
            raise ActionError(f"Command `{normalized_executable}` is not in the allowlist.")

        completed = subprocess.run(
            [executable, *parts[1:]],
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            raise ActionError(f"Command failed with exit code {completed.returncode}.\n{output.strip()}")
        return output.strip() or "Command completed with no output."

    def _resolve_permitted_path(self, raw_path: str, *, require_parent: bool) -> Path:
        path = Path(raw_path).expanduser()
        resolved = path.resolve(strict=False)
        if not self._is_allowed_path(resolved, require_parent=require_parent):
            raise ActionError(f"Path is outside the permitted workspace scope: {resolved}")
        return resolved

    def _is_allowed_path(self, path: Path, *, require_parent: bool) -> bool:
        candidate = path.parent if require_parent else path
        if self._is_sensitive_path(candidate):
            return False
        return any(self._is_relative_to(candidate, root) for root in self._allowed_roots())

    @staticmethod
    def _allowed_roots() -> tuple[Path, ...]:
        roots = [Path.cwd().resolve(), Path.home().resolve(), Path(tempfile.gettempdir()).resolve()]
        unique: list[Path] = []
        for root in roots:
            if root not in unique:
                unique.append(root)
        return tuple(unique)

    @staticmethod
    def _is_sensitive_path(path: Path) -> bool:
        sensitive_roots: list[Path] = []
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        for value in (system_root, program_files, program_files_x86, program_data):
            if value:
                sensitive_roots.append(Path(value).resolve())
        return any(ActionExecutor._is_relative_to(path, root) for root in sensitive_roots)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
