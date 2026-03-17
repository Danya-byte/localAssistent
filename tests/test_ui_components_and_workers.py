from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDateTime, QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QWidget

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.actions.executor import ActionExecutor
from local_assistant.models import AppSettings, AssistantAction, GenerationRequest, ModelDownloadProgress
from local_assistant.ui.components.conversation_list_delegate import (
    CONVERSATION_TIMESTAMP_ROLE,
    CONVERSATION_TITLE_ROLE,
    ConversationListDelegate,
)
from local_assistant.ui.components.sheet_dialog import SheetDialog
from local_assistant.ui.workers import ActionWorker, GenerationWorker, InstallerWorker, ModelDownloadWorker, RuntimeRefreshWorker


def get_app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class UiComponentsAndWorkersTests(unittest.TestCase):
    def test_sheet_dialog_layout_flags_and_show_event(self) -> None:
        app = get_app()
        parent = QWidget()
        parent.setGeometry(100, 120, 800, 600)
        dialog = SheetDialog(
            parent,
            title="Danger zone",
            body="Delete file?",
            details="line1\nline2",
            confirm_text="Delete",
            cancel_text="Cancel",
            danger=True,
        )
        self.assertEqual(dialog.title_label.text(), "Danger zone")
        self.assertEqual(dialog.body_label.text(), "Delete file?")
        self.assertEqual(dialog.confirm_button.text(), "Delete")
        self.assertTrue(bool(dialog.confirm_button.property("danger")))
        self.assertTrue(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)

        dialog.show()
        app.processEvents()
        self.assertTrue(dialog.details_view.isVisible())
        self.assertTrue(dialog.cancel_button.isVisible())
        expected_x = parent.frameGeometry().x() + (parent.frameGeometry().width() - dialog.width()) // 2
        expected_y = parent.frameGeometry().y() + parent.frameGeometry().height() - dialog.height() - 28
        self.assertEqual(dialog.pos(), QPoint(expected_x, expected_y))
        dialog.close()
        parent.close()

        dialog = SheetDialog(title="Info", body="Body", details="", confirm_text="OK")
        self.assertFalse(dialog.details_view.isVisible())
        self.assertFalse(dialog.cancel_button.isVisible())
        dialog.close()

    def test_conversation_list_delegate_size_paint_and_elide(self) -> None:
        app = get_app()
        _ = app
        delegate = ConversationListDelegate(lambda value: "12:30" if value else "")
        model = QStandardItemModel()
        item = QStandardItem("Fallback title")
        item.setData("Conversation title", CONVERSATION_TITLE_ROLE)
        item.setData(QDateTime.currentDateTime(), CONVERSATION_TIMESTAMP_ROLE)
        model.appendRow(item)
        index = model.index(0, 0)

        image = QImage(220, 60, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 220, 60)
        option.palette = QApplication.palette()
        option.state = QStyle.StateFlag.State_None
        option.widget = None
        size = delegate.sizeHint(option, index)
        self.assertEqual(size.height(), 44)
        delegate.paint(painter, option, index)
        painter.end()
        tiny_image = QImage(10, 10, QImage.Format.Format_ARGB32)
        tiny_image.fill(0)
        tiny_painter = QPainter(tiny_image)
        self.assertEqual(delegate._elide(tiny_painter, "hello", 0), "")  # noqa: SLF001
        tiny_painter.end()
        self.assertTrue(delegate._title_color(QApplication.palette(), QStyle.StateFlag.State_None).isValid())  # noqa: SLF001
        self.assertTrue(delegate._meta_color(QApplication.palette(), QStyle.StateFlag.State_None).isValid())  # noqa: SLF001

        blank_item = QStandardItem("")
        model.appendRow(blank_item)
        blank_index = model.index(1, 0)
        image = QImage(220, 60, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        delegate.paint(painter, option, blank_index)
        painter.end()

    def test_generation_worker_action_worker_and_refresh_worker_cover_success_and_failure(self) -> None:
        received: list[str] = []
        metadata: list[object] = []
        failures: list[tuple[str, bool]] = []
        finished: list[str] = []

        provider = Mock()
        provider.stream_chat.return_value = iter(["a", "b"])
        provider.pop_response_metadata.return_value = {"ok": True}
        request = GenerationRequest(
            conversation_id="c1",
            assistant_message_id="m1",
            provider_id="local_llama",
            provider_config={},
            model="demo",
            messages=[],
            reasoning_enabled=False,
            temperature=0.1,
            top_p=0.9,
            max_tokens=1,
        )
        worker = GenerationWorker(provider, request)
        worker.chunk_received.connect(received.append)
        worker.metadata_received.connect(metadata.append)
        worker.failed.connect(lambda message, cancelled: failures.append((message, cancelled)))
        worker.finished.connect(lambda: finished.append("done"))
        worker.run()
        self.assertEqual(received, ["a", "b"])
        self.assertEqual(metadata, [{"ok": True}])
        self.assertEqual(failures, [])
        self.assertEqual(finished, ["done"])

        provider = Mock()

        def cancelling_stream(_request, cancel_event):
            cancel_event.set()
            yield "chunk"

        provider.stream_chat.side_effect = cancelling_stream
        provider.pop_response_metadata.return_value = {}
        worker = GenerationWorker(provider, request)
        failures = []
        worker.failed.connect(lambda message, cancelled: failures.append((message, cancelled)))
        worker.run()
        self.assertEqual(failures, [("Generation cancelled by user.", True)])

        provider = Mock()
        provider.stream_chat.side_effect = RuntimeError("boom")
        worker = GenerationWorker(provider, request)
        failures = []
        worker.failed.connect(lambda message, cancelled: failures.append((message, cancelled)))
        worker.run()
        self.assertEqual(failures, [("boom", False)])

        executor = Mock(spec=ActionExecutor)
        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="command_run",
            title="Run",
            description="Run command",
            target="echo hi",
            risk="high",
            payload={"command": "echo hi"},
        )
        settings = AppSettings(provider_id="local_llama", model="demo", system_prompt="safe")
        action_worker = ActionWorker(executor, action, settings)
        completed: list[str] = []
        failed_messages: list[str] = []
        action_worker.completed.connect(completed.append)
        action_worker.failed.connect(failed_messages.append)
        executor.execute.return_value = "ok"
        action_worker.run()
        self.assertEqual(completed, ["ok"])
        executor.execute.side_effect = RuntimeError("nope")
        action_worker.run()
        self.assertIn("nope", failed_messages[-1])

        service = Mock()
        refresh_worker = RuntimeRefreshWorker(service)
        refresh_completed: list[object] = []
        refresh_failed: list[str] = []
        refresh_worker.completed.connect(refresh_completed.append)
        refresh_worker.failed.connect(refresh_failed.append)
        service.refresh_runtime_configuration.return_value = {"ready": True}
        refresh_worker.run()
        self.assertEqual(refresh_completed, [{"ready": True}])
        service.refresh_runtime_configuration.side_effect = RuntimeError("broken")
        refresh_worker.run()
        self.assertEqual(refresh_failed[-1], "broken")

    def test_model_download_worker_and_installer_worker_cover_paths(self) -> None:
        service = Mock()
        worker = ModelDownloadWorker(service, "demo")
        completed: list[object] = []
        progress_events: list[ModelDownloadProgress] = []
        failures: list[str] = []
        worker.completed.connect(completed.append)
        worker.progress.connect(progress_events.append)
        worker.failed.connect(failures.append)

        def install(model_id, cancel_event, callback):
            callback(
                ModelDownloadProgress(
                    model_id=model_id,
                    display_name="Demo",
                    stage="downloading",
                    downloaded_bytes=1,
                    total_bytes=2,
                    message="downloading",
                )
            )
            return {"model_id": model_id, "cancelled": cancel_event.is_set()}

        service.install_local_model.side_effect = install
        worker.run()
        self.assertEqual(progress_events[0].model_id, "demo")
        self.assertEqual(completed[0]["model_id"], "demo")
        worker.cancel()
        self.assertTrue(worker.cancel_event.is_set())
        service.install_local_model.side_effect = RuntimeError("download failed")
        worker.run()
        self.assertEqual(failures[-1], "download failed")

        installer_service = Mock()
        installer_worker = InstallerWorker(installer_service, prefer_latest=True, mode="installer")
        installer_done: list[object] = []
        installer_failed: list[str] = []
        installer_worker.completed.connect(installer_done.append)
        installer_worker.failed.connect(installer_failed.append)
        installer_service.prepare_installer_handoff.return_value = {"kind": "installer"}
        installer_worker.run()
        installer_service.prepare_installer_handoff.assert_called_with(prefer_latest=True)
        self.assertEqual(installer_done[-1]["kind"], "installer")

        patch_worker = InstallerWorker(installer_service, mode="patch")
        installer_service.prepare_patch_handoff.return_value = {"kind": "patch"}
        patch_worker.completed.connect(installer_done.append)
        patch_worker.run()
        self.assertEqual(installer_done[-1]["kind"], "patch")

        installer_service.prepare_patch_handoff.side_effect = RuntimeError("patch failed")
        patch_worker.failed.connect(installer_failed.append)
        patch_worker.run()
        self.assertEqual(installer_failed[-1], "patch failed")
