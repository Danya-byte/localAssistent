from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.actions.executor import ActionExecutor
from local_assistant.config import AppPaths
from local_assistant.models import GenerationRequest, MessageRecord, ModelDescriptor, ProviderDescriptor, ProviderHealth
from local_assistant.services import ChatService, RuntimeRefreshResult, RuntimeStatus
from local_assistant.services.update_service import ReleaseCheck, RuntimeManifest, UpdateService
from local_assistant.storage import Storage
from local_assistant.ui.main_window import MainWindow
from local_assistant.ui.pages.chat_page import ChatWorkspace
from local_assistant.ui.theme import build_stylesheet


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

    def stream_chat(self, request: GenerationRequest, cancel_event: Event):
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
        self.release_check = ReleaseCheck(current_version="0.1.0")

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


class SidebarUiTests(unittest.TestCase):
    def test_sidebar_new_chat_button_style_centers_text(self) -> None:
        light_stylesheet = build_stylesheet("light")
        dark_stylesheet = build_stylesheet("dark")
        self.assertIn("QPushButton#SidebarNewChatButton", light_stylesheet)
        self.assertIn("text-align: center;", light_stylesheet)
        self.assertIn("text-align: center;", dark_stylesheet)
        self.assertIn("QFrame#SidebarTitleLine", light_stylesheet)
        self.assertIn("QFrame#SidebarTitleLine", dark_stylesheet)
        self.assertIn("QFrame#PresenceChip", light_stylesheet)
        self.assertIn("QLabel#PresenceChipDot", dark_stylesheet)
        self.assertIn("border-radius: 20px;", light_stylesheet)
        self.assertIn("QLabel#ChatHeaderTitle", dark_stylesheet)
        self.assertIn("QScrollBar:horizontal", light_stylesheet)
        self.assertIn("QScrollArea#ChatView", light_stylesheet)
        self.assertIn("width: 0px;", light_stylesheet)
        self.assertIn("height: 0px;", dark_stylesheet)

    def test_chat_workspace_exposes_compact_sidebar_contract(self) -> None:
        app = get_app()
        workspace = ChatWorkspace()
        workspace.resize(1100, 720)
        workspace.show()
        app.processEvents()

        self.assertEqual(workspace.sidebar_panel.minimumWidth(), 220)
        self.assertEqual(workspace.sidebar_panel.maximumWidth(), 284)
        self.assertEqual(workspace.export_md_button.parentWidget(), workspace.sidebar_panel)
        self.assertEqual(workspace.export_md_button.objectName(), "SidebarFloatingExportButton")
        self.assertEqual(workspace.conversation_list.viewportMargins().bottom(), workspace.SIDEBAR_EXPORT_VIEWPORT_INSET)
        self.assertEqual(workspace.sidebar_title_label.objectName(), "SidebarSectionTitle")
        self.assertEqual(workspace.new_chat_button.objectName(), "SidebarNewChatButton")
        self.assertEqual(workspace.sidebar_title_line_left.objectName(), "SidebarTitleLine")
        self.assertEqual(workspace.sidebar_title_line_right.objectName(), "SidebarTitleLine")
        self.assertEqual(workspace.sidebar_title_row.objectName(), "SidebarTitleRow")
        self.assertLess(workspace.sidebar_header_section.geometry().top(), workspace.conversation_list.geometry().top())
        self.assertEqual(workspace.composer_card.parentWidget(), workspace.chat_surface)
        self.assertEqual(workspace.chat_title.objectName(), "ChatHeaderTitle")
        self.assertLessEqual(workspace.composer.height(), 40)
        self.assertEqual(workspace.chat_composer_geometry, workspace.composer_card.geometry())
        self.assertGreater(workspace.chat_view_bottom_inset, 0)
        self.assertEqual(workspace.chat_view.viewportMargins().bottom(), workspace.chat_view_bottom_inset)

        workspace.close()

    def test_main_window_initializes_in_local_only_mode(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            storage = Storage(paths.db_path)
            service = ChatService(
                storage=storage,
                providers=FakeRegistry(),
                update_service=FakeUpdateService(),
            )
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            window.show()
            app.processEvents()

            self.assertEqual(window._selected_provider_id(), "local_llama")
            self.assertEqual(window._current_chat_source(), "local")
            self.assertTrue(window.new_chat_button.text().startswith("+ "))
            self.assertTrue(bool(window.sidebar_title_label.text().strip()))
            self.assertEqual(window.status_chip.objectName(), "PresenceChip")
            self.assertEqual(window.status_chip.property("state"), "online")
            self.assertEqual(window.status_chip.label.text(), "Online")

            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_conversation_timestamp_formatting_uses_time_for_today_and_date_for_older(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            window.show()
            app.processEvents()

            now = datetime.now().astimezone().replace(second=0, microsecond=0)
            yesterday = now - timedelta(days=1)

            self.assertEqual(window._format_conversation_timestamp(now.isoformat()), now.strftime("%H:%M"))
            self.assertEqual(window._format_conversation_timestamp(yesterday.isoformat()), yesterday.strftime("%d.%m"))

            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_message_bubble_html_is_adaptive_and_left_aligned(self) -> None:
        bubble_html = MainWindow._message_bubble_html(  # noqa: SLF001
            content="Short",
            status_suffix="",
            is_user=False,
            dark=False,
        )

        self.assertIn("display:inline-block;width:auto;min-width:0;max-width:620px;", bubble_html)
        self.assertIn("border-radius:22px;", bubble_html)
        self.assertIn("border:1px solid", bubble_html)
        self.assertIn("text-align:left;", bubble_html)
        self.assertIn("font-size:15px;", bubble_html)
        self.assertIn("padding:11px 16px 12px 16px;", bubble_html)

    def test_chat_renderer_document_uses_shrink_wrap_bubbles(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            now = datetime.now().astimezone()
            messages = [
                MessageRecord(
                    message_id="m1",
                    conversation_id="c1",
                    role="user",
                    content="hi",
                    status="completed",
                    created_at=now,
                    updated_at=now,
                ),
                MessageRecord(
                    message_id="m2",
                    conversation_id="c1",
                    role="assistant",
                    content="hello",
                    status="completed",
                    created_at=now,
                    updated_at=now,
                ),
            ]
            html_document = window._chat_renderer.render_document(  # noqa: SLF001
                messages=messages,
                dark=True,
                typing_message_id=None,
                has_received_generation_chunk=False,
                typing_phase=0,
                bottom_spacer_px=0,
            )
            self.assertIn("<table", html_document)
            self.assertIn("display:inline-block;width:auto;min-width:0;max-width:620px;", html_document)
            self.assertIn("height:0px", html_document)
            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_typing_indicator_text_animates_dots(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            window._typing_indicator_phase = 0  # noqa: SLF001
            self.assertEqual(window._typing_indicator_text(), "Typing.")  # noqa: SLF001
            window._typing_indicator_phase = 1  # noqa: SLF001
            self.assertEqual(window._typing_indicator_text(), "Typing..")  # noqa: SLF001
            window._typing_indicator_phase = 2  # noqa: SLF001
            self.assertEqual(window._typing_indicator_text(), "Typing...")  # noqa: SLF001
            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_assistant_avatar_uses_image_asset(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            window.show()
            app.processEvents()

            avatar_html = window._assistant_avatar_html(dark=False)  # noqa: SLF001
            self.assertIn("data:image/png;base64,", avatar_html)
            user_avatar_html = window._user_avatar_html()  # noqa: SLF001
            self.assertIn("data:image/png;base64,", user_avatar_html)

            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_render_messages_respects_pinned_scroll_state(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            window.show()
            app.processEvents()

            now = datetime.now().astimezone()
            messages = [
                MessageRecord(
                    message_id=f"m{index}",
                    conversation_id="c1",
                    role="assistant",
                    content=f"Line {index} " * 20,
                    status="completed",
                    created_at=now,
                    updated_at=now,
                )
                for index in range(10)
            ]
            window._chat_pinned_to_bottom = True  # noqa: SLF001
            self.assertEqual(window._current_chat_bottom_spacer(True), 0)  # noqa: SLF001
            self.assertGreater(window.chat_workspace_widget.chat_view_bottom_inset, 0)
            window._render_messages(messages)  # noqa: SLF001
            app.processEvents()
            scrollbar = window.chat_view.verticalScrollBar()
            self.assertEqual(scrollbar.value(), scrollbar.maximum())

            window._chat_pinned_to_bottom = False  # noqa: SLF001
            self.assertEqual(window._current_chat_bottom_spacer(False), 0)  # noqa: SLF001
            scrollbar.setValue(0)
            window._render_messages(messages)  # noqa: SLF001
            app.processEvents()
            self.assertEqual(scrollbar.value(), 0)

            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_render_messages_builds_real_qt_bubbles_for_both_roles(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            window.show()
            app.processEvents()

            now = datetime.now().astimezone()
            messages = [
                MessageRecord(
                    message_id="m1",
                    conversation_id="c1",
                    role="user",
                    content="user text",
                    status="completed",
                    created_at=now,
                    updated_at=now,
                ),
                MessageRecord(
                    message_id="m2",
                    conversation_id="c1",
                    role="assistant",
                    content="assistant text",
                    status="completed",
                    created_at=now,
                    updated_at=now,
                ),
            ]
            window._render_messages(messages)  # noqa: SLF001
            app.processEvents()

            bubbles = window.chat_messages_host.findChildren(QFrame, "ChatBubble")
            owners = {bubble.property("owner") for bubble in bubbles}
            self.assertEqual(len(bubbles), 2)
            self.assertEqual(owners, {"user", "assistant"})

            window.close()
            app.processEvents()
        finally:
            temp_dir.cleanup()

    def test_chat_workspace_composer_grows_upward(self) -> None:
        app = get_app()
        workspace = ChatWorkspace()
        workspace.resize(1100, 720)
        workspace.show()
        app.processEvents()

        initial_geometry = workspace.composer_card.geometry()
        initial_bottom = initial_geometry.bottom()
        initial_inset = workspace.chat_view_bottom_inset
        self.assertLessEqual(initial_geometry.height(), 104)
        workspace.composer.setPlainText("one line\nsecond line\nthird line")
        app.processEvents()

        grown_geometry = workspace.composer_card.geometry()
        self.assertGreater(grown_geometry.height(), initial_geometry.height())
        self.assertEqual(grown_geometry.bottom(), initial_bottom)
        self.assertGreater(workspace.chat_view_bottom_inset, initial_inset)
        self.assertEqual(workspace.chat_view.viewportMargins().bottom(), workspace.chat_view_bottom_inset)

        workspace.close()

    def test_runtime_refresh_completion_uses_snapshot_without_service_requery(self) -> None:
        app = get_app()
        temp_dir = tempfile.TemporaryDirectory()
        window = None
        original_list_models = None
        original_get_source_health = None
        try:
            root = Path(temp_dir.name)
            paths = make_paths(root)
            paths.ensure()
            service = ChatService(storage=Storage(paths.db_path), providers=FakeRegistry(), update_service=FakeUpdateService())
            window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
            window._background_refresh_timer.stop()  # noqa: SLF001
            result = RuntimeRefreshResult(
                status=RuntimeStatus(current_version="0.1.0", last_check_status="ok"),
                local_status="ready",
                local_detail="Local runtime is ready.",
                runtime_ready=True,
                provider_health=ProviderHealth(status="ready", detail="Local runtime is ready.", models=[ModelDescriptor(model_id="demo-model", display_name="demo-model")]),
                provider_models=[ModelDescriptor(model_id="demo-model", display_name="demo-model")],
                local_models=[],
                installed_local_models=[],
                runtime_binary_available=True,
            )

            original_list_models = window.service.list_models
            original_get_source_health = window.service.get_source_health
            window.service.list_models = lambda _provider_id: (_ for _ in ()).throw(AssertionError("service.list_models should not be called"))  # type: ignore[method-assign]
            window.service.get_source_health = lambda _source="local": (_ for _ in ()).throw(AssertionError("service.get_source_health should not be called"))  # type: ignore[method-assign]
            window._handle_runtime_refresh_completed(result)  # noqa: SLF001
            app.processEvents()

            self.assertEqual(window.current_health.status, "ready")
            self.assertGreaterEqual(window.model_combo.count(), 1)
            self.assertIn(
                "demo-model",
                [window.model_combo.itemData(index) for index in range(window.model_combo.count())],
            )
        finally:
            if window is not None:
                try:
                    if original_list_models is not None:
                        window.service.list_models = original_list_models  # type: ignore[method-assign]
                    if original_get_source_health is not None:
                        window.service.get_source_health = original_get_source_health  # type: ignore[method-assign]
                except Exception:
                    pass
                window.close()
                app.processEvents()
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
