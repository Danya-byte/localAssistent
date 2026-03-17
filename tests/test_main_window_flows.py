from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QComboBox, QListWidgetItem, QMessageBox

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.actions.executor import ActionExecutor
from local_assistant.config import AppPaths
from local_assistant.i18n import LocalizationManager
from local_assistant.exceptions import ProviderError
from local_assistant.models import (
    AssistantAction,
    ChatMessage,
    ConversationSummary,
    GenerationRequest,
    InstalledLocalModel,
    LocalModelDescriptor,
    MessageRecord,
    ModelDownloadProgress,
    ModelDescriptor,
    ProviderDescriptor,
    ProviderHealth,
)
from local_assistant.services import ChatService, RuntimeRefreshResult, RuntimeStatus
from local_assistant.services.chat_service import PreparedGeneration
from local_assistant.services.update_service import ReleaseCheck, RuntimeManifest, UpdateService
from local_assistant.storage import Storage
from local_assistant.ui.main_window import MainWindow


class FakeProvider:
    descriptor = ProviderDescriptor(
        provider_id="local_llama",
        display_name="Local Qwen",
        description_key="provider_local_desc",
    )

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        return ProviderHealth(status="ready", detail="ready", models=[ModelDescriptor(model_id=desired_model or "demo", display_name=desired_model or "demo")])

    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        return [ModelDescriptor(model_id="demo-model", display_name="demo-model")]

    def stream_chat(self, request: GenerationRequest, cancel_event):
        _ = request
        _ = cancel_event
        yield "chunk"

    def pop_response_metadata(self, assistant_message_id: str) -> dict[str, str]:
        _ = assistant_message_id
        return {}


class FakeRegistry:
    def __init__(self) -> None:
        self.providers = {"local_llama": FakeProvider()}

    def list_descriptors(self) -> list[ProviderDescriptor]:
        return [provider.descriptor for provider in self.providers.values()]

    def get(self, provider_id: str) -> FakeProvider:
        provider = self.providers.get(provider_id)
        if provider is None:
            raise KeyError(provider_id)
        return provider


class FakeUpdateService(UpdateService):
    def __init__(self) -> None:
        super().__init__(manifest_path=Path("unused.json"))
        self.remote_manifest = RuntimeManifest(source="remote")
        self.release_check = ReleaseCheck(current_version="0.2.0")

    def load_bundled_manifest(self) -> RuntimeManifest:
        return RuntimeManifest(source="bundled")

    def fetch_runtime_manifest(self) -> RuntimeManifest:
        return self.remote_manifest

    def check_latest_release(self) -> ReleaseCheck:
        return self.release_check


def get_app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def make_paths(root: Path) -> AppPaths:
    return AppPaths(
        root=root,
        data_dir=root / "data",
        logs_dir=root / "logs",
        exports_dir=root / "exports",
        models_dir=root / "models",
        runtime_dir=root / "runtime",
        cache_dir=root / "cache",
        db_path=root / "data" / "app.sqlite3",
        secrets_path=root / "data" / "secrets.json",
    )


class MainWindowFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = get_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.paths = make_paths(root)
        self.paths.ensure()
        self.service = ChatService(storage=Storage(self.paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
        self.window = MainWindow(service=self.service, executor=ActionExecutor(), paths=self.paths)
        self.window._background_refresh_timer.stop()  # noqa: SLF001
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()
        self.temp_dir.cleanup()

    @staticmethod
    def _prepared(conversation_id: str = "c1", message_id: str = "m1") -> PreparedGeneration:
        now = datetime.now().astimezone()
        return PreparedGeneration(
            conversation=ConversationSummary(
                conversation_id=conversation_id,
                title="Chat",
                created_at=now,
                updated_at=now,
            ),
            assistant_message=MessageRecord(
                message_id=message_id,
                conversation_id=conversation_id,
                role="assistant",
                content="",
                status="pending",
                created_at=now,
                updated_at=now,
            ),
            request=GenerationRequest(
                conversation_id=conversation_id,
                assistant_message_id=message_id,
                provider_id="local_llama",
                provider_config={},
                model="demo-model",
                messages=[ChatMessage(role="user", content="hi")],
                reasoning_enabled=False,
                temperature=0.7,
                top_p=0.9,
                max_tokens=128,
            ),
        )

    def test_model_download_handlers_and_local_model_status(self) -> None:
        descriptor = LocalModelDescriptor(
            model_id="demo-model",
            display_name="Demo",
            description="Desc",
            source="hf",
            download_url="https://example.com/demo.gguf",
            file_name="demo.gguf",
            size_hint="1 MB",
            quantization="Q4",
            recommended_ram_gb=8,
            context_length=4096,
        )
        installed = InstalledLocalModel(
            model_id="demo-model",
            file_path="C:/models/demo.gguf",
            file_name="demo.gguf",
            source="hf",
            downloaded_at="2026-03-17T00:00:00+00:00",
            size_bytes=10,
        )
        self.window._cached_local_models = [descriptor]  # noqa: SLF001
        self.window._cached_installed_models = {}  # noqa: SLF001
        self.window.local_model_combo.clear()
        self.window.local_model_combo.addItem("Demo", "demo-model")
        self.window.model_combo.addItem("Demo", "demo-model")
        self.window.local_model_combo.setCurrentIndex(0)

        with patch.object(self.window, "_show_event") as show_event:
            self.window._handle_model_download_progress(  # noqa: SLF001
                ModelDownloadProgress(
                    model_id="demo-model",
                    display_name="Demo",
                    stage="downloading",
                    total_bytes=100,
                    downloaded_bytes=25,
                    message="Downloading",
                )
            )
        self.assertEqual(show_event.call_args.kwargs["progress"], 25)
        self.window._handle_model_download_progress(object())  # noqa: SLF001

        self.window.service.list_installed_local_models = lambda: [installed]  # type: ignore[method-assign]
        self.window.service.load_settings = lambda: self.window.settings  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_populate_models"),
            patch.object(self.window, "_populate_local_models"),
            patch.object(self.window, "_refresh_health_banner"),
            patch.object(self.window, "_start_runtime_refresh") as start_runtime_refresh,
        ):
            self.window._handle_model_download_completed(SimpleNamespace(model_id="demo-model"))  # noqa: SLF001
        self.assertEqual(self.window.settings.model, "demo-model")
        start_runtime_refresh.assert_called_once_with(manual=False, notify_runtime=True)

        with patch.object(self.window, "_finish_event") as finish_event:
            self.window._handle_model_download_failed("bad download")  # noqa: SLF001
        self.assertIn("bad download", finish_event.call_args.kwargs["message"])

        self.window._runtime_binary_available = True  # noqa: SLF001
        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        self.window._cached_installed_models = {"demo-model": installed}  # noqa: SLF001
        self.window.settings.model = "demo-model"
        self.window._refresh_local_model_status()  # noqa: SLF001
        self.assertIn("desc", self.window.local_model_status_value.text().lower())

    def test_conversation_selection_send_and_regenerate_flows(self) -> None:
        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        self.window.current_conversation_id = "c-existing"
        with (
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_update_interaction_state"),
        ):
            self.window._handle_conversation_selection(None, None)  # noqa: SLF001
        self.assertIsNone(self.window.current_conversation_id)

        item = QListWidgetItem("Chat title\nmeta")
        item.setData(Qt.ItemDataRole.UserRole, "c1")
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_update_interaction_state"),
        ):
            self.window._handle_conversation_selection(item, None)  # noqa: SLF001
        self.assertEqual(self.window.current_conversation_id, "c1")

        with patch.object(self.window, "_show_warning") as show_warning:
            self.window.generation_worker = object()  # type: ignore[assignment]
            self.window._start_new_chat()  # noqa: SLF001
        show_warning.assert_called_once()
        self.window.generation_worker = None

        with patch.object(self.window, "_show_warning") as show_warning:
            self.window.action_worker = object()  # type: ignore[assignment]
            self.window._send_message()  # noqa: SLF001
        show_warning.assert_called_once()
        self.window.action_worker = None

        self.window.current_health = ProviderHealth(status="missing_model", detail="missing")
        with patch.object(self.window, "_notify") as notify:
            self.window._send_message()  # noqa: SLF001
        notify.assert_called_once()

        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        self.window.composer.setPlainText("hello")
        prepared = self._prepared()
        self.window.service.prepare_user_generation = lambda *_args, **_kwargs: prepared  # type: ignore[method-assign]
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_populate_conversations"),
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_start_generation") as start_generation,
        ):
            self.window._send_message()  # noqa: SLF001
        self.assertEqual(self.window.current_conversation_id, "c1")
        start_generation.assert_called_once()

        self.window.current_conversation_id = None
        with patch.object(self.window, "_show_warning") as show_warning:
            self.window._regenerate_last()  # noqa: SLF001
        show_warning.assert_called_once()

        self.window.current_conversation_id = "c1"
        self.window.service.regenerate_last_response = lambda _cid: None  # type: ignore[method-assign]
        with patch.object(self.window, "_show_warning") as show_warning:
            self.window._regenerate_last()  # noqa: SLF001
        show_warning.assert_called_once()

        self.window.service.regenerate_last_response = lambda _cid: prepared  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_start_generation") as start_generation,
        ):
            self.window._regenerate_last()  # noqa: SLF001
        start_generation.assert_called_once()

    def test_action_runtime_and_update_flows(self) -> None:
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
        self.window._show_approval_page(action)  # noqa: SLF001
        self.assertEqual(self.window.pending_action_id, "a1")
        self.assertIn("echo hi", self.window.approval_payload_view.toPlainText())

        self.window.service.get_action = lambda _aid: action  # type: ignore[method-assign]
        self.window.service.mark_action_approved = lambda _aid: action  # type: ignore[method-assign]
        with patch.object(self.window, "_start_action_execution") as start_action:
            self.window._allow_pending_action()  # noqa: SLF001
        start_action.assert_called_once()

        self.window.pending_action_id = "a1"
        self.window.service.mark_action_denied = lambda _aid: action  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_notify"),
            patch.object(self.window, "_continue_after_action") as continue_after,
        ):
            self.window._deny_pending_action()  # noqa: SLF001
        continue_after.assert_called_once()

        self.window.pending_action_id = "a1"
        self.window.service.mark_action_executed = lambda _aid, _text: action  # type: ignore[method-assign]
        with patch.object(self.window, "_continue_after_action") as continue_after:
            self.window._handle_action_completed("done")  # noqa: SLF001
        continue_after.assert_called_once()

        self.window.pending_action_id = "a1"
        self.window.service.mark_action_failed = lambda _aid, _err: action  # type: ignore[method-assign]
        with patch.object(self.window, "_continue_after_action") as continue_after:
            self.window._handle_action_failed("boom")  # noqa: SLF001
        continue_after.assert_called_once()

        prepared = self._prepared("c2", "m2")
        self.window.pending_action_id = "a1"
        self.window.service.build_action_follow_up = lambda _action: prepared  # type: ignore[method-assign]
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_populate_conversations"),
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_start_generation") as start_generation,
        ):
            self.window._continue_after_action(action)  # noqa: SLF001
        self.assertIsNone(self.window.pending_action_id)
        start_generation.assert_called_once()

        status = RuntimeStatus(current_version="0.2.0", latest_version="0.2.1", release_url="https://example.com", last_check_status="update_available")
        result = RuntimeRefreshResult(
            status=status,
            update_available=True,
            local_status="ready",
            local_detail="",
            runtime_ready=True,
            provider_health=ProviderHealth(status="ready", detail="ok", models=[ModelDescriptor(model_id="demo-model", display_name="Demo")]),
            provider_models=[ModelDescriptor(model_id="demo-model", display_name="Demo")],
            local_models=[],
            installed_local_models=[],
            runtime_binary_available=True,
        )
        with (
            patch.object(self.window, "_populate_models"),
            patch.object(self.window, "_populate_local_models"),
            patch.object(self.window, "_refresh_local_model_status"),
            patch.object(self.window, "_apply_health"),
            patch.object(self.window, "_refresh_update_section"),
            patch.object(self.window, "_notify") as notify,
            patch.object(self.window, "_finish_event") as finish_event,
            patch.object(self.window, "_maybe_prompt_installer_handoff") as maybe_prompt,
        ):
            self.window._handle_runtime_refresh_completed(result)  # noqa: SLF001
        notify.assert_called_once()
        finish_event.assert_called_once()
        maybe_prompt.assert_called_once()

        with (
            patch.object(self.window, "_refresh_update_section"),
            patch.object(self.window, "_finish_event") as finish_event,
        ):
            self.window._handle_runtime_refresh_failed("offline")  # noqa: SLF001
        self.assertEqual(self.window.runtime_status.last_check_status, "error")
        finish_event.assert_called_once()

        self.window.runtime_status = RuntimeStatus(current_version="0.2.0", repair_required=True, repair_reason="Need repair")
        self.assertIn("Need repair", self.window._runtime_status_text())  # noqa: SLF001
        self.assertIn("checksum", self.window._normalize_update_error("checksum mismatch"))  # noqa: SLF001

    def test_installer_export_and_misc_handlers(self) -> None:
        with patch("local_assistant.ui.main_window.QDesktopServices.openUrl") as open_url:
            self.window.runtime_status.release_url = ""
            self.window._open_release_page()  # noqa: SLF001
            self.window.runtime_status.release_url = "https://example.com/release"
            self.window._open_release_page()  # noqa: SLF001
        open_url.assert_called_once()

        with (
            patch("local_assistant.ui.main_window.QMenu") as menu_cls,
            patch("local_assistant.ui.main_window.QDesktopServices.openUrl") as open_url,
        ):
            menu = menu_cls.return_value
            developer_action = object()
            github_action = object()
            menu.addAction.side_effect = [developer_action, github_action]
            menu.exec.return_value = github_action
            self.window._open_support_menu()  # noqa: SLF001
        open_url.assert_called_once()

        with patch.object(self.window, "_start_patch_handoff") as start_patch:
            patch_result = RuntimeRefreshResult(
                status=RuntimeStatus(current_version="0.2.0", latest_version="0.2.1"),
                update_available=True,
                update_kind="patch",
                patch_available=True,
            )
            self.window._installer_prompt_token = None  # noqa: SLF001
            self.window._maybe_prompt_installer_handoff(patch_result)  # noqa: SLF001
        start_patch.assert_called_once()

        with patch("local_assistant.ui.main_window.SheetDialog") as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.DialogCode.Accepted = 1
            dialog.exec.return_value = 1
            with patch.object(self.window, "_start_installer_handoff") as start_installer:
                repair_result = RuntimeRefreshResult(
                    status=RuntimeStatus(current_version="0.2.0"),
                    repair_required=True,
                    repair_reason="broken",
                    installer_available=True,
                )
                self.window._installer_prompt_token = None  # noqa: SLF001
                self.window._maybe_prompt_installer_handoff(repair_result)  # noqa: SLF001
            start_installer.assert_called_once_with(prefer_latest=False)

        with patch("local_assistant.ui.main_window.QTimer.singleShot") as single_shot:
            self.window.service.launch_patch_update = Mock()  # type: ignore[method-assign]
            self.window._handle_patch_prepared(SimpleNamespace(patch_path="C:/tmp/patch.zip"))  # noqa: SLF001
            self.window.service.launch_patch_update.assert_called_once()
            single_shot.assert_called()

        with patch.object(self.window, "_handle_patch_failed") as handle_failed:
            self.window._handle_patch_prepared(SimpleNamespace())  # noqa: SLF001
        handle_failed.assert_called_once()

        with patch("local_assistant.ui.main_window.QTimer.singleShot") as single_shot:
            self.window.service.launch_installer = Mock()  # type: ignore[method-assign]
            self.window._handle_installer_prepared(SimpleNamespace(installer_path="C:/tmp/setup.exe"))  # noqa: SLF001
            self.window.service.launch_installer.assert_called_once()
            single_shot.assert_called()

        with (
            patch.object(self.window, "_finish_event"),
            patch.object(self.window, "_notify") as notify,
        ):
            self.window._handle_patch_failed("checksum mismatch")  # noqa: SLF001
            self.window._handle_installer_failed("signature is invalid")  # noqa: SLF001
        self.assertGreaterEqual(notify.call_count, 2)

        with patch.object(self.window, "_show_warning") as show_warning:
            self.window.current_conversation_id = None
            self.window._export_current("markdown")  # noqa: SLF001
        show_warning.assert_called_once()

        self.window.current_conversation_id = "c1"
        with patch("local_assistant.ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")):
            self.window._export_current("markdown")  # noqa: SLF001

        with patch("local_assistant.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(self.paths.exports_dir / "out.md"), "")):
            with (
                patch.object(self.window.service, "export_conversation_markdown"),
                patch.object(self.window, "_notify") as notify,
            ):
                self.window._export_current("markdown")  # noqa: SLF001
        notify.assert_called_once()

    def test_health_message_and_interaction_helpers(self) -> None:
        with patch.object(self.window.service, "get_source_health", side_effect=RuntimeError("boom")):
            self.window._health_snapshot_valid = False  # noqa: SLF001
            self.window._refresh_health_banner()  # noqa: SLF001
        self.assertEqual(self.window.current_health.status, "error")

        self.window._apply_health(ProviderHealth(status="missing_model", detail="not installed"))  # noqa: SLF001
        self.assertTrue(self.window.health_banner.text())
        self.assertIn("setup", self.window._status_mode)  # noqa: SLF001

        self.assertEqual(self.window._normalize_error_message(RuntimeError("plain")), "plain")  # noqa: SLF001
        self.assertTrue(self.window._normalize_error_message(ProviderError("Local runtime missing")))  # noqa: SLF001
        self.assertTrue(self.window._consumer_health_detail(ProviderHealth(status="error", detail="timed out")))  # noqa: SLF001

        with (
            patch("local_assistant.ui.main_window.SheetDialog") as dialog_cls,
            patch.object(self.window, "_show_alert") as show_alert,
        ):
            dialog_cls.return_value.exec.return_value = 0
            self.window._show_message_box(QMessageBox.Icon.Warning, "Title", "Message")  # noqa: SLF001
        show_alert.assert_called_once()

        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        self.window.current_conversation_id = "c1"
        self.window._update_interaction_state()  # noqa: SLF001
        self.assertTrue(self.window.send_button.isEnabled())
        self.window.pending_action_id = "a1"
        self.window._update_interaction_state()  # noqa: SLF001
        self.assertTrue(self.window._is_locked())  # noqa: SLF001

    def test_additional_main_window_branches(self) -> None:
        with patch("local_assistant.ui.main_window.resolve_asset", return_value=Path("missing.png")):
            self.window._apply_brand_art()  # noqa: SLF001

        with patch("local_assistant.ui.main_window.QApplication.primaryScreen", return_value=None):
            self.window._position_window()  # noqa: SLF001

        self.window.service.list_models = Mock(side_effect=RuntimeError("no models"))  # type: ignore[method-assign]
        self.window._cached_provider_models = []  # noqa: SLF001
        self.window._populate_models()  # noqa: SLF001
        self.assertGreaterEqual(self.window.model_combo.count(), 1)

        descriptor = LocalModelDescriptor(
            model_id="demo-model",
            display_name="Demo",
            description="Desc",
            source="hf",
            download_url="https://example.com/demo.gguf",
            file_name="demo.gguf",
            size_hint="1 MB",
            quantization="Q4",
            recommended_ram_gb=8,
            context_length=4096,
        )
        self.window._cached_local_models = [descriptor]  # noqa: SLF001
        self.window.settings.model = "demo-model"
        self.window._populate_local_models()  # noqa: SLF001
        self.assertIn("1 MB", self.window.local_model_combo.itemText(0))
        self.assertIn("RAM: 8 GB+", self.window.local_model_combo.itemData(0, Qt.ItemDataRole.ToolTipRole))

        self.assertEqual(self.window._format_conversation_timestamp("bad"), "")  # noqa: SLF001

        installed = InstalledLocalModel(
            model_id="demo-model",
            file_path="C:/models/demo.gguf",
            file_name="demo.gguf",
            source="hf",
            downloaded_at="2026-03-17T00:00:00+00:00",
            size_bytes=10,
        )
        self.window._cached_installed_models = {"demo-model": installed}  # noqa: SLF001
        self.window._runtime_binary_available = False  # noqa: SLF001
        self.window.current_health = ProviderHealth(status="error", detail="offline")
        self.window._refresh_local_model_status()  # noqa: SLF001
        self.assertIn("runtime", self.window.local_model_status_value.text().lower())
        self.window.runtime_refresh_worker = object()  # type: ignore[assignment]
        self.window._runtime_binary_available = True  # noqa: SLF001
        self.window._refresh_local_model_status()  # noqa: SLF001
        self.assertNotEqual(self.window.local_model_status_value.text(), "")
        self.window.runtime_refresh_worker = None

        self.window.service.remove_local_model = Mock(side_effect=RuntimeError("remove failed"))  # type: ignore[method-assign]
        with patch.object(self.window, "_show_error") as show_error:
            self.window._remove_selected_local_model()  # noqa: SLF001
        show_error.assert_called_once()

        self.window.settings.last_conversation_id = None
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with patch.object(self.window, "_render_messages") as render_messages:
            self.window._restore_last_conversation()  # noqa: SLF001
        render_messages.assert_called_once()

        self.window.local_model_combo.clear()
        self.window.local_model_combo.addItem("Demo", "demo-model")
        self.window.model_combo.clear()
        self.window.model_combo.addItem("Other", "other-model")
        with (
            patch.object(self.window, "_persist_settings") as persist,
            patch.object(self.window, "_refresh_local_model_status") as refresh_local,
            patch.object(self.window, "_refresh_health_banner") as refresh_banner,
        ):
            self.window._handle_local_model_change()  # noqa: SLF001
        persist.assert_called_once()
        refresh_local.assert_called_once()
        refresh_banner.assert_called_once()

        with (
            patch.object(LocalizationManager, "set_language") as set_language,
            patch.object(self.window, "_persist_settings") as persist,
            patch.object(self.window, "_retranslate_ui") as retranslate,
            patch.object(self.window, "_refresh_health_banner") as refresh_banner,
        ):
            self.window._handle_language_change()  # noqa: SLF001
        set_language.assert_called_once()
        persist.assert_called_once()
        retranslate.assert_called_once()
        refresh_banner.assert_called_once()

        self.window.current_conversation_id = "c1"
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with (
            patch.object(self.window, "sender", return_value=object()),
            patch.object(self.window, "_apply_theme") as apply_theme,
            patch.object(self.window, "_populate_theme_choices") as populate_choices,
            patch.object(self.window, "_persist_settings") as persist,
            patch.object(self.window, "_update_nav_state") as update_nav,
            patch.object(self.window, "_render_messages") as render_messages,
        ):
            self.window._handle_theme_change()  # noqa: SLF001
        apply_theme.assert_called_once()
        populate_choices.assert_called_once()
        persist.assert_called_once()
        update_nav.assert_called_once()
        render_messages.assert_called_once()

        self.window.composer.setPlainText("   ")
        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        with patch.object(self.window.service, "prepare_user_generation", side_effect=AssertionError("should not be called")):
            self.window._send_message()  # noqa: SLF001
        self.window.composer.setPlainText("hello")
        self.window.service.prepare_user_generation = Mock(side_effect=RuntimeError("send failed"))  # type: ignore[method-assign]
        with patch.object(self.window, "_show_error") as show_error:
            self.window._send_message()  # noqa: SLF001
        show_error.assert_called_once()

        self.window.current_assistant_message_id = None
        self.window._handle_generation_chunk("chunk")  # noqa: SLF001
        self.window.current_assistant_message_id = "m1"
        self.window.current_conversation_id = None
        with patch.object(self.window.service, "append_to_message") as append_to_message:
            self.window._handle_generation_chunk("chunk")  # noqa: SLF001
        append_to_message.assert_called_once()

        self.window.current_assistant_message_id = "m1"
        with patch.object(self.window.service, "update_message_metadata") as update_metadata:
            self.window._handle_generation_metadata({})
            self.window._handle_generation_metadata("bad")
            self.window._handle_generation_metadata({"ok": True})
        update_metadata.assert_called_once_with("m1", {"ok": True})

        self.window.current_assistant_message_id = "m1"
        self.window.current_conversation_id = "c1"
        self.window.service.parse_action_request = Mock(return_value=None)  # type: ignore[method-assign]
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with (
            patch.object(self.window.service, "finalize_message"),
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_populate_conversations"),
            patch.object(self.window, "_notify") as notify,
            patch.object(self.window, "_refresh_activity_chip") as refresh_chip,
        ):
            self.window._handle_generation_completed()  # noqa: SLF001
        notify.assert_called_once()
        refresh_chip.assert_called_once_with("ready")

        action = AssistantAction(
            action_id="a2",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="command_run",
            title="Run",
            description="Run command",
            target="echo hi",
            risk="medium",
            payload={"command": "echo hi"},
        )
        self.window.service.parse_action_request = Mock(return_value=action)  # type: ignore[method-assign]
        with (
            patch.object(self.window.service, "finalize_message"),
            patch.object(self.window.service, "mark_action_denied", return_value=action),
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_populate_conversations"),
            patch.object(self.window, "_show_approval_sheet", return_value=False),
            patch.object(self.window, "_notify") as notify,
            patch.object(self.window, "_continue_after_action") as continue_after,
        ):
            self.window._handle_generation_completed()  # noqa: SLF001
        notify.assert_called_once()
        continue_after.assert_called_once()

        self.window.current_assistant_message_id = None
        self.window._handle_generation_completed()  # noqa: SLF001

        self.window.current_assistant_message_id = None
        with patch.object(self.window, "_show_error") as show_error:
            self.window._handle_generation_failed("boom", cancelled=False)  # noqa: SLF001
        show_error.assert_called_once()
        with patch.object(self.window, "_notify") as notify:
            self.window._handle_generation_failed("cancelled", cancelled=True)  # noqa: SLF001
        notify.assert_called_once()

        self.window.generation_worker = None
        self.window._cancel_generation()  # noqa: SLF001
        self.window.pending_action_id = "a1"
        self.window.action_worker = object()  # type: ignore[assignment]
        self.window._allow_pending_action()  # noqa: SLF001
        self.window._deny_pending_action()  # noqa: SLF001
        self.window.action_worker = None
        self.window.service.get_action = lambda _aid: None  # type: ignore[method-assign]
        self.window._allow_pending_action()  # noqa: SLF001

        self.window.service.build_action_follow_up = Mock(side_effect=RuntimeError("follow-up failed"))  # type: ignore[method-assign]
        with patch.object(self.window, "_show_error") as show_error:
            self.window._continue_after_action(action)  # noqa: SLF001
        show_error.assert_called_once()

        self.window.runtime_refresh_worker = object()  # type: ignore[assignment]
        self.window._start_runtime_refresh(manual=True)  # noqa: SLF001
        self.window.runtime_refresh_worker = None
        self.window._handle_runtime_refresh_completed(object())  # noqa: SLF001

        with patch.object(self.window, "_finish_event") as finish_event:
            self.window._handle_runtime_refresh_completed(
                RuntimeRefreshResult(
                    status=RuntimeStatus(current_version="0.2.0"),
                    local_status="missing_runtime",
                    local_detail="",
                    runtime_ready=False,
                    provider_health=ProviderHealth(status="missing_runtime", detail="runtime missing"),
                )
            )  # noqa: SLF001
            self.window._handle_runtime_refresh_completed(
                RuntimeRefreshResult(
                    status=RuntimeStatus(current_version="0.2.0"),
                    local_status="error",
                    local_detail="timed out",
                    runtime_ready=False,
                    provider_health=ProviderHealth(status="error", detail="timed out"),
                )
            )  # noqa: SLF001
        self.assertGreaterEqual(finish_event.call_count, 2)

        self.window.runtime_status.latest_version = "0.2.1"
        self.window._installer_prompt_token = "patch:0.2.1"  # noqa: SLF001
        with patch.object(self.window, "_start_patch_handoff") as start_patch:
            self.window._maybe_prompt_installer_handoff(
                RuntimeRefreshResult(
                    status=RuntimeStatus(current_version="0.2.0", latest_version="0.2.1"),
                    update_available=True,
                    update_kind="patch",
                    patch_available=True,
                )
            )  # noqa: SLF001
        start_patch.assert_not_called()

        self.window._installer_prompt_token = None  # noqa: SLF001
        with patch("local_assistant.ui.main_window.SheetDialog") as dialog_cls:
            dialog_cls.return_value.DialogCode.Accepted = 1
            dialog_cls.return_value.exec.return_value = 0
            with patch.object(self.window, "_start_installer_handoff") as start_installer:
                self.window._maybe_prompt_installer_handoff(
                    RuntimeRefreshResult(
                        status=RuntimeStatus(current_version="0.2.0", latest_version="0.2.2"),
                        update_available=True,
                        installer_available=True,
                    )
                )  # noqa: SLF001
            start_installer.assert_not_called()

        self.window.installer_worker = object()  # type: ignore[assignment]
        with patch.object(self.window, "_notify") as notify:
            self.window._start_patch_handoff()  # noqa: SLF001
        notify.assert_called_once()
        self.window.installer_worker = None

        self.window.runtime_status = RuntimeStatus(current_version="0.2.0", last_check_status="error", last_check_error="bad")
        self.assertIn("bad", self.window._runtime_status_text())  # noqa: SLF001

        with (
            patch("local_assistant.ui.main_window.QMenu") as menu_cls,
            patch("local_assistant.ui.main_window.QDesktopServices.openUrl") as open_url,
        ):
            menu = menu_cls.return_value
            developer_action = object()
            github_action = object()
            menu.addAction.side_effect = [developer_action, github_action]
            menu.exec.return_value = developer_action
            self.window._open_support_menu()  # noqa: SLF001
        open_url.assert_called_once()

        self.window._health_snapshot_valid = True  # noqa: SLF001
        self.window.current_health = ProviderHealth(status="missing_model", detail="not installed")
        self.window._refresh_health_banner()  # noqa: SLF001
        self.assertEqual(self.window.health_banner.objectName(), "HealthBannerWarning")

        self.window.action_worker = object()  # type: ignore[assignment]
        with patch.object(self.window, "_refresh_activity_chip") as refresh_chip:
            self.window._apply_health(ProviderHealth(status="ready", detail="ok"))  # noqa: SLF001
        refresh_chip.assert_called_once_with("busy")
        self.window.action_worker = None

        self.window.current_conversation_id = "c1"
        with patch("local_assistant.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(self.paths.exports_dir / "out.json"), "")):
            with (
                patch.object(self.window.service, "export_conversation_json", side_effect=RuntimeError("export failed")),
                patch.object(self.window, "_show_error") as show_error,
            ):
                self.window._export_current("json")  # noqa: SLF001
        show_error.assert_called_once()

        self.window.model_combo.clear()
        self.window.model_combo.setEditable(True)
        self.window.model_combo.setCurrentText("fallback-model")
        self.assertEqual(self.window._selected_model_id(), "fallback-model")  # noqa: SLF001
        self.window.theme_combo.setCurrentIndex(-1)
        self.assertEqual(self.window._selected_theme(), self.window.settings.theme)  # noqa: SLF001

        with patch("local_assistant.ui.main_window.QApplication.instance", return_value=None):
            self.window._apply_theme("dark")  # noqa: SLF001

        self.assertEqual(self.window._consumer_health_detail(ProviderHealth(status="error", detail="")), "")  # noqa: SLF001

        with (
            patch.object(self.window, "_show_message_box") as show_message_box,
            patch("local_assistant.ui.main_window.LOGGER") as logger,
        ):
            self.window._show_error("Oops", RuntimeError("boom"))  # noqa: SLF001
        logger.exception.assert_called_once()
        show_message_box.assert_called_once()

        with patch.object(self.window.notification_center, "show_alert") as show_alert:
            self.window._notify("Hi", "There", variant="success", timeout_ms=123)  # noqa: SLF001
        show_alert.assert_called_once()

        fake_thread = Mock()
        fake_worker = Mock()
        fake_event = Mock()
        self.window.generation_worker = fake_worker  # type: ignore[assignment]
        self.window.generation_thread = fake_thread  # type: ignore[assignment]
        self.window.action_thread = fake_thread  # type: ignore[assignment]
        self.window.runtime_refresh_thread = fake_thread  # type: ignore[assignment]
        self.window.installer_thread = fake_thread  # type: ignore[assignment]
        self.window.model_download_worker = fake_worker  # type: ignore[assignment]
        self.window.model_download_thread = fake_thread  # type: ignore[assignment]
        with patch.object(self.window.service.runtime_service, "stop") as stop_runtime:
            self.window.closeEvent(fake_event)  # noqa: SLF001
        self.assertTrue(fake_worker.cancel.called)
        self.assertTrue(fake_thread.quit.called)
        stop_runtime.assert_called_once()
        fake_event.accept.assert_called_once()

    def test_ui_helper_population_and_branding_methods(self) -> None:
        self.window._apply_icons()  # noqa: SLF001
        self.assertFalse(self.window.send_button.icon().isNull())

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "icon.png"
            image = QImage(16, 16, QImage.Format.Format_ARGB32)
            image.fill(0xFF336699)
            image.save(str(image_path))
            with patch("local_assistant.ui.main_window.resolve_asset", return_value=image_path):
                self.window._apply_brand_art()  # noqa: SLF001
            self.assertIsNotNone(self.window.profile_icon_label.pixmap())

        fake_screen = Mock()
        fake_screen.availableGeometry.return_value = QRect(0, 0, 1200, 800)
        with patch("local_assistant.ui.main_window.QApplication.primaryScreen", return_value=fake_screen):
            self.window._position_window()  # noqa: SLF001

        self.window._populate_language_choices("en")  # noqa: SLF001
        self.assertEqual(self.window.language_combo.currentData(), "en")
        self.window._populate_theme_choices("light")  # noqa: SLF001
        self.assertEqual(self.window.theme_combo.currentData(), "light")
        self.window._populate_source_choices("local")  # noqa: SLF001
        self.window._populate_chat_source_choices("local")  # noqa: SLF001
        self.window._populate_providers()  # noqa: SLF001
        self.assertEqual(self.window.provider_combo.currentData(), "local_llama")

        self.window._cached_provider_models = [ModelDescriptor(model_id="demo-model", display_name="Demo", description="desc")]  # noqa: SLF001
        self.window._populate_models()  # noqa: SLF001
        self.assertGreaterEqual(self.window.model_combo.count(), 1)
        self.window._cached_local_models = [
            LocalModelDescriptor(
                model_id="demo-model",
                display_name="Demo",
                description="Local demo",
                source="hf",
                download_url="https://example.com/demo.gguf",
                file_name="demo.gguf",
                size_hint="1 MB",
                quantization="Q4",
                recommended_ram_gb=8,
                context_length=4096,
            )
        ]  # noqa: SLF001
        self.window._populate_local_models()  # noqa: SLF001
        self.assertGreaterEqual(self.window.local_model_combo.count(), 1)

        settings = self.window.settings
        settings.language = "en"
        settings.theme = "light"
        settings.command_allowlist = ["echo", "dir"]
        self.window._apply_settings_to_form(settings)  # noqa: SLF001
        self.assertEqual(self.window.language_combo.currentData(), "en")
        self.assertEqual(self.window.theme_combo.currentData(), "light")
        self.assertIn("echo", self.window.command_allowlist_input.text())

        self.window._retranslate_ui()  # noqa: SLF001
        self.assertTrue(self.window.windowTitle())

        self.window._apply_consumer_mode()  # noqa: SLF001
        self.assertFalse(self.window.chat_source_combo.isVisible())

        temp_root = self.window.centralWidget().layout()
        self.window._build_bottom_nav(temp_root)  # noqa: SLF001
        self.assertIsNotNone(self.window.bottom_nav_card)

        self.window._apply_glass_effects()  # noqa: SLF001
        self.assertIsNotNone(self.window.sidebar_panel.graphicsEffect())
        self.assertIsNotNone(self.window.settings_panel.graphicsEffect())

        self.window._sync_overlay_geometry()  # noqa: SLF001
        self.assertEqual(self.window.overlay_host.geometry(), self.window.centralWidget().rect())

        self.window._position_bottom_nav()  # noqa: SLF001
        self.assertGreater(self.window.bottom_nav.geometry().width(), 0)
        self.window._position_chat_composer_overlay()  # noqa: SLF001
        self.window._reposition_overlays()  # noqa: SLF001

    def test_generation_runtime_and_installer_thread_start_helpers(self) -> None:
        signal = lambda: SimpleNamespace(connect=Mock())  # noqa: E731
        fake_thread = Mock()
        fake_thread.started = signal()
        fake_thread.finished = signal()
        fake_generation_worker = Mock()
        fake_generation_worker.chunk_received = signal()
        fake_generation_worker.metadata_received = signal()
        fake_generation_worker.completed = signal()
        fake_generation_worker.failed = signal()
        fake_generation_worker.finished = signal()

        prepared = self._prepared()
        with patch.object(self.window, "_show_error") as show_error:
            self.window.service.providers.get = lambda _pid: (_ for _ in ()).throw(RuntimeError("missing provider"))  # type: ignore[method-assign]
            self.window._start_generation(prepared)  # noqa: SLF001
        show_error.assert_called_once()

        self.window.service.providers.get = lambda _pid: FakeProvider()  # type: ignore[method-assign]
        with (
            patch("local_assistant.ui.main_window.QThread", return_value=fake_thread),
            patch("local_assistant.ui.main_window.GenerationWorker", return_value=fake_generation_worker),
            patch.object(self.window, "_update_interaction_state"),
        ):
            self.window._start_generation(prepared)  # noqa: SLF001
        fake_thread.start.assert_called_once()

        self.window.current_assistant_message_id = "m1"
        self.window.current_conversation_id = "c1"
        self.window.service.append_to_message = Mock()  # type: ignore[method-assign]
        self.window.service.load_messages = lambda _cid: []  # type: ignore[method-assign]
        with patch.object(self.window, "_render_messages") as render_messages:
            self.window._handle_generation_chunk("abc")  # noqa: SLF001
        self.window.service.append_to_message.assert_called_once()  # type: ignore[attr-defined]
        render_messages.assert_called_once()

        self.window.service.update_message_metadata = Mock()  # type: ignore[method-assign]
        self.window._handle_generation_metadata({"reasoning_details": []})  # noqa: SLF001
        self.window.service.update_message_metadata.assert_called_once()  # type: ignore[attr-defined]

        self.window.service.finalize_message = Mock()  # type: ignore[method-assign]
        self.window.service.parse_action_request = lambda _mid: None  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_populate_conversations"),
            patch.object(self.window, "_notify") as notify,
            patch.object(self.window, "_refresh_activity_chip") as refresh_chip,
        ):
            self.window._handle_generation_completed()  # noqa: SLF001
        notify.assert_called_once()
        refresh_chip.assert_called_with("ready")

        action = AssistantAction(
            action_id="a1",
            conversation_id="c1",
            assistant_message_id="m1",
            kind="command_run",
            title="Run",
            description="Run",
            target="echo hi",
            risk="high",
            payload={"command": "echo hi"},
        )
        self.window.pending_action_id = None
        self.window.service.parse_action_request = lambda _mid: action  # type: ignore[method-assign]
        self.window.service.mark_action_approved = lambda _aid: action  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_populate_conversations"),
            patch.object(self.window, "_show_approval_sheet", return_value=True),
            patch.object(self.window, "_start_action_execution") as start_action,
        ):
            self.window._handle_generation_completed()  # noqa: SLF001
        start_action.assert_called_once()

        self.window.service.fail_message = Mock()  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_render_messages"),
            patch.object(self.window, "_notify") as notify,
            patch.object(self.window, "_show_error") as show_error,
        ):
            self.window._handle_generation_failed("cancelled", True)  # noqa: SLF001
            self.window._handle_generation_failed("boom", False)  # noqa: SLF001
        self.assertGreaterEqual(notify.call_count, 1)
        show_error.assert_called_once()

        self.window.generation_worker = Mock()
        with patch.object(self.window, "_notify") as notify:
            self.window._cancel_generation()  # noqa: SLF001
        self.window.generation_worker.cancel.assert_called_once()
        notify.assert_called_once()

        runtime_thread = Mock()
        runtime_thread.started = signal()
        runtime_thread.finished = signal()
        runtime_worker = Mock()
        runtime_worker.completed = signal()
        runtime_worker.failed = signal()
        runtime_worker.finished = signal()
        with (
            patch("local_assistant.ui.main_window.QThread", return_value=runtime_thread),
            patch("local_assistant.ui.main_window.RuntimeRefreshWorker", return_value=runtime_worker),
            patch.object(self.window, "_persist_settings"),
            patch.object(self.window, "_refresh_update_section"),
            patch.object(self.window, "_update_interaction_state"),
        ):
            self.window._start_runtime_refresh(manual=True, notify_runtime=True)  # noqa: SLF001
        runtime_thread.start.assert_called_once()

        installer_thread = Mock()
        installer_thread.started = signal()
        installer_thread.finished = signal()
        installer_worker = Mock()
        installer_worker.completed = signal()
        installer_worker.failed = signal()
        installer_worker.finished = signal()
        with (
            patch("local_assistant.ui.main_window.QThread", return_value=installer_thread),
            patch("local_assistant.ui.main_window.InstallerWorker", return_value=installer_worker),
        ):
            self.window._start_patch_handoff()  # noqa: SLF001
        installer_thread.start.assert_called_once()

        installer_thread = Mock()
        installer_thread.started = signal()
        installer_thread.finished = signal()
        installer_worker = Mock()
        installer_worker.completed = signal()
        installer_worker.failed = signal()
        installer_worker.finished = signal()
        self.window.installer_worker = None
        with (
            patch("local_assistant.ui.main_window.QThread", return_value=installer_thread),
            patch("local_assistant.ui.main_window.InstallerWorker", return_value=installer_worker),
        ):
            self.window._start_installer_handoff(prefer_latest=True)  # noqa: SLF001
        installer_thread.start.assert_called_once()

    def test_main_window_misc_state_scroll_and_profile_helpers(self) -> None:
        self.window._refresh_secret_status()  # noqa: SLF001
        self.assertEqual(self.window._notification_label("Hide"), self.window._t("button_hide"))  # noqa: SLF001
        self.assertEqual(self.window._notification_label("Custom"), "Custom")  # noqa: SLF001
        self.assertEqual(self.window._model_download_event_id("  "), "model-download:active")  # noqa: SLF001
        self.assertEqual(self.window._role_label("assistant"), self.window._t("role_assistant"))  # noqa: SLF001
        self.assertEqual(self.window._localized_action_kind("command_run"), self.window._t("action_command_run"))  # noqa: SLF001
        self.assertEqual(self.window._localized_risk("high"), self.window._t("risk_high"))  # noqa: SLF001
        self.assertEqual(self.window._selected_provider_id(), "local_llama")  # noqa: SLF001
        self.assertEqual(self.window._selected_default_source(), "local")  # noqa: SLF001
        self.assertEqual(self.window._selected_chat_source(), "local")  # noqa: SLF001
        self.assertEqual(self.window._current_chat_source(), "local")  # noqa: SLF001

        self.window.model_combo.clear()
        self.window.model_combo.setEditable(True)
        self.window.model_combo.addItem("Demo", "demo-model")
        self.window.model_combo.setCurrentIndex(0)
        self.assertEqual(self.window._selected_model_id(), "demo-model")  # noqa: SLF001
        self.assertEqual(self.window._selected_model_label(), "Demo")  # noqa: SLF001
        self.assertEqual(self.window._model_display_name("demo-model"), "Demo")  # noqa: SLF001

        editable = QComboBox()
        editable.setEditable(True)
        self.window._set_combo_by_data(editable, "custom")  # noqa: SLF001
        self.assertEqual(editable.currentText(), "custom")

        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        self.window._set_workspace("profile")  # noqa: SLF001
        self.assertEqual(self.window._workspace, "profile")
        self.assertTrue(self.window._header_context_text())  # noqa: SLF001
        self.window._set_workspace("chat")  # noqa: SLF001
        self.window._update_nav_state()  # noqa: SLF001

        with patch("local_assistant.ui.main_window.build_stylesheet", return_value="QWidget{}"):
            self.window._apply_theme("dark")  # noqa: SLF001
        self.assertEqual(self.window.settings.theme, "dark")

        self.window._chat_pinned_to_bottom = True  # noqa: SLF001
        self.window._scroll_chat_to_bottom_if_pinned(True)  # noqa: SLF001
        self.window._handle_chat_scroll(self.window.chat_view.verticalScrollBar().maximum())  # noqa: SLF001
        self.window._handle_chat_composer_geometry_changed()  # noqa: SLF001
        self.window._restore_chat_scroll(0)  # noqa: SLF001
        self.window._typing_indicator_message_id = "m1"  # noqa: SLF001
        self.window.current_conversation_id = None
        self.window._advance_typing_indicator()  # noqa: SLF001
        self.assertEqual(self.window._typing_indicator_text(), "Typing.")  # noqa: SLF001
        self.window._stop_typing_indicator()  # noqa: SLF001

        self.window.current_health = ProviderHealth(status="missing_runtime", detail="runtime binary missing")
        self.assertTrue(self.window._profile_status_text())  # noqa: SLF001
        self.assertTrue(self.window._consumer_health_detail(self.window.current_health))  # noqa: SLF001
        self.assertTrue(self.window._append_health_detail("Body", "Detail"))  # noqa: SLF001
        self.assertEqual(self.window._append_health_detail("Body", "Body"), "Body")  # noqa: SLF001
        self.assertEqual(self.window._provider_display_name("local_llama"), "Local Qwen")  # noqa: SLF001
        self.assertEqual(self.window._provider_id_for_source("local"), "local_llama")  # noqa: SLF001
        self.assertTrue(self.window._model_name_for_source("local"))  # noqa: SLF001
        self.assertTrue(self.window._provider_description("local_llama"))  # noqa: SLF001
        self.assertTrue(self.window._setup_guidance_for_health("local_llama", self.window.current_health, "Demo"))  # noqa: SLF001
        self.window._populate_setup_guidance(self.window.current_health)  # noqa: SLF001

    def test_main_window_install_remove_persist_and_close_helpers(self) -> None:
        self.window.local_model_combo.clear()
        self.window.local_model_combo.addItem("Demo", "demo-model")
        self.window.model_combo.clear()
        self.window.model_combo.addItem("Demo", "demo-model")
        self.window.local_model_combo.setCurrentIndex(0)

        self.window.service.get_installed_local_model = lambda _model_id: object()  # type: ignore[method-assign]
        with patch.object(self.window, "_open_selected_local_model_chat") as open_chat:
            self.window._install_selected_local_model()  # noqa: SLF001
        open_chat.assert_called_once()

        self.window.service.get_installed_local_model = lambda _model_id: None  # type: ignore[method-assign]
        self.window.model_download_worker = object()  # type: ignore[assignment]
        with patch.object(self.window, "_notify") as notify:
            self.window._install_selected_local_model()  # noqa: SLF001
        notify.assert_called_once()
        self.window.model_download_worker = None

        signal = lambda: SimpleNamespace(connect=Mock())  # noqa: E731
        download_thread = Mock()
        download_thread.started = signal()
        download_thread.finished = signal()
        download_worker = Mock()
        download_worker.progress = signal()
        download_worker.completed = signal()
        download_worker.failed = signal()
        download_worker.finished = signal()
        with (
            patch("local_assistant.ui.main_window.QThread", return_value=download_thread),
            patch("local_assistant.ui.main_window.ModelDownloadWorker", return_value=download_worker),
            patch.object(self.window, "_show_event"),
        ):
            self.window._install_selected_local_model()  # noqa: SLF001
        download_thread.start.assert_called_once()

        self.window.current_health = ProviderHealth(status="ready", detail="ok")
        with patch.object(self.window.composer, "setFocus") as set_focus:
            self.window._open_selected_local_model_chat()  # noqa: SLF001
        set_focus.assert_called_once()
        self.window.current_health = ProviderHealth(status="missing_model", detail="missing")
        with (
            patch.object(self.window, "_refresh_health_banner"),
            patch.object(self.window, "_notify") as notify,
        ):
            self.window._open_selected_local_model_chat()  # noqa: SLF001
        notify.assert_called_once()

        self.window.model_download_worker = object()  # type: ignore[assignment]
        self.window._remove_selected_local_model()  # noqa: SLF001
        self.window.model_download_worker = None
        self.window.service.remove_local_model = Mock()  # type: ignore[method-assign]
        self.window.service.list_installed_local_models = lambda: []  # type: ignore[method-assign]
        with (
            patch.object(self.window, "_notify"),
            patch.object(self.window, "_refresh_local_model_status"),
            patch.object(self.window, "_refresh_health_banner"),
        ):
            self.window._remove_selected_local_model()  # noqa: SLF001
        self.window.service.remove_local_model.assert_called_once()  # type: ignore[attr-defined]

        settings = self.window._collect_settings_from_form()  # noqa: SLF001
        self.assertEqual(settings.provider_id, "local_llama")
        self.assertTrue(isinstance(settings.command_allowlist, list))

        with patch.object(self.window.service, "save_settings", side_effect=RuntimeError("persist failed")):
            with patch.object(self.window, "_show_error") as show_error:
                self.window._persist_settings()  # noqa: SLF001
        show_error.assert_called_once()

        self.window._is_closing = True  # noqa: SLF001
        with patch.object(self.window.service, "save_settings") as save_settings:
            self.window._persist_settings()  # noqa: SLF001
        save_settings.assert_not_called()
        self.window._is_closing = False  # noqa: SLF001

        self.window.settings.last_conversation_id = None
        with patch.object(self.window, "_render_messages") as render_messages:
            self.window._restore_last_conversation()  # noqa: SLF001
        render_messages.assert_called()

        self.assertEqual(self.window._normalize_update_error("Trusted release manifest is not available"), self.window._t("update_error_manifest_unavailable"))  # noqa: SLF001
        self.assertEqual(self.window._normalize_update_error("signature is invalid"), self.window._t("update_error_signature_invalid"))  # noqa: SLF001

        event = Mock()
        self.window.closeEvent(event)  # noqa: SLF001
        event.accept.assert_called_once()
