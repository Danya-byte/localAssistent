from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Event

from .config import AppPaths


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class BootstrapResult:
    status: str
    message: str = ""

    @property
    def exit_code(self) -> int:
        return {
            "success": 0,
            "skipped": 10,
            "failed": 1,
        }.get(self.status, 1)


def bootstrap_recommended_model(service) -> BootstrapResult:
    progress_messages: list[str] = []

    def _progress_callback(progress) -> None:
        progress_messages.append(f"{progress.stage}:{progress.downloaded_bytes}/{progress.total_bytes}")
        LOGGER.info("Recommended model bootstrap progress: %s - %s", progress.stage, progress.message)

    try:
        installed = service.install_recommended_local_model(Event(), _progress_callback)
    except Exception as exc:  # noqa: BLE001
        if "No recommended local model" in str(exc):
            LOGGER.warning("Recommended model bootstrap skipped: %s", exc)
            return BootstrapResult(status="skipped", message=str(exc))
        LOGGER.exception("Recommended model bootstrap failed")
        return BootstrapResult(status="failed", message=str(exc))
    LOGGER.info("Recommended model bootstrap finished: %s", installed.model_id)
    return BootstrapResult(status="success", message=installed.model_id)


def build_service_for_paths(paths: AppPaths):
    from .actions.executor import ActionExecutor
    from .providers import ProviderRegistry
    from .services import ChatService, LocalRuntimeService, ModelCatalogService, ModelDownloadService, UpdateService
    from .storage import Storage

    storage = Storage(paths.db_path)
    catalog_service = ModelCatalogService()
    runtime_service = LocalRuntimeService(paths)
    download_service = ModelDownloadService(paths.models_dir)
    providers = ProviderRegistry(runtime_service=runtime_service, storage=storage, catalog_service=catalog_service)
    update_service = UpdateService(cache_dir=paths.cache_dir)
    service = ChatService(
        storage=storage,
        providers=providers,
        update_service=update_service,
        catalog_service=catalog_service,
        runtime_service=runtime_service,
        download_service=download_service,
    )
    return service, ActionExecutor()
