from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Local Assistant"
DEFAULT_PROVIDER_ID = "ollama"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_LANGUAGE = "ru"
DEFAULT_SYSTEM_PROMPT = (
    "You are a local desktop assistant. Be concise, transparent about limitations, "
    "and never claim an external action succeeded before the system confirms it."
)
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_COMMAND_ALLOWLIST = [
    "dir",
    "echo",
    "type",
    "whoami",
    "hostname",
    "ipconfig",
    "tasklist",
]


@dataclass(slots=True, frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    logs_dir: Path
    exports_dir: Path
    db_path: Path

    @classmethod
    def resolve(cls) -> "AppPaths":
        custom_root = os.getenv("LOCAL_ASSISTANT_HOME")
        if custom_root:
            root = Path(custom_root).expanduser().resolve()
        else:
            appdata = os.getenv("APPDATA")
            if appdata:
                root = Path(appdata) / "LocalAssistant"
            else:
                root = Path.home() / ".local-assistant"

        data_dir = root / "data"
        logs_dir = root / "logs"
        exports_dir = root / "exports"
        db_path = data_dir / "app.sqlite3"
        return cls(root=root, data_dir=data_dir, logs_dir=logs_dir, exports_dir=exports_dir, db_path=db_path)

    def ensure(self) -> None:
        for directory in (self.root, self.data_dir, self.logs_dir, self.exports_dir):
            directory.mkdir(parents=True, exist_ok=True)
