from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ChatService",
    "LocalRuntimeService",
    "ModelCatalogService",
    "ModelDownloadService",
    "RuntimeRefreshResult",
    "RuntimeStatus",
    "UpdateService",
]


def __getattr__(name: str) -> Any:
    if name == "ChatService":
        return import_module(".chat_service", __name__).ChatService
    if name == "LocalRuntimeService":
        return import_module(".local_runtime_service", __name__).LocalRuntimeService
    if name == "ModelCatalogService":
        return import_module(".model_catalog_service", __name__).ModelCatalogService
    if name == "ModelDownloadService":
        return import_module(".model_download_service", __name__).ModelDownloadService
    if name in {"RuntimeRefreshResult", "RuntimeStatus", "UpdateService"}:
        module = import_module(".update_service", __name__)
        return getattr(module, name)
    raise AttributeError(name)
