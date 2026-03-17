from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _load_version() -> str:
    candidate = project_root() / "VERSION.txt"
    if candidate.exists():
        value = candidate.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "0.2.0"


APP_NAME = "Local Assistant"
APP_VERSION = _load_version()
DEVELOPER_URL = "https://t.me/rollpit"
PRODUCT_GITHUB_URL = "https://github.com/Danya-byte/localAssistent"
DEFAULT_PROVIDER_ID = "local_llama"
DEFAULT_MODEL = "qwen2.5-1.5b-instruct-q4-k-m"
DEFAULT_LANGUAGE = "ru"
GITHUB_RELEASE_API_URL = "https://api.github.com/repos/Danya-byte/localAssistent/releases/latest"
RUNTIME_MANIFEST_URL = "https://raw.githubusercontent.com/Danya-byte/localAssistent/main/updates/manifest.json"
RUNTIME_UPDATE_TIMEOUT_SECONDS = 10
RUNTIME_UPDATE_USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_MAX_TOKENS = 128
DEFAULT_LOCAL_RUNTIME_PORT = 8654
DEFAULT_LOCAL_CONTEXT = 8192
LOCAL_RUNTIME_BINARY_NAME = "llama-server.exe"
RUNTIME_MANIFEST_ASSET_NAME = "LocalAssistant-manifest.json"
INSTALLER_ASSET_NAME = "LocalAssistantSetup.exe"
PATCH_BUNDLE_ASSET_NAME = "LocalAssistantPatch.zip"
PATCH_UPDATER_SCRIPT_NAME = "apply_patch_update.ps1"
DEFAULT_SYSTEM_PROMPT = (
    "You are a desktop assistant. Be concise, transparent about limitations, "
    "and never claim an external action succeeded before the system confirms it."
)
DEFAULT_COMMAND_ALLOWLIST = [
    "dir",
    "echo",
    "type",
    "whoami",
    "hostname",
    "ipconfig",
    "tasklist",
]


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()


def resolve_asset(*parts: str) -> Path:
    return project_root().joinpath(*parts)


def bundled_manifest_path() -> Path:
    return resolve_asset("updates", "manifest.json")


def bundled_model_catalog_path() -> Path:
    return resolve_asset("assets", "models", "catalog.json")


@dataclass(slots=True, frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    logs_dir: Path
    exports_dir: Path
    models_dir: Path
    runtime_dir: Path
    cache_dir: Path
    db_path: Path
    secrets_path: Path

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
        models_dir = root / "models"
        runtime_dir = root / "runtime"
        cache_dir = root / "cache"
        db_path = data_dir / "app.sqlite3"
        secrets_path = data_dir / "secrets.json"
        return cls(
            root=root,
            data_dir=data_dir,
            logs_dir=logs_dir,
            exports_dir=exports_dir,
            models_dir=models_dir,
            runtime_dir=runtime_dir,
            cache_dir=cache_dir,
            db_path=db_path,
            secrets_path=secrets_path,
        )

    def ensure(self) -> None:
        for directory in (self.root, self.data_dir, self.logs_dir, self.exports_dir, self.models_dir, self.runtime_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
