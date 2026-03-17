from __future__ import annotations

import logging
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from ..actions.executor import ActionExecutor
from ..models import AppSettings, AssistantAction, GenerationRequest, ModelDownloadProgress
from ..providers.base import ModelProvider


LOGGER = logging.getLogger(__name__)


class GenerationWorker(QObject):
    chunk_received = Signal(str)
    metadata_received = Signal(object)
    completed = Signal()
    failed = Signal(str, bool)
    finished = Signal()

    def __init__(self, provider: ModelProvider, request: GenerationRequest) -> None:
        super().__init__()
        self.provider = provider
        self.request = request
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            for chunk in self.provider.stream_chat(self.request, self.cancel_event):
                if self.cancel_event.is_set():
                    self.failed.emit("Generation cancelled by user.", True)
                    return
                self.chunk_received.emit(chunk)
            if self.cancel_event.is_set():
                self.failed.emit("Generation cancelled by user.", True)
            else:
                self.metadata_received.emit(self.provider.pop_response_metadata(self.request.assistant_message_id))
                self.completed.emit()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Generation worker failed")
            self.failed.emit(str(exc), False)
        finally:
            self.finished.emit()


class ActionWorker(QObject):
    completed = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, executor: ActionExecutor, action: AssistantAction, settings: AppSettings) -> None:
        super().__init__()
        self.executor = executor
        self.action = action
        self.settings = settings

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self.executor.execute(self.action, self.settings))
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Action worker failed")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class RuntimeRefreshWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, service) -> None:
        super().__init__()
        self.service = service

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self.service.refresh_runtime_configuration())
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Runtime refresh worker failed")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ModelDownloadWorker(QObject):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, service, model_id: str) -> None:
        super().__init__()
        self.service = service
        self.model_id = model_id
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self.service.install_local_model(self.model_id, self.cancel_event, self._emit_progress))
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Model download worker failed")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def _emit_progress(self, progress: ModelDownloadProgress) -> None:
        self.progress.emit(progress)


class InstallerWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, service, *, prefer_latest: bool = False, mode: str = "installer") -> None:
        super().__init__()
        self.service = service
        self.prefer_latest = prefer_latest
        self.mode = mode

    @Slot()
    def run(self) -> None:
        try:
            if self.mode == "patch":
                self.completed.emit(self.service.prepare_patch_handoff())
            else:
                self.completed.emit(self.service.prepare_installer_handoff(prefer_latest=self.prefer_latest))
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Installer worker failed")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()
