from __future__ import annotations

import logging
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from ..actions.executor import ActionExecutor
from ..models import AppSettings, AssistantAction, GenerationRequest
from ..providers.base import ModelProvider


LOGGER = logging.getLogger(__name__)


class GenerationWorker(QObject):
    chunk_received = Signal(str)
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
