from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, QThread, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QColor, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ..actions.executor import ActionExecutor
from ..config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER_ID,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEVELOPER_URL,
    PRODUCT_GITHUB_URL,
    AppPaths,
    resolve_asset,
)
from ..exceptions import ProviderError
from ..i18n import LocalizationManager
from ..models import AppSettings, AssistantAction, Language, MessageRecord, ModelDownloadProgress, ModelSource, ProviderHealth, ThemeMode
from ..services import RuntimeRefreshResult, RuntimeStatus
from ..services.chat_service import ChatService, PreparedGeneration
from .components import BottomNav, ChatEmptyState, ChatMessageRow, ChatRenderer, ConversationListDelegate, NotificationCenter, PresenceChip, SheetDialog
from .components.chat_layout import compute_chat_composer_bottom_clearance
from .components.chat_rendering import build_message_bubble_html, typing_indicator_text
from .components.conversation_list_delegate import CONVERSATION_ID_ROLE, CONVERSATION_TIMESTAMP_ROLE, CONVERSATION_TITLE_ROLE
from .pages import ChatWorkspace, ProfilePage
from .theme import build_stylesheet
from .workers import ActionWorker, GenerationWorker, InstallerWorker, ModelDownloadWorker, RuntimeRefreshWorker


LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    RUNTIME_EVENT_ID = "runtime:local"
    INSTALLER_EVENT_ID = "runtime:installer"
    PATCH_EVENT_ID = "runtime:patch"

    def __init__(self, service: ChatService, executor: ActionExecutor, paths: AppPaths) -> None:
        super().__init__()
        self.service = service
        self.executor = executor
        self.paths = paths
        self.state = self.service.initialize()
        self.settings = self.state.settings
        self.localization = LocalizationManager(self.settings.language or DEFAULT_LANGUAGE)

        self.current_conversation_id: str | None = None
        self.current_assistant_message_id: str | None = None
        self.pending_action_id: str | None = None
        self.generation_thread: QThread | None = None
        self.generation_worker: GenerationWorker | None = None
        self.action_thread: QThread | None = None
        self.action_worker: ActionWorker | None = None
        self.runtime_refresh_thread: QThread | None = None
        self.runtime_refresh_worker: RuntimeRefreshWorker | None = None
        self.model_download_thread: QThread | None = None
        self.model_download_worker: ModelDownloadWorker | None = None
        self.installer_thread: QThread | None = None
        self.installer_worker: InstallerWorker | None = None
        self.runtime_status: RuntimeStatus = self.service.get_runtime_status()
        self._status_mode = "ready"
        self._updating_form = False
        self._draft_chat_source: ModelSource = self.settings.default_source
        self._conversation_items: dict[str, QListWidgetItem] = {}
        self._provider_descriptors = {item.provider_id: item for item in self.service.list_provider_descriptors()}
        self._rendered_provider_id: str | None = None
        self.provider_config_inputs: dict[str, QLineEdit] = {}
        self.provider_secret_status_labels: dict[str, QLabel] = {}
        self.current_health = ProviderHealth(status="error", detail="", models=[])
        self._workspace = "chat"
        self._installer_prompt_token: str | None = None
        self._is_closing = False
        self._chat_pinned_to_bottom = True
        self._chat_autoscrolling = False
        self._cached_provider_models = []
        self._cached_local_models = []
        self._cached_installed_models: dict[str, object] = {}
        self._runtime_binary_available = False
        self._health_snapshot_valid = False
        self._last_chat_signature: tuple[object, ...] | None = None
        self._last_chat_bottom_spacer = -1
        self._typing_indicator_timer = QTimer(self)
        self._typing_indicator_timer.setInterval(400)
        self._typing_indicator_timer.timeout.connect(self._advance_typing_indicator)
        self._typing_indicator_phase = 0
        self._typing_indicator_message_id: str | None = None
        self._has_received_generation_chunk = False
        self._background_refresh_timer = QTimer(self)
        self._background_refresh_timer.setSingleShot(True)
        self._background_refresh_timer.timeout.connect(self._schedule_background_runtime_refresh)
        self._chat_renderer = ChatRenderer(self._t)
        self._cached_local_models = list(self.service.list_local_models())
        self._cached_installed_models = {item.model_id: item for item in self.service.list_installed_local_models()}
        self._runtime_binary_available = self.service.runtime_service.is_binary_available()

        self.setWindowTitle(APP_NAME)
        self.resize(1120, 720)
        self.setMinimumSize(920, 580)
        self._setup_ui()
        self._position_window()
        self._apply_icons()
        self._apply_brand_art()
        self._apply_glass_effects()
        self._populate_providers()
        self._apply_settings_to_form(self.settings)
        self._populate_models()
        self._populate_conversations()
        self._restore_last_conversation()
        self._retranslate_ui()
        self._refresh_health_banner()
        self._refresh_update_section()
        self._update_interaction_state()
        self._background_refresh_timer.start(1200)

    def _setup_ui(self) -> None:
        app = QApplication.instance()
        assert app is not None
        app.setStyleSheet(build_stylesheet(self.settings.theme))
        app.setFont(QFont("Segoe UI Variable", 10))

        central = QWidget()
        central.setObjectName("AppRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        self.header_card = QFrame()
        self.header_card.setObjectName("HeaderCard")
        header = QHBoxLayout(self.header_card)
        header.setContentsMargins(22, 18, 22, 18)
        header.setSpacing(18)

        header_copy = QVBoxLayout()
        header_copy.setSpacing(6)
        self.header_title = QLabel()
        self.header_title.setObjectName("HeaderTitle")
        self.header_subtitle = QLabel()
        self.header_subtitle.setWordWrap(True)
        self.header_context_label = QLabel()
        self.header_context_label.setObjectName("MutedLabel")
        self.header_context_label.setWordWrap(True)
        header_copy.addWidget(self.header_title)
        header_copy.addWidget(self.header_subtitle)
        header_copy.addWidget(self.header_context_label)
        header.addLayout(header_copy, 1)

        self.status_chip = PresenceChip()
        self.status_chip.setMinimumWidth(132)
        self.status_chip.setMaximumWidth(188)
        header.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignTop)
        self.header_card.hide()

        self.health_banner = QLabel()
        self.health_banner.setWordWrap(True)
        self.health_banner.hide()

        self.workspace_stack = QStackedWidget()
        root.addWidget(self.workspace_stack, 1)
        self.chat_workspace_widget = ChatWorkspace()
        self.profile_page_widget = ProfilePage()
        self.workspace_stack.addWidget(self.chat_workspace_widget)
        self.workspace_stack.addWidget(self.profile_page_widget)
        self._bind_workspace_widgets()
        self._apply_consumer_mode()

        self.bottom_nav = BottomNav(central)
        self.bottom_nav.chat_requested.connect(lambda: self._set_workspace("chat"))
        self.bottom_nav.profile_requested.connect(lambda: self._set_workspace("profile"))
        self.bottom_nav_card = self.bottom_nav
        self.chat_nav_button = self.bottom_nav.chat_button
        self.profile_nav_button = self.bottom_nav.profile_button
        self.bottom_nav.set_theme(self.settings.theme)
        self._set_workspace("chat")

        self.setCentralWidget(central)
        self.overlay_host = QWidget(central)
        self.overlay_host.setObjectName("OverlayHost")
        self.overlay_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.overlay_host.raise_()
        self.notification_center = NotificationCenter(central, translator=self._notification_label)
        self.notification_center.layout_changed.connect(self._reposition_overlays)
        self.setStatusBar(QStatusBar())
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().hide()
        self.file_menu = self.menuBar().addMenu("")
        self.export_md_action = QAction(self)
        self.export_md_action.triggered.connect(lambda: self._export_current("markdown"))
        self.export_json_action = QAction(self)
        self.export_json_action.triggered.connect(lambda: self._export_current("json"))
        self.file_menu.addAction(self.export_md_action)
        self.file_menu.addAction(self.export_json_action)
        self.menuBar().hide()
        self._sync_overlay_geometry()

    def _apply_consumer_mode(self) -> None:
        self.profile_page_widget.apply_consumer_mode()
        self.chat_source_label.hide()
        self.chat_source_value.hide()
        self.chat_source_combo.hide()
        self.setup_provider_summary.hide()
        self.setup_model_summary.hide()
        self.setup_steps_label.hide()
        self.setup_steps_view.hide()
        self.setup_copy_button.hide()

    def _bind_workspace_widgets(self) -> None:
        self.chat_workspace = self.chat_workspace_widget
        self.sidebar_panel = self.chat_workspace_widget.sidebar_panel
        self.sidebar_header_section = self.chat_workspace_widget.sidebar_header_section
        self.sidebar_title_label = self.chat_workspace_widget.sidebar_title_label
        self.chat_header_card = self.chat_workspace_widget.chat_header_card
        self.chat_header_actions_layout = self.chat_workspace_widget.chat_header_actions_layout
        self.center_shell = self.chat_workspace_widget.center_shell
        self.conversation_list = self.chat_workspace_widget.conversation_list
        self.new_chat_button = self.chat_workspace_widget.new_chat_button
        self.export_md_button = self.chat_workspace_widget.export_md_button
        self.chat_title = self.chat_workspace_widget.chat_title
        self.main_stack = self.chat_workspace_widget.main_stack
        self.chat_page = self.chat_workspace_widget.chat_page
        self.chat_surface = self.chat_workspace_widget.chat_surface
        self.chat_source_label = self.chat_workspace_widget.chat_source_label
        self.chat_source_value = self.chat_workspace_widget.chat_source_value
        self.chat_source_combo = self.chat_workspace_widget.chat_source_combo
        self.chat_view = self.chat_workspace_widget.chat_view
        self.chat_messages_host = self.chat_workspace_widget.chat_messages_host
        self.chat_messages_layout = self.chat_workspace_widget.chat_messages_layout
        self.composer_card = self.chat_workspace_widget.composer_card
        self.composer = self.chat_workspace_widget.composer
        self.send_button = self.chat_workspace_widget.send_button
        self.cancel_button = self.chat_workspace_widget.cancel_button
        self.regenerate_button = self.chat_workspace_widget.regenerate_button
        self.export_json_button = self.chat_workspace_widget.export_json_button
        self.setup_page = self.chat_workspace_widget.setup_page
        self.setup_card = self.chat_workspace_widget.setup_card
        self.setup_title = self.chat_workspace_widget.setup_title
        self.setup_body = self.chat_workspace_widget.setup_body
        self.setup_provider_summary = self.chat_workspace_widget.setup_provider_summary
        self.setup_model_summary = self.chat_workspace_widget.setup_model_summary
        self.setup_steps_label = self.chat_workspace_widget.setup_steps_label
        self.setup_steps_view = self.chat_workspace_widget.setup_steps_view
        self.setup_hint_label = self.chat_workspace_widget.setup_hint_label
        self.setup_refresh_button = self.chat_workspace_widget.setup_refresh_button
        self.setup_profile_button = self.chat_workspace_widget.setup_profile_button
        self.setup_copy_button = self.chat_workspace_widget.setup_copy_button
        self.approval_page = self.chat_workspace_widget.approval_page
        self.approval_card = self.chat_workspace_widget.approval_card
        self.approval_title = self.chat_workspace_widget.approval_title
        self.approval_text = self.chat_workspace_widget.approval_text
        self.approval_kind_label = self.chat_workspace_widget.approval_kind_label
        self.approval_kind_value = self.chat_workspace_widget.approval_kind_value
        self.approval_target_label = self.chat_workspace_widget.approval_target_label
        self.approval_target_value = self.chat_workspace_widget.approval_target_value
        self.approval_risk_label = self.chat_workspace_widget.approval_risk_label
        self.approval_risk_value = self.chat_workspace_widget.approval_risk_value
        self.approval_details_label = self.chat_workspace_widget.approval_details_label
        self.approval_details_value = self.chat_workspace_widget.approval_details_value
        self.approval_payload_label = self.chat_workspace_widget.approval_payload_label
        self.approval_payload_view = self.chat_workspace_widget.approval_payload_view
        self.allow_button = self.chat_workspace_widget.allow_button
        self.deny_button = self.chat_workspace_widget.deny_button

        self.settings_workspace = self.profile_page_widget
        self.settings_panel = self.profile_page_widget.settings_panel
        self.settings_intro_card = self.profile_page_widget.settings_intro_card
        self.profile_icon_label = self.profile_page_widget.profile_icon_label
        self.settings_title_label = self.profile_page_widget.settings_title_label
        self.provider_description_label = self.profile_page_widget.provider_description_label
        self.provider_description_value = self.profile_page_widget.provider_description_value
        self.support_menu_button = self.profile_page_widget.support_menu_button
        self.settings_scroll = self.profile_page_widget.settings_scroll
        self.settings_content = self.profile_page_widget.settings_content
        self.assistant_title_label = self.profile_page_widget.assistant_title_label
        self.default_source_label = self.profile_page_widget.default_source_label
        self.default_source_combo = self.profile_page_widget.default_source_combo
        self.provider_profile_label = self.profile_page_widget.provider_profile_label
        self.provider_combo = self.profile_page_widget.provider_combo
        self.refresh_button = self.profile_page_widget.refresh_button
        self.model_profile_label = self.profile_page_widget.model_profile_label
        self.model_combo = self.profile_page_widget.model_combo
        self.system_prompt_label = self.profile_page_widget.system_prompt_label
        self.system_prompt_input = self.profile_page_widget.system_prompt_input
        self.temperature_label = self.profile_page_widget.temperature_label
        self.temperature_input = self.profile_page_widget.temperature_input
        self.top_p_label = self.profile_page_widget.top_p_label
        self.top_p_input = self.profile_page_widget.top_p_input
        self.max_tokens_label = self.profile_page_widget.max_tokens_label
        self.max_tokens_input = self.profile_page_widget.max_tokens_input
        self.provider_fields_title = self.profile_page_widget.provider_fields_title
        self.provider_form_host = self.profile_page_widget.provider_form_host
        self.provider_form_layout = self.profile_page_widget.provider_form_layout
        self.api_title_label = self.profile_page_widget.api_title_label
        self.api_model_label = self.profile_page_widget.api_model_label
        self.api_model_input = self.profile_page_widget.api_model_input
        self.reasoning_enabled_checkbox = self.profile_page_widget.reasoning_enabled_checkbox
        self.appearance_title_label = self.profile_page_widget.appearance_title_label
        self.language_profile_label = self.profile_page_widget.language_profile_label
        self.language_combo = self.profile_page_widget.language_combo
        self.theme_profile_label = self.profile_page_widget.theme_profile_label
        self.theme_combo = self.profile_page_widget.theme_combo
        self.updates_title_label = self.profile_page_widget.updates_title_label
        self.current_version_label = self.profile_page_widget.current_version_label
        self.current_version_value = self.profile_page_widget.current_version_value
        self.update_status_label = self.profile_page_widget.update_status_label
        self.update_status_value = self.profile_page_widget.update_status_value
        self.latest_version_label = self.profile_page_widget.latest_version_label
        self.latest_version_value = self.profile_page_widget.latest_version_value
        self.open_release_button = self.profile_page_widget.open_release_button
        self.updates_refresh_button = self.profile_page_widget.updates_refresh_button
        self.local_models_title_label = self.profile_page_widget.local_models_title_label
        self.local_model_label = self.profile_page_widget.local_model_label
        self.local_model_combo = self.profile_page_widget.local_model_combo
        self.local_model_status_label = self.profile_page_widget.local_model_status_label
        self.local_model_status_value = self.profile_page_widget.local_model_status_value
        self.install_model_button = self.profile_page_widget.install_model_button
        self.remove_model_button = self.profile_page_widget.remove_model_button
        self.account_title_label = self.profile_page_widget.account_title_label
        self.telegram_status_label = self.profile_page_widget.telegram_status_label
        self.telegram_status_value = self.profile_page_widget.telegram_status_value
        self.telegram_help_label = self.profile_page_widget.telegram_help_label
        self.permissions_title_label = self.profile_page_widget.permissions_title_label
        self.require_confirmation_checkbox = self.profile_page_widget.require_confirmation_checkbox
        self.web_enabled_checkbox = self.profile_page_widget.web_enabled_checkbox
        self.files_enabled_checkbox = self.profile_page_widget.files_enabled_checkbox
        self.commands_enabled_checkbox = self.profile_page_widget.commands_enabled_checkbox
        self.command_allowlist_label = self.profile_page_widget.command_allowlist_label
        self.command_allowlist_input = self.profile_page_widget.command_allowlist_input

        self.chat_header_actions_layout.insertWidget(0, self.status_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self.chat_view.verticalScrollBar().valueChanged.connect(self._handle_chat_scroll)
        self.chat_workspace_widget.chat_composer_geometry_changed.connect(self._handle_chat_composer_geometry_changed)
        self.conversation_delegate = ConversationListDelegate(self._format_conversation_timestamp, self.conversation_list)
        self.conversation_list.setItemDelegate(self.conversation_delegate)

        self.conversation_list.currentItemChanged.connect(self._handle_conversation_selection)
        self.new_chat_button.clicked.connect(self._start_new_chat)
        self.export_md_button.clicked.connect(lambda: self._export_current("markdown"))
        self.send_button.clicked.connect(self._send_message)
        self.cancel_button.clicked.connect(self._cancel_generation)
        self.regenerate_button.clicked.connect(self._regenerate_last)
        self.export_json_button.clicked.connect(lambda: self._export_current("json"))
        self.setup_refresh_button.clicked.connect(self._refresh_runtime_state)
        self.setup_profile_button.clicked.connect(lambda: self._set_workspace("profile"))
        self.setup_copy_button.clicked.connect(self._copy_setup_steps)
        self.allow_button.clicked.connect(self._allow_pending_action)
        self.deny_button.clicked.connect(self._deny_pending_action)
        self.chat_source_combo.currentIndexChanged.connect(self._handle_chat_source_change)
        self.default_source_combo.currentIndexChanged.connect(self._handle_default_source_change)
        self.provider_combo.currentIndexChanged.connect(self._handle_provider_change)
        self.model_combo.currentTextChanged.connect(self._handle_model_change)
        self.language_combo.currentIndexChanged.connect(self._handle_language_change)
        self.theme_combo.currentIndexChanged.connect(self._handle_theme_change)
        self.refresh_button.clicked.connect(self._refresh_runtime_state)
        self.updates_refresh_button.clicked.connect(self._refresh_runtime_state)
        self.open_release_button.clicked.connect(self._open_release_page)
        self.support_menu_button.clicked.connect(self._open_support_menu)
        self.local_model_combo.currentIndexChanged.connect(self._handle_local_model_change)
        self.install_model_button.clicked.connect(self._install_selected_local_model)
        self.remove_model_button.clicked.connect(self._remove_selected_local_model)
        self.system_prompt_input.textChanged.connect(self._persist_settings)
        self.temperature_input.valueChanged.connect(self._persist_settings)
        self.top_p_input.valueChanged.connect(self._persist_settings)
        self.max_tokens_input.valueChanged.connect(self._persist_settings)
        self.require_confirmation_checkbox.stateChanged.connect(self._persist_settings)
        self.web_enabled_checkbox.stateChanged.connect(self._persist_settings)
        self.files_enabled_checkbox.stateChanged.connect(self._persist_settings)
        self.commands_enabled_checkbox.stateChanged.connect(self._persist_settings)
        self.command_allowlist_input.textChanged.connect(self._persist_settings)
        self._configure_generation_controls()

    def _apply_icons(self) -> None:
        style = self.style()
        icon_map = (
            (self.export_md_button, "SP_DialogSaveButton"),
            (self.export_json_button, "SP_DialogSaveButton"),
            (self.send_button, "SP_DialogApplyButton"),
            (self.cancel_button, "SP_DialogCancelButton"),
            (self.regenerate_button, "SP_BrowserReload"),
            (self.refresh_button, "SP_BrowserReload"),
            (self.updates_refresh_button, "SP_BrowserReload"),
            (self.setup_refresh_button, "SP_BrowserReload"),
        )
        for button, pixmap_name in icon_map:
            standard_pixmap = getattr(QStyle.StandardPixmap, pixmap_name, None)
            if standard_pixmap is None:
                continue
            button.setIcon(style.standardIcon(standard_pixmap))

    def _apply_brand_art(self) -> None:
        asset_path = resolve_asset("assets", "branding", "app-icon.png")
        if not asset_path.exists():
            return
        pixmap = QPixmap(str(asset_path))
        if pixmap.isNull():
            return
        size = self.profile_icon_label.width()
        self.profile_icon_label.setPixmap(
            pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _position_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(geometry.center())
        self.move(frame.topLeft())

    def _build_bottom_nav(self, root: QVBoxLayout) -> None:
        self.bottom_nav_card = QFrame()
        self.bottom_nav_card.setObjectName("BottomNavCard")
        self.bottom_nav_card.setMaximumWidth(360)
        nav = QHBoxLayout(self.bottom_nav_card)
        nav.setContentsMargins(14, 12, 14, 12)
        nav.setSpacing(12)
        nav.addStretch(1)
        self.chat_nav_button = QPushButton()
        self.chat_nav_button.setProperty("bottomnav", True)
        self.chat_nav_button.clicked.connect(lambda: self._set_workspace("chat"))
        self.profile_nav_button = QPushButton()
        self.profile_nav_button.setProperty("bottomnav", True)
        self.profile_nav_button.clicked.connect(lambda: self._set_workspace("profile"))
        nav.addWidget(self.chat_nav_button)
        nav.addWidget(self.profile_nav_button)
        nav.addStretch(1)
        root.addWidget(self.bottom_nav_card, 0, Qt.AlignmentFlag.AlignHCenter)

    def _apply_glass_effects(self) -> None:
        for widget, blur_radius, y_offset, alpha in (
            (self.sidebar_panel, 34, 14, 76),
            (self.settings_panel, 34, 14, 76),
            (self.chat_header_card, 24, 8, 34),
            (self.bottom_nav_card, 18, 6, 28),
            (self.chat_surface, 26, 10, 34),
            (self.composer_card, 28, 12, 38),
            (self.setup_card, 32, 14, 46),
            (self.approval_card, 32, 14, 46),
            (self.settings_intro_card, 24, 10, 34),
        ):
            effect = QGraphicsDropShadowEffect(widget)
            effect.setBlurRadius(blur_radius)
            effect.setOffset(0, y_offset)
            effect.setColor(QColor(15, 23, 42, alpha))
            widget.setGraphicsEffect(effect)
        QTimer.singleShot(0, self._sync_overlay_geometry)

    def _sync_overlay_geometry(self) -> None:
        central = self.centralWidget()
        if central is None or not hasattr(self, "overlay_host"):
            return
        self.overlay_host.setGeometry(central.rect())
        self._position_bottom_nav()
        self._position_chat_composer_overlay()
        self.notification_center.set_host_geometry(central.rect())
        self.overlay_host.raise_()
        self._reposition_overlays()
        self.bottom_nav.raise_()

    def _position_bottom_nav(self) -> None:
        central = self.centralWidget()
        if central is None or not hasattr(self, "bottom_nav"):
            return
        self.bottom_nav.adjustSize()
        nav_width = min(self.bottom_nav.sizeHint().width(), max(220, central.width() - 44))
        nav_height = self.bottom_nav.sizeHint().height()
        x = max(24, (central.width() - nav_width) // 2)
        y = max(24, central.height() - nav_height - 22)
        self.bottom_nav.setGeometry(x, y, nav_width, nav_height)
        self.bottom_nav.raise_()

    def _position_chat_composer_overlay(self) -> None:
        central = self.centralWidget()
        if central is None or not hasattr(self, "chat_surface") or not hasattr(self, "chat_workspace_widget"):
            return
        if not self.chat_surface.isVisible():
            return
        surface_origin = self.chat_surface.mapTo(central, QPoint(0, 0))
        surface_bottom = surface_origin.y() + self.chat_surface.height()
        nav_top = self.bottom_nav.geometry().top() if hasattr(self, "bottom_nav") else central.height()
        clearance = compute_chat_composer_bottom_clearance(surface_bottom=surface_bottom, nav_top=nav_top)
        self.chat_workspace_widget.set_chat_composer_bottom_clearance(clearance)

    def _reposition_overlays(self) -> None:
        if not hasattr(self, "notification_center"):
            return
        central = self.centralWidget()
        if central is None:
            return
        self.notification_center.set_host_geometry(central.rect())

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._t("app_title"))
        self.notification_center.retranslate()
        self.header_title.setText(self._t("header_title"))
        self.header_subtitle.setText(self._t("header_subtitle"))
        self.header_context_label.setText(self._header_context_text())
        self.bottom_nav.set_labels(self._t("nav_chat"), self._t("nav_profile"))
        self.sidebar_title_label.setText(self._t("sidebar_conversations"))
        self.chat_source_label.setText(self._t("chat_source"))
        self.chat_source_value.setText(self._t(f"source_{self._current_chat_source()}"))
        self.new_chat_button.setText(f"+ {self._t('button_new_chat')}")
        self.export_md_button.setText(self._t("button_export_md"))
        self.send_button.setText(self._t("button_send"))
        self.cancel_button.setText(self._t("button_cancel"))
        self.regenerate_button.setText(self._t("button_regenerate"))
        self.export_json_button.setText(self._t("button_export_json"))
        self.setup_steps_label.setText(self._t("setup_steps"))
        self.setup_refresh_button.setText(self._t("button_refresh"))
        self.setup_profile_button.setText(self._t("button_open_profile"))
        self.setup_copy_button.setText(self._t("button_copy_steps"))
        self.setup_hint_label.setText(self._t("setup_panel_hint"))
        self.composer.setPlaceholderText(self._t("chat_placeholder"))
        self.approval_kind_label.setText(self._t("approval_kind"))
        self.approval_target_label.setText(self._t("approval_target"))
        self.approval_risk_label.setText(self._t("approval_risk"))
        self.approval_details_label.setText(self._t("approval_details"))
        self.approval_payload_label.setText(self._t("approval_payload"))
        self.allow_button.setText(self._t("button_allow"))
        self.deny_button.setText(self._t("button_deny"))
        self.settings_title_label.setText(self._t("profile_title"))
        self.provider_description_label.setText(self._t("profile_status"))
        self.provider_description_value.setText(self._profile_status_text())
        self.support_menu_button.setText("⚙")
        self.support_menu_button.setToolTip(self._t("button_support_menu"))
        self.assistant_title_label.setText(self._t("profile_assistant"))
        self.default_source_label.setText(self._t("settings_default_source"))
        self.provider_profile_label.setText(self._t("settings_provider"))
        self.model_profile_label.setText(self._t("settings_model"))
        self.refresh_button.setText(self._t("button_refresh"))
        self.local_models_title_label.setText(self._t("settings_local_models"))
        self.local_model_label.setText(self._t("settings_local_model"))
        self.local_model_status_label.setText(self._t("settings_local_model_status"))
        self.remove_model_button.setText(self._t("button_remove_model"))
        self.appearance_title_label.setText(self._t("settings_appearance"))
        self.language_profile_label.setText(self._t("settings_language"))
        self.theme_profile_label.setText(self._t("settings_theme"))
        self.updates_title_label.setText(self._t("settings_updates"))
        self.current_version_label.setText(self._t("updates_current_version"))
        self.update_status_label.setText(self._t("updates_status"))
        self.latest_version_label.setText(self._t("updates_latest_version"))
        self.open_release_button.setText(self._t("button_open_release"))
        self.updates_refresh_button.setText(self._t("button_refresh"))
        self.provider_fields_title.setText(self._t("provider_details"))
        self.account_title_label.setText(self._t("settings_account"))
        self.telegram_status_label.setText(self._t("telegram_status"))
        self.telegram_status_value.setText(self._t("telegram_status_coming_soon"))
        self.telegram_help_label.setText(self._t("telegram_account_hint"))
        self.permissions_title_label.setText(self._t("settings_permissions"))
        self.system_prompt_label.setText(self._t("settings_system_prompt"))
        self.temperature_label.setText(self._t("settings_temperature"))
        self.top_p_label.setText(self._t("settings_top_p"))
        self.max_tokens_label.setText(self._t("settings_max_tokens"))
        self._configure_generation_controls()
        self.require_confirmation_checkbox.setText(self._t("settings_require_confirmation"))
        self.web_enabled_checkbox.setText(self._t("settings_web_enabled"))
        self.files_enabled_checkbox.setText(self._t("settings_files_enabled"))
        self.commands_enabled_checkbox.setText(self._t("settings_commands_enabled"))
        self.command_allowlist_label.setText(self._t("settings_command_allowlist"))
        self.file_menu.setTitle(self._t("file_menu"))
        self.export_md_action.setText(self._t("menu_export_md"))
        self.export_json_action.setText(self._t("menu_export_json"))
        self.profile_page_widget.assistant_card.set_description(self._profile_status_text())
        self.profile_page_widget.provider_card.set_description(self._provider_description(self._selected_provider_id()))
        self.profile_page_widget.local_models_card.set_description(self._t("settings_local_models_hint"))
        self.profile_page_widget.appearance_card.set_description(self._t("header_context_profile"))
        self.profile_page_widget.updates_card.set_description(self._t("updates_card_hint"))
        self.profile_page_widget.account_card.set_description(self._t("telegram_account_hint"))
        self.profile_page_widget.permissions_card.set_description(self._t("approval_body"))
        self._populate_source_choices(self._selected_default_source())
        self._populate_chat_source_choices(self._current_chat_source())
        self._populate_language_choices(self._selected_language())
        self._populate_theme_choices(self._selected_theme())
        self._populate_local_models()
        self._refresh_local_model_status()
        self.provider_description_value.setText(self._profile_status_text())
        self._render_provider_config_fields()
        self._refresh_activity_chip(self._status_mode)
        self._populate_setup_guidance(self.current_health)
        self._refresh_update_section()
        self._update_nav_state()
        self._render_messages(self.service.load_messages(self.current_conversation_id) if self.current_conversation_id else [])
        QTimer.singleShot(0, self._sync_overlay_geometry)

    def _populate_language_choices(self, current: str | None = None) -> None:
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(self._t("language_ru"), "ru")
        self.language_combo.addItem(self._t("language_en"), "en")
        self._set_combo_by_data(self.language_combo, current or self.localization.language)
        self.language_combo.blockSignals(False)

    def _populate_theme_choices(self, current: str | None = None) -> None:
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItem(self._t("theme_light"), "light")
        self.theme_combo.addItem(self._t("theme_dark"), "dark")
        self._set_combo_by_data(self.theme_combo, current or self.settings.theme)
        self.theme_combo.blockSignals(False)

    def _populate_source_choices(self, current: str | None = None) -> None:
        self.default_source_combo.blockSignals(True)
        self.default_source_combo.clear()
        self.default_source_combo.addItem(self._t("source_local"), "local")
        self._set_combo_by_data(self.default_source_combo, current or "local")
        self.default_source_combo.blockSignals(False)

    def _populate_chat_source_choices(self, current: str | None = None) -> None:
        self.chat_source_combo.blockSignals(True)
        self.chat_source_combo.clear()
        self.chat_source_combo.addItem(self._t("source_local"), "local")
        self._set_combo_by_data(self.chat_source_combo, current or "local")
        self.chat_source_combo.blockSignals(False)

    def _populate_providers(self) -> None:
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for descriptor in self._provider_descriptors.values():
            if descriptor.provider_id != "local_llama":
                continue
            self.provider_combo.addItem(descriptor.display_name, descriptor.provider_id)
        self._set_combo_by_data(self.provider_combo, "local_llama")
        self.provider_combo.blockSignals(False)

    def _populate_models(self) -> None:
        models = list(self._cached_provider_models)
        if not models:
            try:
                models = list(self.service.list_models(self._selected_provider_id()))
            except Exception:  # noqa: BLE001
                models = []
            self._cached_provider_models = list(models)
        current = self.settings.model or DEFAULT_MODEL
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        seen: set[str] = set()
        for item in models:
            if not item.model_id or item.model_id in seen:
                continue
            seen.add(item.model_id)
            self.model_combo.addItem(item.display_name or item.model_id, item.model_id)
            index = self.model_combo.count() - 1
            self.model_combo.setItemData(index, item.description, Qt.ItemDataRole.ToolTipRole)
        if current and current not in seen:
            self.model_combo.addItem(current, current)
        self._set_combo_by_data(self.model_combo, current)
        if self.model_combo.currentIndex() < 0 and current:
            self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)

    def _populate_local_models(self) -> None:
        models = list(self._cached_local_models)
        if not models:
            models = self.service.list_local_models()
            self._cached_local_models = list(models)
        current = self.settings.model or DEFAULT_MODEL
        self.local_model_combo.blockSignals(True)
        self.local_model_combo.clear()
        for item in models:
            label = item.display_name
            meta_parts = []
            if item.size_hint:
                meta_parts.append(item.size_hint)
            if item.description:
                meta_parts.append(item.description)
            if meta_parts:
                label = f"{label} · {' · '.join(meta_parts)}"
            self.local_model_combo.addItem(label, item.model_id)
            index = self.local_model_combo.count() - 1
            tooltip_parts = [item.display_name]
            if item.description:
                tooltip_parts.append(item.description)
            if item.size_hint:
                tooltip_parts.append(f"Size: {item.size_hint}")
            if item.quantization:
                tooltip_parts.append(f"Quant: {item.quantization}")
            if item.recommended_ram_gb:
                tooltip_parts.append(f"RAM: {item.recommended_ram_gb} GB+")
            self.local_model_combo.setItemData(index, "\n".join(tooltip_parts), Qt.ItemDataRole.ToolTipRole)
        if current:
            self._set_combo_by_data(self.local_model_combo, current)
        self.local_model_combo.blockSignals(False)

    def _apply_settings_to_form(self, settings: AppSettings) -> None:
        self._updating_form = True
        try:
            self.settings = settings
            self.state.settings = settings
            self._apply_theme(settings.theme)
            self._populate_source_choices(settings.default_source)
            self._set_combo_by_data(self.default_source_combo, settings.default_source)
            self._set_combo_by_data(self.provider_combo, settings.provider_id)
            self._populate_chat_source_choices(self._current_chat_source())
            self._populate_language_choices(settings.language)
            self._set_combo_by_data(self.language_combo, settings.language)
            self._populate_theme_choices(settings.theme)
            self._set_combo_by_data(self.theme_combo, settings.theme)
            self.model_combo.setCurrentText(settings.model)
            self.api_model_input.setText(settings.api_model or DEFAULT_MODEL)
            self._populate_local_models()
            self._set_combo_by_data(self.local_model_combo, settings.model)
            self.reasoning_enabled_checkbox.setChecked(settings.reasoning_enabled)
            self.system_prompt_input.setPlainText(settings.system_prompt)
            self.temperature_input.setValue(DEFAULT_TEMPERATURE)
            self.top_p_input.setValue(DEFAULT_TOP_P)
            self.max_tokens_input.setValue(DEFAULT_MAX_TOKENS)
            self.require_confirmation_checkbox.setChecked(settings.require_confirmation)
            self.web_enabled_checkbox.setChecked(settings.web_enabled)
            self.files_enabled_checkbox.setChecked(settings.files_enabled)
            self.commands_enabled_checkbox.setChecked(settings.commands_enabled)
            self.command_allowlist_input.setText(", ".join(settings.command_allowlist))
            self.provider_description_value.setText(self._profile_status_text())
            self._render_provider_config_fields()
            self._configure_generation_controls()
            self._refresh_local_model_status()
            self.default_source_label.hide()
            self.default_source_combo.hide()
            self.chat_source_combo.hide()
            self.provider_combo.setEnabled(False)
        finally:
            self._updating_form = False

    def _render_provider_config_fields(self) -> None:
        while self.provider_form_layout.rowCount():
            self.provider_form_layout.removeRow(0)
        self.provider_config_inputs.clear()
        self.provider_secret_status_labels.clear()
        self._rendered_provider_id = None

    def _populate_conversations(self) -> None:
        selected = self.current_conversation_id
        self._conversation_items.clear()
        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()
        for conversation in self.service.load_conversations():
            title = " ".join(conversation.title.split())
            item = QListWidgetItem(title)
            item.setData(CONVERSATION_ID_ROLE, conversation.conversation_id)
            item.setData(CONVERSATION_TITLE_ROLE, title)
            item.setData(CONVERSATION_TIMESTAMP_ROLE, conversation.updated_at.isoformat())
            item.setSizeHint(QSize(0, 44))
            item.setToolTip(f"{title}\n{conversation.updated_at.astimezone():%d.%m.%Y %H:%M}")
            self.conversation_list.addItem(item)
            self._conversation_items[conversation.conversation_id] = item
        self.conversation_list.blockSignals(False)
        if selected and selected in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[selected])

    def _format_conversation_timestamp(self, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return ""
        local_timestamp = timestamp.astimezone()
        now = datetime.now().astimezone()
        return local_timestamp.strftime("%H:%M") if local_timestamp.date() == now.date() else local_timestamp.strftime("%d.%m")

    def _refresh_secret_status(self) -> None:
        return

    def _refresh_local_model_status(self) -> None:
        selected = self._selected_local_model_id()
        installed = self._cached_installed_models.get(selected) if selected else None
        descriptor = next((item for item in self._cached_local_models if item.model_id == selected), None)
        description = descriptor.description if descriptor else ""
        downloading = self.model_download_worker is not None
        runtime_available = self._runtime_binary_available
        runtime_ready = self.current_health.status == "ready" and bool(selected) and self.settings.model == selected
        if installed is None:
            text = self._t("local_model_status_missing")
            if description:
                text = f"{text}\n{description}"
            self.local_model_status_value.setText(text)
            self.install_model_button.setText(self._t("button_downloading_model") if downloading else self._t("button_install_model"))
            self.install_model_button.setEnabled(not downloading)
            self.remove_model_button.setEnabled(False)
            return
        if runtime_ready:
            text = self._t("local_model_status_ready")
        elif self.runtime_refresh_worker is not None and runtime_available:
            text = self._t("local_model_status_starting")
        elif runtime_available:
            text = self._t("local_model_status_runtime_preparing")
        else:
            text = self._t("local_model_status_installed_runtime_missing")
        if description:
            text = f"{text}\n{description}"
        self.local_model_status_value.setText(text)
        self.install_model_button.setText(self._t("button_open_chat"))
        self.install_model_button.setEnabled(not downloading)
        self.remove_model_button.setEnabled(not downloading)

    def _install_selected_local_model(self) -> None:
        model_id = self._selected_local_model_id()
        if model_id and self.service.get_installed_local_model(model_id) is not None:
            self._open_selected_local_model_chat()
            return
        if self.model_download_worker is not None:
            self._notify(self._t("local_model_download_in_progress"), variant="info")
            return
        if not model_id:
            return
        self.model_download_thread = QThread(self)
        self.model_download_worker = ModelDownloadWorker(self.service, model_id)
        self.model_download_worker.moveToThread(self.model_download_thread)
        self.model_download_thread.started.connect(self.model_download_worker.run)
        self.model_download_worker.progress.connect(self._handle_model_download_progress)
        self.model_download_worker.completed.connect(self._handle_model_download_completed)
        self.model_download_worker.failed.connect(self._handle_model_download_failed)
        self.model_download_worker.finished.connect(self._model_download_cleanup)
        self.model_download_worker.finished.connect(self.model_download_thread.quit)
        self.model_download_worker.finished.connect(self.model_download_worker.deleteLater)
        self.model_download_thread.finished.connect(self.model_download_thread.deleteLater)
        self.model_download_thread.start()
        self._show_event(
            event_id=self._model_download_event_id(model_id),
            title=self._t("local_model_download_in_progress"),
            message=model_id,
            variant="info",
        )
        self._refresh_local_model_status()

    def _open_selected_local_model_chat(self) -> None:
        self._set_workspace("chat")
        self._refresh_health_banner()
        if self.current_health.status == "ready":
            self.composer.setFocus()
            return
        self._notify(self._t("status_setup_required"), variant="warning")

    def _remove_selected_local_model(self) -> None:
        model_id = self._selected_local_model_id()
        if not model_id or self.model_download_worker is not None:
            return
        try:
            self.service.remove_local_model(model_id)
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_generation"), exc)
            return
        self._notify(self._t("local_model_removed"), variant="warning")
        self._cached_installed_models = {item.model_id: item for item in self.service.list_installed_local_models()}
        self._health_snapshot_valid = False
        self._refresh_local_model_status()
        self._refresh_health_banner()

    def _handle_model_download_progress(self, progress: object) -> None:
        if not isinstance(progress, ModelDownloadProgress):
            return
        percent = None
        if progress.total_bytes > 0:
            percent = int((progress.downloaded_bytes / progress.total_bytes) * 100)
        self._show_event(
            event_id=self._model_download_event_id(progress.model_id),
            title=progress.display_name,
            message=progress.message,
            variant="info",
            progress=percent,
        )
        self._refresh_local_model_status()

    def _handle_model_download_completed(self, installed_model: object) -> None:
        installed_model_id = getattr(installed_model, "model_id", "")
        selected_model_id = self._selected_local_model_id() or installed_model_id
        self._finish_event(
            event_id=self._model_download_event_id(selected_model_id),
            title=self._t("local_model_ready"),
            variant="success",
            progress=100,
            timeout_ms=3200,
        )
        self._populate_models()
        self._populate_local_models()
        self._cached_installed_models = {item.model_id: item for item in self.service.list_installed_local_models()}
        self._health_snapshot_valid = False
        if installed_model_id:
            self._updating_form = True
            try:
                self._set_combo_by_data(self.local_model_combo, installed_model_id)
                self._set_combo_by_data(self.model_combo, installed_model_id)
                self.settings.model = installed_model_id
                self.state.settings.model = installed_model_id
            finally:
                self._updating_form = False
            self.service.save_settings(self._collect_settings_from_form())
            self.settings = self.service.load_settings()
            self.state.settings = self.settings
        self._refresh_local_model_status()
        self._refresh_health_banner()
        self._start_runtime_refresh(manual=False, notify_runtime=True)

    def _handle_model_download_failed(self, error: str) -> None:
        selected_model_id = self._selected_local_model_id() or "active"
        self._finish_event(
            event_id=self._model_download_event_id(selected_model_id),
            title=self._t("local_model_download_failed"),
            message=error,
            variant="error",
            timeout_ms=0,
        )
        self._refresh_local_model_status()

    def _model_download_cleanup(self) -> None:
        self.model_download_worker = None
        self.model_download_thread = None
        self._update_interaction_state()

    def _restore_last_conversation(self) -> None:
        if self.settings.last_conversation_id and self.settings.last_conversation_id in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[self.settings.last_conversation_id])
        elif self.conversation_list.count():
            self.conversation_list.setCurrentRow(0)
        else:
            self.chat_title.setText(self._t("chat_title_new"))
            self._render_messages([])

    def _handle_provider_change(self) -> None:
        return

    def _handle_model_change(self) -> None:
        if self._updating_form:
            return
        self._persist_settings()
        self._health_snapshot_valid = False
        self._refresh_local_model_status()
        self._refresh_health_banner()

    def _handle_local_model_change(self) -> None:
        if self._updating_form:
            return
        selected = self._selected_local_model_id()
        if selected:
            self.model_combo.blockSignals(True)
            self._set_combo_by_data(self.model_combo, selected)
            self.model_combo.blockSignals(False)
        self._persist_settings()
        self._health_snapshot_valid = False
        self._refresh_local_model_status()
        self._refresh_health_banner()

    def _handle_language_change(self) -> None:
        if self._updating_form:
            return
        self.localization.set_language(self._selected_language())
        self._persist_settings()
        self._retranslate_ui()
        self._refresh_health_banner()

    def _handle_theme_change(self) -> None:
        if self._updating_form:
            return
        sender = self.sender()
        if isinstance(sender, QComboBox) and sender.currentData() in {"light", "dark"}:
            theme = sender.currentData()
        else:
            theme = self._selected_theme()
        self._apply_theme(theme)
        self._populate_theme_choices(theme)
        self._persist_settings()
        self._update_nav_state()
        self._render_messages(self.service.load_messages(self.current_conversation_id) if self.current_conversation_id else [])

    def _handle_default_source_change(self) -> None:
        return

    def _handle_chat_source_change(self) -> None:
        return

    def _handle_conversation_selection(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        self._set_workspace("chat")
        if current is None:
            self.current_conversation_id = None
            self._draft_chat_source = self.settings.default_source
            self._populate_chat_source_choices(self._current_chat_source())
            self._sync_chat_source_ui()
            self.chat_title.setText(self._t("chat_title_new"))
            self._render_messages([])
            self.settings = self.service.set_last_conversation(None)
            self.state.settings = self.settings
            self._update_interaction_state()
            return
        self.current_conversation_id = current.data(CONVERSATION_ID_ROLE)
        self.settings = self.service.set_last_conversation(self.current_conversation_id)
        self.state.settings = self.settings
        self._populate_chat_source_choices(self._current_chat_source())
        self._sync_chat_source_ui()
        self.chat_title.setText(current.text().splitlines()[0])
        self._render_messages(self.service.load_messages(self.current_conversation_id))
        self._update_interaction_state()

    def _start_new_chat(self) -> None:
        if self._is_locked():
            self._show_warning(self._t("warning_in_progress"), self._t("warning_finish_current_first"))
            return
        self._set_workspace("chat")
        self.conversation_list.clearSelection()
        self.current_conversation_id = None
        self._draft_chat_source = self.settings.default_source
        self._populate_chat_source_choices(self._current_chat_source())
        self._sync_chat_source_ui()
        self.chat_title.setText(self._t("chat_title_new"))
        self._render_messages([])
        self.composer.setFocus()
        self._persist_settings()

    def _send_message(self) -> None:
        if self._is_locked():
            self._show_warning(self._t("warning_in_progress"), self._t("warning_finish_current_first"))
            return
        self._set_workspace("chat")
        if self.current_health.status != "ready":
            self._refresh_health_banner()
            self._notify(self._t("status_setup_required"), variant="warning")
            return
        text = self.composer.toPlainText().strip()
        if not text:
            return
        self._persist_settings()
        try:
            prepared = self.service.prepare_user_generation(
                self.current_conversation_id,
                text,
                source_override=self._current_chat_source(),
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_send"), exc)
            return
        self.composer.clear()
        self.current_conversation_id = prepared.conversation.conversation_id
        self.current_assistant_message_id = prepared.assistant_message.message_id
        self._has_received_generation_chunk = False
        self._populate_conversations()
        if self.current_conversation_id in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[self.current_conversation_id])
        self._render_messages(self.service.load_messages(prepared.conversation.conversation_id))
        self._start_generation(prepared)

    def _regenerate_last(self) -> None:
        if self._is_locked():
            self._show_warning(self._t("warning_in_progress"), self._t("warning_finish_current_first"))
            return
        if self.current_conversation_id is None:
            self._show_warning(self._t("warning_no_conversation"), self._t("warning_no_conversation"))
            return
        self._persist_settings()
        prepared = self.service.regenerate_last_response(self.current_conversation_id)
        if prepared is None:
            self._show_warning(self._t("warning_no_regen"), self._t("warning_no_regen"))
            return
        self.current_assistant_message_id = prepared.assistant_message.message_id
        self._has_received_generation_chunk = False
        self._render_messages(self.service.load_messages(prepared.conversation.conversation_id))
        self._start_generation(prepared)

    def _start_generation(self, prepared: PreparedGeneration) -> None:
        try:
            provider = self.service.providers.get(prepared.request.provider_id)
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_generation"), exc)
            return
        self._typing_indicator_message_id = prepared.assistant_message.message_id
        self._typing_indicator_phase = 0
        self._typing_indicator_timer.start()
        self._refresh_activity_chip("busy")
        self.generation_thread = QThread(self)
        self.generation_worker = GenerationWorker(provider, prepared.request)
        self.generation_worker.moveToThread(self.generation_thread)
        self.generation_thread.started.connect(self.generation_worker.run)
        self.generation_worker.chunk_received.connect(self._handle_generation_chunk)
        self.generation_worker.metadata_received.connect(self._handle_generation_metadata)
        self.generation_worker.completed.connect(self._handle_generation_completed)
        self.generation_worker.failed.connect(self._handle_generation_failed)
        self.generation_worker.finished.connect(self._generation_cleanup)
        self.generation_worker.finished.connect(self.generation_thread.quit)
        self.generation_worker.finished.connect(self.generation_worker.deleteLater)
        self.generation_thread.finished.connect(self.generation_thread.deleteLater)
        self.generation_thread.start()
        self._update_interaction_state()

    def _handle_generation_chunk(self, chunk: str) -> None:
        if self.current_assistant_message_id is None:
            return
        self._has_received_generation_chunk = True
        self._stop_typing_indicator()
        self.service.append_to_message(self.current_assistant_message_id, chunk)
        if self.current_conversation_id:
            self._render_messages(self.service.load_messages(self.current_conversation_id))

    def _handle_generation_metadata(self, metadata: object) -> None:
        if self.current_assistant_message_id is None or not isinstance(metadata, dict) or not metadata:
            return
        self.service.update_message_metadata(self.current_assistant_message_id, metadata)

    def _handle_generation_completed(self) -> None:
        if self.current_assistant_message_id is None:
            return
        self._stop_typing_indicator()
        self.service.finalize_message(self.current_assistant_message_id)
        action = self.service.parse_action_request(self.current_assistant_message_id)
        if self.current_conversation_id:
            self._render_messages(self.service.load_messages(self.current_conversation_id))
        self._populate_conversations()
        if action is not None and action.action_id is not None:
            approved = self._show_approval_sheet(action)
            if approved:
                self.pending_action_id = action.action_id
                self._start_action_execution(self.service.mark_action_approved(action.action_id))
            else:
                self._notify(self._t("status_action_denied"), variant="warning")
                self._continue_after_action(self.service.mark_action_denied(action.action_id))
        else:
            self._notify(self._t("status_response_completed"), variant="success")
            self._refresh_activity_chip("ready")

    def _handle_generation_failed(self, error: str, cancelled: bool) -> None:
        self._stop_typing_indicator()
        if self.current_assistant_message_id is not None:
            self.service.fail_message(self.current_assistant_message_id, error, cancelled=cancelled)
            if self.current_conversation_id:
                self._render_messages(self.service.load_messages(self.current_conversation_id))
        if cancelled:
            self._notify(self._t("status_generation_cancelled"), variant="warning")
        else:
            self._show_error(self._t("error_generation"), ProviderError(error))
        self._refresh_activity_chip("ready")

    def _generation_cleanup(self) -> None:
        self._stop_typing_indicator()
        self.generation_worker = None
        self.generation_thread = None
        self.current_assistant_message_id = None
        self._has_received_generation_chunk = False
        self._update_interaction_state()
        if self.pending_action_id is None and self.action_worker is None:
            self._refresh_health_banner()

    def _cancel_generation(self) -> None:
        if self.generation_worker is not None:
            self.generation_worker.cancel()
            self._notify(self._t("status_cancelling"), variant="info")

    def _show_approval_page(self, action: AssistantAction) -> None:
        self.pending_action_id = action.action_id
        self.approval_title.setText(self._t("approval_title"))
        self.approval_text.setText(action.description or self._t("approval_body"))
        self.approval_kind_value.setText(self._localized_action_kind(action.kind))
        self.approval_target_value.setText(action.target)
        self.approval_risk_value.setText(self._localized_risk(action.risk))
        self.approval_details_value.setText(action.description or action.title)
        self.approval_payload_view.setPlainText(json.dumps(action.payload, indent=2, ensure_ascii=False))
        self._update_interaction_state()

    def _allow_pending_action(self) -> None:
        if self.pending_action_id is None or self.action_worker is not None:
            return
        action = self.service.get_action(self.pending_action_id)
        if action is None:
            return
        self._start_action_execution(self.service.mark_action_approved(action.action_id or ""))

    def _deny_pending_action(self) -> None:
        if self.pending_action_id is None or self.action_worker is not None:
            return
        self._notify(self._t("status_action_denied"), variant="warning")
        self._continue_after_action(self.service.mark_action_denied(self.pending_action_id))

    def _start_action_execution(self, action: AssistantAction) -> None:
        self._refresh_activity_chip("executing")
        self.action_thread = QThread(self)
        self.action_worker = ActionWorker(self.executor, action, self.settings)
        self.action_worker.moveToThread(self.action_thread)
        self.action_thread.started.connect(self.action_worker.run)
        self.action_worker.completed.connect(self._handle_action_completed)
        self.action_worker.failed.connect(self._handle_action_failed)
        self.action_worker.finished.connect(self._action_cleanup)
        self.action_worker.finished.connect(self.action_thread.quit)
        self.action_worker.finished.connect(self.action_worker.deleteLater)
        self.action_thread.finished.connect(self.action_thread.deleteLater)
        self.action_thread.start()
        self._update_interaction_state()

    def _handle_action_completed(self, result_text: str) -> None:
        if self.pending_action_id is not None:
            self._notify(self._t("status_action_completed"), variant="success")
            self._continue_after_action(self.service.mark_action_executed(self.pending_action_id, result_text))

    def _handle_action_failed(self, error: str) -> None:
        if self.pending_action_id is not None:
            self._notify(self._t("status_action_failed"), error, variant="error", timeout_ms=5200)
            self._continue_after_action(self.service.mark_action_failed(self.pending_action_id, error))

    def _continue_after_action(self, action: AssistantAction) -> None:
        self.pending_action_id = None
        self._update_interaction_state()
        try:
            prepared = self.service.build_action_follow_up(action)
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_action"), exc)
            return
        self.current_conversation_id = prepared.conversation.conversation_id
        self.current_assistant_message_id = prepared.assistant_message.message_id
        self._populate_conversations()
        if self.current_conversation_id in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[self.current_conversation_id])
        self._render_messages(self.service.load_messages(prepared.conversation.conversation_id))
        self._start_generation(prepared)

    def _action_cleanup(self) -> None:
        self.action_worker = None
        self.action_thread = None
        self._update_interaction_state()

    def _persist_settings(self) -> None:
        if self._updating_form or self._is_closing:
            return
        try:
            self.settings = self._collect_settings_from_form()
            self.state.settings = self.settings
            self.service.save_settings(self.settings)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Unable to persist settings")
            self._show_error(self._t("settings_title"), exc)

    def _collect_settings_from_form(self) -> AppSettings:
        provider_configs = {"local_llama": dict(self.settings.provider_configs.get("local_llama", {}))}
        allowlist = [item.strip() for item in self.command_allowlist_input.text().replace("\n", ",").split(",") if item.strip()]
        selected_model = self._selected_local_model_id() or self._selected_model_id() or DEFAULT_MODEL
        return AppSettings(
            provider_id="local_llama",
            model=selected_model,
            system_prompt=self.system_prompt_input.toPlainText().strip(),
            default_source="local",
            api_model="",
            reasoning_enabled=False,
            language=self._selected_language(),
            theme=self._selected_theme(),
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_tokens=DEFAULT_MAX_TOKENS,
            last_conversation_id=self.current_conversation_id,
            provider_configs=provider_configs,
            web_enabled=self.web_enabled_checkbox.isChecked(),
            files_enabled=self.files_enabled_checkbox.isChecked(),
            commands_enabled=self.commands_enabled_checkbox.isChecked(),
            require_confirmation=self.require_confirmation_checkbox.isChecked(),
            command_allowlist=allowlist,
        )

    def _refresh_runtime_state(self) -> None:
        self._start_runtime_refresh(manual=True, notify_runtime=True)

    def _schedule_background_runtime_refresh(self) -> None:
        if self.runtime_refresh_worker is None:
            self._start_runtime_refresh(manual=False)

    def _start_runtime_refresh(self, manual: bool, notify_runtime: bool = False) -> None:
        if self.runtime_refresh_worker is not None:
            return
        self._persist_settings()
        self.runtime_status.last_check_status = "checking"
        self.runtime_status.last_check_error = ""
        self._refresh_update_section()
        if notify_runtime:
            self._show_event(
                event_id=self.RUNTIME_EVENT_ID,
                title=self._t("runtime_event_starting_title"),
                message=self._t("runtime_event_starting_body", model=self._model_display_name(self.settings.model or DEFAULT_MODEL)),
                variant="info",
            )
        self.runtime_refresh_thread = QThread(self)
        self.runtime_refresh_worker = RuntimeRefreshWorker(self.service)
        self.runtime_refresh_worker.moveToThread(self.runtime_refresh_thread)
        self.runtime_refresh_thread.started.connect(self.runtime_refresh_worker.run)
        self.runtime_refresh_worker.completed.connect(self._handle_runtime_refresh_completed)
        self.runtime_refresh_worker.failed.connect(self._handle_runtime_refresh_failed)
        self.runtime_refresh_worker.finished.connect(self._runtime_refresh_cleanup)
        self.runtime_refresh_worker.finished.connect(self.runtime_refresh_thread.quit)
        self.runtime_refresh_worker.finished.connect(self.runtime_refresh_worker.deleteLater)
        self.runtime_refresh_thread.finished.connect(self.runtime_refresh_thread.deleteLater)
        self.runtime_refresh_thread.start()
        self._update_interaction_state()

    def _handle_runtime_refresh_completed(self, result: object) -> None:
        if not isinstance(result, RuntimeRefreshResult):
            return
        self.runtime_status = result.status
        self._cached_provider_models = list(result.provider_models or [])
        self._cached_local_models = list(result.local_models or [])
        self._cached_installed_models = {item.model_id: item for item in (result.installed_local_models or [])}
        self._runtime_binary_available = result.runtime_binary_available
        self._health_snapshot_valid = True
        self._populate_models()
        self._populate_local_models()
        self._refresh_local_model_status()
        self._apply_health(result.provider_health or ProviderHealth(status=result.local_status, detail=result.local_detail, models=[]))
        self._refresh_update_section()
        if result.update_available:
            self._notify(self._t("toast_update_available"), variant="success")
        if result.runtime_ready:
            self._finish_event(
                event_id=self.RUNTIME_EVENT_ID,
                title=self._t("runtime_event_ready_title"),
                message=self._t("runtime_event_ready_body"),
                variant="success",
                timeout_ms=3200,
            )
        elif result.local_status == "missing_runtime":
            self._finish_event(
                event_id=self.RUNTIME_EVENT_ID,
                title=self._t("runtime_event_missing_title"),
                message=self._t("runtime_event_missing_body"),
                variant="error",
                timeout_ms=0,
            )
        elif result.local_detail:
            self._finish_event(
                event_id=self.RUNTIME_EVENT_ID,
                title=self._t("runtime_event_failed_title"),
                message=self._consumer_health_detail(ProviderHealth(status=result.local_status, detail=result.local_detail, models=[])),
                variant="warning",
                timeout_ms=0,
            )
        self._maybe_prompt_installer_handoff(result)

    def _handle_runtime_refresh_failed(self, error: str) -> None:
        self.runtime_status.last_check_status = "error"
        self.runtime_status.last_check_error = error
        self._refresh_update_section()
        self._finish_event(
            event_id=self.RUNTIME_EVENT_ID,
            title=self._t("runtime_event_failed_title"),
            message=error,
            variant="error",
            timeout_ms=0,
        )

    def _runtime_refresh_cleanup(self) -> None:
        self.runtime_refresh_worker = None
        self.runtime_refresh_thread = None
        self._update_interaction_state()

    def _maybe_prompt_installer_handoff(self, result: RuntimeRefreshResult) -> None:
        local_installer_available = self.service.update_service.find_local_installer() is not None
        if result.update_available and result.update_kind == "patch" and result.patch_available:
            if self._is_locked() or self.model_download_worker is not None:
                return
            prompt_token = f"patch:{self.runtime_status.latest_version}"
            if self._installer_prompt_token == prompt_token:
                return
            self._installer_prompt_token = prompt_token
            self._start_patch_handoff()
            return
        if result.repair_required and (result.installer_available or local_installer_available):
            prompt_token = f"repair:{result.repair_reason.strip().lower()}"
            if self._installer_prompt_token == prompt_token:
                return
            self._installer_prompt_token = prompt_token
            dialog = SheetDialog(
                self,
                title=self._t("installer_repair_title"),
                body=self._t("installer_repair_body"),
                confirm_text=self._t("button_repair_now"),
                cancel_text=self._t("button_later"),
                danger=False,
            )
            if dialog.exec() == int(dialog.DialogCode.Accepted):
                self._start_installer_handoff(prefer_latest=False)
            return
        if result.update_available and result.installer_available:
            prompt_token = f"update:{self.runtime_status.latest_version}"
            if self._installer_prompt_token == prompt_token:
                return
            self._installer_prompt_token = prompt_token
            dialog = SheetDialog(
                self,
                title=self._t("installer_update_title"),
                body=self._t("installer_update_body", version=self.runtime_status.latest_version or APP_VERSION),
                confirm_text=self._t("button_install_update"),
                cancel_text=self._t("button_later"),
                danger=False,
            )
            if dialog.exec() == int(dialog.DialogCode.Accepted):
                self._start_installer_handoff(prefer_latest=True)

    def _start_patch_handoff(self) -> None:
        if self.installer_worker is not None:
            self._notify(self._t("patch_status_preparing"), variant="info")
            return
        self._show_event(
            event_id=self.PATCH_EVENT_ID,
            title=self._t("patch_status_preparing"),
            message=self._t("patch_status_preparing_body"),
            variant="info",
        )
        self.installer_thread = QThread(self)
        self.installer_worker = InstallerWorker(self.service, mode="patch")
        self.installer_worker.moveToThread(self.installer_thread)
        self.installer_thread.started.connect(self.installer_worker.run)
        self.installer_worker.completed.connect(self._handle_patch_prepared)
        self.installer_worker.failed.connect(self._handle_patch_failed)
        self.installer_worker.finished.connect(self._installer_cleanup)
        self.installer_worker.finished.connect(self.installer_thread.quit)
        self.installer_worker.finished.connect(self.installer_worker.deleteLater)
        self.installer_thread.finished.connect(self.installer_thread.deleteLater)
        self.installer_thread.start()

    def _start_installer_handoff(self, *, prefer_latest: bool) -> None:
        if self.installer_worker is not None:
            self._notify(self._t("installer_status_preparing"), variant="info")
            return
        self._show_event(
            event_id=self.INSTALLER_EVENT_ID,
            title=self._t("installer_status_preparing"),
            message=self._t("installer_status_preparing_body"),
            variant="info",
        )
        self.installer_thread = QThread(self)
        self.installer_worker = InstallerWorker(self.service, prefer_latest=prefer_latest)
        self.installer_worker.moveToThread(self.installer_thread)
        self.installer_thread.started.connect(self.installer_worker.run)
        self.installer_worker.completed.connect(self._handle_installer_prepared)
        self.installer_worker.failed.connect(self._handle_installer_failed)
        self.installer_worker.finished.connect(self._installer_cleanup)
        self.installer_worker.finished.connect(self.installer_thread.quit)
        self.installer_worker.finished.connect(self.installer_worker.deleteLater)
        self.installer_thread.finished.connect(self.installer_thread.deleteLater)
        self.installer_thread.start()

    def _handle_patch_prepared(self, plan: object) -> None:
        patch_path = getattr(plan, "patch_path", None)
        if patch_path is None:
            self._handle_patch_failed(self._t("patch_status_error"))
            return
        try:
            self._show_event(
                event_id=self.PATCH_EVENT_ID,
                title=self._t("patch_status_launching"),
                message=self._t("patch_status_launching_body"),
                variant="info",
            )
            self.service.launch_patch_update(Path(str(patch_path)), current_pid=os.getpid())
        except Exception as exc:  # noqa: BLE001
            self._handle_patch_failed(str(exc))
            return
        self._finish_event(
            event_id=self.PATCH_EVENT_ID,
            title=self._t("patch_status_ready"),
            message=self._t("patch_status_ready_body"),
            variant="success",
            timeout_ms=1800,
        )
        QTimer.singleShot(200, self.close)

    def _handle_installer_prepared(self, plan: object) -> None:
        installer_path = getattr(plan, "installer_path", None)
        if installer_path is None:
            self._handle_installer_failed(self._t("installer_status_error"))
            return
        try:
            self._show_event(
                event_id=self.INSTALLER_EVENT_ID,
                title=self._t("installer_status_launching"),
                message=self._t("installer_status_launching_body"),
                variant="info",
            )
            self.service.launch_installer(Path(str(installer_path)))
        except Exception as exc:  # noqa: BLE001
            self._handle_installer_failed(str(exc))
            return
        self._finish_event(
            event_id=self.INSTALLER_EVENT_ID,
            title=self._t("installer_status_ready"),
            message=self._t("installer_status_ready_body"),
            variant="success",
            timeout_ms=1800,
        )
        QTimer.singleShot(200, self.close)

    def _handle_patch_failed(self, error: str) -> None:
        normalized_error = self._normalize_update_error(error)
        self._finish_event(
            event_id=self.PATCH_EVENT_ID,
            title=self._t("patch_status_error"),
            message=normalized_error,
            variant="error",
            timeout_ms=0,
        )
        self._notify(self._t("patch_status_error"), normalized_error, variant="error", timeout_ms=5200)

    def _handle_installer_failed(self, error: str) -> None:
        normalized_error = self._normalize_update_error(error)
        self._finish_event(
            event_id=self.INSTALLER_EVENT_ID,
            title=self._t("installer_status_error"),
            message=normalized_error,
            variant="error",
            timeout_ms=0,
        )
        self._notify(self._t("installer_status_error"), normalized_error, variant="error", timeout_ms=5200)

    def _normalize_update_error(self, error: str) -> str:
        normalized = error.strip().lower()
        if "trusted release manifest is not available" in normalized or "release manifest is missing or invalid" in normalized:
            return self._t("update_error_manifest_unavailable")
        if "checksum mismatch" in normalized:
            return self._t("update_error_checksum_mismatch")
        if "signature is invalid" in normalized:
            return self._t("update_error_signature_invalid")
        return error

    def _installer_cleanup(self) -> None:
        self.installer_worker = None
        self.installer_thread = None

    def _refresh_update_section(self) -> None:
        self.current_version_value.setText(APP_VERSION)
        self.update_status_value.setText(self._runtime_status_text())
        self.latest_version_value.setText(self.runtime_status.latest_version or self._t("updates_latest_unknown"))
        self.open_release_button.setEnabled(bool(self.runtime_status.release_url))

    def _runtime_status_text(self) -> str:
        if self.runtime_status.repair_required:
            status_text = self._t("updates_status_repair_required")
            if self.runtime_status.repair_reason:
                return f"{status_text}\n{self.runtime_status.repair_reason}"
            return status_text
        status_key = {
            "idle": "updates_status_idle",
            "checking": "updates_status_checking",
            "ok": "updates_status_ok",
            "update_available": "updates_status_available",
            "error": "updates_status_error",
        }.get(self.runtime_status.last_check_status, "updates_status_idle")
        status_text = self._t(status_key)
        if self.runtime_status.last_check_error:
            return f"{status_text}\n{self.runtime_status.last_check_error}"
        return status_text

    def _open_release_page(self) -> None:
        if not self.runtime_status.release_url:
            return
        QDesktopServices.openUrl(QUrl(self.runtime_status.release_url))

    def _open_support_menu(self) -> None:
        menu = QMenu(self)
        developer_action = menu.addAction(self._t("support_developer"))
        github_action = menu.addAction(self._t("support_github"))
        selected = menu.exec(self.support_menu_button.mapToGlobal(self.support_menu_button.rect().bottomRight()))
        if selected == developer_action:
            QDesktopServices.openUrl(QUrl(DEVELOPER_URL))
        elif selected == github_action:
            QDesktopServices.openUrl(QUrl(PRODUCT_GITHUB_URL))

    def _refresh_health_banner(self) -> None:
        if self._health_snapshot_valid:
            health = self.current_health
        else:
            try:
                health = self.service.get_source_health(self._current_chat_source())
            except Exception as exc:  # noqa: BLE001
                health = ProviderHealth(status="error", detail=str(exc))
        self._apply_health(health)

    def _apply_health(self, health: ProviderHealth) -> None:
        self.current_health = health
        name = {
            "ready": "HealthBannerReady",
            "missing_runtime": "HealthBannerWarning",
            "missing_configuration": "HealthBannerWarning",
            "missing_model": "HealthBannerWarning",
            "error": "HealthBannerError",
        }[health.status]
        self.health_banner.setObjectName(name)
        self.health_banner.style().unpolish(self.health_banner)
        self.health_banner.style().polish(self.health_banner)
        parts = [self._t({"ready": "health_ready", "missing_runtime": "health_missing_runtime", "missing_configuration": "health_missing_configuration", "missing_model": "health_missing_model", "error": "health_error"}[health.status])]
        detail = self._consumer_health_detail(health)
        if detail:
            parts.append(detail)
        self.health_banner.setText(" ".join(parts))
        self.header_context_label.setText(self._header_context_text())
        self.provider_description_value.setText(self._profile_status_text())
        self.profile_page_widget.assistant_card.set_description(self._profile_status_text())
        self.profile_page_widget.provider_card.set_description(self._provider_description(self._selected_provider_id()))
        self._populate_setup_guidance(health)
        if not self._is_locked():
            self._refresh_activity_chip("ready" if health.status == "ready" else "setup")
        self._update_interaction_state()

    def _export_current(self, export_format: str) -> None:
        if self.current_conversation_id is None:
            self._show_warning(self._t("warning_no_conversation"), self._t("warning_no_conversation"))
            return
        extension = "md" if export_format == "markdown" else "json"
        suggested = f"conversation-{datetime.now():%Y%m%d-%H%M%S}.{extension}"
        file_filter = self._t("dialog_markdown_filter") if export_format == "markdown" else self._t("dialog_json_filter")
        output_path, _ = QFileDialog.getSaveFileName(self, self._t("dialog_export_title"), str(self.paths.exports_dir / suggested), file_filter)
        if not output_path:
            return
        destination = Path(output_path)
        try:
            if export_format == "markdown":
                self.service.export_conversation_markdown(self.current_conversation_id, destination)
            else:
                self.service.export_conversation_json(self.current_conversation_id, destination)
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_export"), exc)
            return
        self._notify(self._t("dialog_export_title"), str(destination), variant="success", timeout_ms=5200)

    def _render_messages(self, messages: list[MessageRecord]) -> None:
        dark = self.settings.theme == "dark"
        should_pin_to_bottom = self._chat_pinned_to_bottom
        previous_scroll_value = self.chat_view.verticalScrollBar().value()
        render_signature = self._chat_render_signature(messages=messages, dark=dark)
        if render_signature != self._last_chat_signature:
            self._rebuild_chat_widgets(messages=messages, dark=dark)
            self._last_chat_signature = render_signature
            if not should_pin_to_bottom:
                self._restore_chat_scroll(previous_scroll_value)
        elif not should_pin_to_bottom:
            self._restore_chat_scroll(previous_scroll_value)
        self._last_chat_bottom_spacer = self._current_chat_bottom_spacer(should_pin_to_bottom)
        self._scroll_chat_to_bottom_if_pinned(should_pin_to_bottom)

    def _chat_render_signature(self, *, messages: list[MessageRecord], dark: bool) -> tuple[object, ...]:
        return (
            dark,
            self._typing_indicator_message_id,
            self._has_received_generation_chunk,
            self._typing_indicator_phase,
            tuple(
                (
                    message.message_id,
                    message.role,
                    message.content,
                    message.status,
                    message.error,
                )
                for message in messages
            ),
        )

    def _rebuild_chat_widgets(self, *, messages: list[MessageRecord], dark: bool) -> None:
        while self.chat_messages_layout.count():
            item = self.chat_messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not messages:
            empty_state = ChatEmptyState(
                badge=self._t("chat_empty_badge"),
                title=self._t("chat_empty_title"),
                body=self._t("chat_empty_body"),
            )
            self.chat_messages_layout.addStretch(1)
            self.chat_messages_layout.addWidget(empty_state, 0, Qt.AlignmentFlag.AlignHCenter)
            self.chat_messages_layout.addStretch(2)
            return

        for message in messages:
            visible_content = message.content
            if (
                message.message_id == self._typing_indicator_message_id
                and not self._has_received_generation_chunk
                and message.role == "assistant"
                and message.status in {"pending", "streaming"}
                and not message.content.strip()
            ):
                visible_content = typing_indicator_text(self._typing_indicator_phase)
            row = ChatMessageRow(
                message=message,
                visible_content=visible_content,
                avatar_store=self._chat_renderer.avatar_store,
                dark=dark,
            )
            self.chat_messages_layout.addWidget(row)
        self.chat_messages_layout.addStretch(1)

    @staticmethod
    def _message_bubble_html(content: str, status_suffix: str, *, is_user: bool, dark: bool) -> str:
        return build_message_bubble_html(content, status_suffix, is_user=is_user, dark=dark)

    def _assistant_avatar_html(self, dark: bool) -> str:
        return self._chat_renderer.assistant_avatar_html(dark)

    def _user_avatar_html(self) -> str:
        return self._chat_renderer.user_avatar_html()

    def _refresh_activity_chip(self, mode: str) -> None:
        self._status_mode = mode
        state, text = {
            "ready": ("online", "Online"),
            "busy": ("busy", "Busy"),
            "waiting": ("busy", "Busy"),
            "executing": ("busy", "Busy"),
            "setup": ("offline", "Offline"),
        }[mode]
        self.status_chip.set_state(state, text)

    def _handle_chat_scroll(self, value: int) -> None:
        if self._chat_autoscrolling:
            self._chat_pinned_to_bottom = True
            return
        scrollbar = self.chat_view.verticalScrollBar()
        self._chat_pinned_to_bottom = value >= max(0, scrollbar.maximum() - 24)

    def _current_chat_bottom_spacer(self, pinned: bool | None = None) -> int:
        if pinned is None:
            pinned = self._chat_pinned_to_bottom
        if not pinned:
            return 0
        return 0

    def _handle_chat_composer_geometry_changed(self) -> None:
        if self.current_conversation_id is not None and self._chat_pinned_to_bottom:
            self._scroll_chat_to_bottom_if_pinned(True)

    def _restore_chat_scroll(self, value: int) -> None:
        scrollbar = self.chat_view.verticalScrollBar()
        scrollbar.setValue(value)

        def _apply_deferred_restore() -> None:
            deferred_scrollbar = self.chat_view.verticalScrollBar()
            deferred_scrollbar.setValue(min(value, deferred_scrollbar.maximum()))

        QTimer.singleShot(0, _apply_deferred_restore)

    def _scroll_chat_to_bottom_if_pinned(self, pinned: bool | None = None) -> None:
        if pinned is None:
            pinned = self._chat_pinned_to_bottom
        if not pinned:
            return
        self._chat_autoscrolling = True

        scrollbar = self.chat_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        def _apply_deferred_scroll() -> None:
            if self._chat_pinned_to_bottom:
                delayed_scrollbar = self.chat_view.verticalScrollBar()
                delayed_scrollbar.setValue(delayed_scrollbar.maximum())
                QTimer.singleShot(18, _finish_scroll)
            else:
                self._chat_autoscrolling = False

        def _finish_scroll() -> None:
            try:
                final_scrollbar = self.chat_view.verticalScrollBar()
                final_scrollbar.setValue(final_scrollbar.maximum())
            finally:
                self._chat_autoscrolling = False

        QTimer.singleShot(0, _apply_deferred_scroll)

    def _advance_typing_indicator(self) -> None:
        if self.current_conversation_id is None or self._typing_indicator_message_id is None:
            return
        self._typing_indicator_phase = (self._typing_indicator_phase + 1) % 3
        self._render_messages(self.service.load_messages(self.current_conversation_id))

    def _typing_indicator_text(self) -> str:
        return typing_indicator_text(self._typing_indicator_phase)

    def _stop_typing_indicator(self) -> None:
        self._typing_indicator_timer.stop()
        self._typing_indicator_message_id = None
        self._typing_indicator_phase = 0

    def _update_interaction_state(self) -> None:
        generating = self.generation_worker is not None
        executing = self.action_worker is not None
        refreshing_runtime = self.runtime_refresh_worker is not None
        downloading_model = self.model_download_worker is not None
        locked = generating or executing
        provider_ready = self.current_health.status == "ready"
        export_enabled = self.current_conversation_id is not None and not generating and not executing
        for widget, enabled in (
            (self.send_button, not locked and provider_ready),
            (self.cancel_button, generating),
            (self.new_chat_button, not locked),
            (self.regenerate_button, not locked and self.current_conversation_id is not None and provider_ready),
            (self.export_md_button, export_enabled),
            (self.export_json_button, export_enabled),
            (self.composer, not locked and provider_ready),
            (self.chat_source_combo, not locked and not generating and not executing),
            (self.provider_combo, not locked),
            (self.model_combo, not locked),
            (self.default_source_combo, not locked),
            (self.api_model_input, not locked),
            (self.language_combo, not locked),
            (self.theme_combo, not locked),
            (self.local_model_combo, not locked and not downloading_model),
            (self.install_model_button, not locked and not downloading_model),
            (self.remove_model_button, not locked and not downloading_model),
            (self.refresh_button, not locked and not refreshing_runtime),
            (self.updates_refresh_button, not locked and not refreshing_runtime),
            (self.setup_refresh_button, not locked and not refreshing_runtime),
            (self.open_release_button, bool(self.runtime_status.release_url)),
            (self.setup_profile_button, True),
            (self.setup_copy_button, True),
            (self.conversation_list, not locked),
            (self.system_prompt_input, not locked),
            (self.temperature_input, not locked),
            (self.top_p_input, not locked),
            (self.max_tokens_input, not locked),
            (self.require_confirmation_checkbox, not locked),
            (self.web_enabled_checkbox, not locked),
            (self.files_enabled_checkbox, not locked),
            (self.commands_enabled_checkbox, not locked),
            (self.command_allowlist_input, not locked),
            (self.allow_button, False),
            (self.deny_button, False),
        ):
            widget.setEnabled(enabled)
        for widget in self.provider_config_inputs.values():
            widget.setEnabled(not locked)
        if provider_ready:
            self.main_stack.setCurrentWidget(self.chat_page)
        else:
            self.main_stack.setCurrentWidget(self.setup_page)
        if provider_ready and not locked:
            self._refresh_activity_chip("ready")
        elif provider_ready:
            self._refresh_activity_chip("busy")
        else:
            self._refresh_activity_chip("setup")

    def _copy_setup_steps(self) -> None:
        QApplication.clipboard().setText(self.setup_steps_view.toPlainText())
        self._notify(self._t("status_setup_steps_copied"), variant="success")

    def _populate_setup_guidance(self, health: ProviderHealth) -> None:
        source = self._current_chat_source()
        provider_id = self._provider_id_for_source(source)
        provider_name = self._provider_display_name(provider_id)
        model_name = self._model_name_for_source(source)
        self.setup_provider_summary.setText(self._t("setup_provider_summary", provider=provider_name))
        self.setup_model_summary.setText(self._t("setup_model_summary", model=model_name))

        if health.status == "ready":
            self.setup_title.setText(self._t("health_ready"))
            self.setup_body.setText(self._provider_description(provider_id))
            self.setup_steps_view.setPlainText("")
            return

        title_key = {
            "missing_runtime": "setup_title_missing_runtime",
            "missing_model": "setup_title_missing_model",
            "missing_configuration": "setup_title_missing_configuration",
            "error": "setup_title_error",
        }[health.status]

        body, steps = self._setup_guidance_for_health(provider_id, health, model_name)
        self.setup_title.setText(self._t(title_key))
        self.setup_body.setText(body)
        self.setup_steps_view.setPlainText("\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1)))

    def _setup_guidance_for_health(self, provider_id: str, health: ProviderHealth, model_name: str) -> tuple[str, list[str]]:
        _ = provider_id
        if health.status == "missing_runtime":
            return self._t("setup_body_missing_runtime_local"), [self._t("setup_step_runtime_binary"), self._t("setup_step_refresh")]
        if health.status == "missing_model":
            return self._t("setup_body_missing_model_local", model=model_name), [self._t("setup_step_open_profile"), self._t("setup_step_install_local_model")]
        return self._append_health_detail(self._t("setup_body_generic_local_error"), self._consumer_health_detail(health)), [self._t("setup_step_refresh")]

    @staticmethod
    def _append_health_detail(body: str, detail: str) -> str:
        normalized_detail = detail.strip()
        if not normalized_detail or normalized_detail == body:
            return body
        return f"{body}\n\n{normalized_detail}"

    def _provider_description(self, provider_id: str) -> str:
        descriptor = self._provider_descriptors.get(provider_id)
        return self._t(descriptor.description_key) if descriptor else ""

    def _provider_display_name(self, provider_id: str) -> str:
        descriptor = self._provider_descriptors.get(provider_id)
        return descriptor.display_name if descriptor else provider_id

    def _provider_id_for_source(self, source: ModelSource) -> str:
        _ = source
        return "local_llama"

    def _model_name_for_source(self, source: ModelSource) -> str:
        _ = source
        return self._model_display_name(self._selected_local_model_id() or self.settings.model or DEFAULT_MODEL)

    def _role_label(self, role: str) -> str:
        return {"system": self._t("role_system"), "user": self._t("role_user"), "assistant": self._t("role_assistant")}.get(role, role)

    def _localized_action_kind(self, action_kind: str) -> str:
        return {"web_fetch": self._t("action_web_fetch"), "file_read": self._t("action_file_read"), "file_write": self._t("action_file_write"), "command_run": self._t("action_command_run")}.get(action_kind, action_kind)

    def _localized_risk(self, risk: str) -> str:
        return {"low": self._t("risk_low"), "medium": self._t("risk_medium"), "high": self._t("risk_high")}.get(risk, risk)

    def _selected_provider_id(self) -> str:
        return "local_llama"

    def _selected_model_id(self) -> str:
        model_id = self.model_combo.currentData()
        if isinstance(model_id, str) and model_id.strip():
            return model_id.strip()
        return self.model_combo.currentText().strip() or self.settings.model

    def _selected_local_model_id(self) -> str:
        model_id = self.local_model_combo.currentData()
        if isinstance(model_id, str) and model_id.strip():
            return model_id.strip()
        return self.settings.model

    def _selected_model_label(self) -> str:
        text = self.model_combo.currentText().strip()
        return text or self._selected_model_id()

    def _model_display_name(self, model_id: str) -> str:
        for index in range(self.model_combo.count()):
            data = self.model_combo.itemData(index)
            if isinstance(data, str) and data == model_id:
                return self.model_combo.itemText(index)
        return model_id

    def _selected_language(self) -> Language:
        language = self.language_combo.currentData()
        return language if language in {"en", "ru"} else self.localization.language

    def _selected_default_source(self) -> ModelSource:
        return "local"

    def _selected_chat_source(self) -> ModelSource:
        return "local"

    def _selected_theme(self) -> ThemeMode:
        theme = self.theme_combo.currentData()
        if theme in {"light", "dark"}:
            return theme
        return self.settings.theme

    def _current_chat_source(self) -> ModelSource:
        return "local"

    def _apply_theme(self, theme: ThemeMode) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self.settings.theme = theme
        app.setStyleSheet(build_stylesheet(theme))
        self.bottom_nav.set_theme(theme)
        self._sync_chat_source_ui()

    def _sync_chat_source_ui(self) -> None:
        source = self._current_chat_source()
        self.chat_source_value.setText(self._t(f"source_{source}"))

    def _header_context_text(self) -> str:
        if self._workspace == "profile":
            return self._t("header_context_profile")
        if self.current_health.status == "ready":
            return self._t("header_context_chat")
        return self._t("header_context_setup")

    def _profile_status_text(self) -> str:
        provider_name = self._provider_display_name(self._selected_provider_id())
        model_name = self._selected_model_label() or self.settings.model
        if self.current_health.status == "ready":
            return self._t("profile_status_ready", provider=provider_name, model=model_name)
        mapping = {
            "missing_runtime": "health_missing_runtime",
            "missing_configuration": "health_missing_configuration",
            "missing_model": "health_missing_model",
            "error": "health_error",
        }
        status_text = self._t(mapping.get(self.current_health.status, "health_error"))
        detail = self.current_health.detail.strip()
        if detail:
            return f"{provider_name} • {status_text}\n{detail}"
        return f"{provider_name} • {status_text}"

    def _profile_status_text(self) -> str:
        provider_name = self._provider_display_name(self._selected_provider_id())
        model_name = self._selected_model_label() or self.settings.model
        if self.current_health.status == "ready":
            return self._t("profile_status_ready", provider=provider_name, model=model_name)
        mapping = {
            "missing_runtime": "health_missing_runtime",
            "missing_configuration": "health_missing_configuration",
            "missing_model": "health_missing_model",
            "error": "health_error",
        }
        status_text = self._t(mapping.get(self.current_health.status, "health_error"))
        detail = self.current_health.detail.strip()
        if detail:
            return f"{provider_name} · {status_text}\n{detail}"
        return f"{provider_name} · {status_text}"

    def _profile_status_text(self) -> str:
        if self.current_health.status == "ready":
            return self._t("profile_status_ready")
        mapping = {
            "missing_runtime": "health_missing_runtime",
            "missing_configuration": "health_missing_configuration",
            "missing_model": "health_missing_model",
            "error": "health_error",
        }
        status_text = self._t(mapping.get(self.current_health.status, "health_error"))
        detail = self._consumer_health_detail(self.current_health)
        if detail:
            return f"{status_text}\n{detail}"
        return status_text

    def _consumer_health_detail(self, health: ProviderHealth) -> str:
        detail = health.detail.strip().lower()
        if not detail:
            return ""
        if "local runtime" in detail or "runtime binary" in detail:
            return self._t("setup_body_missing_runtime_local")
        if "not installed" in detail:
            return self._t("setup_body_missing_model_local", model=self._model_name_for_source("local"))
        if "connection failed" in detail or "timed out" in detail:
            return self._t("setup_body_generic_local_error")
        if health.status == "missing_model":
            return self._t("setup_body_missing_model_local", model=self._model_name_for_source("local"))
        return self._t("setup_body_generic_local_error")

    def _set_workspace(self, workspace: str) -> None:
        self._workspace = workspace
        self.workspace_stack.setCurrentWidget(self.chat_workspace if workspace == "chat" else self.settings_workspace)
        self.header_context_label.setText(self._header_context_text())
        self._update_nav_state()
        QTimer.singleShot(0, self._sync_overlay_geometry)

    def _update_nav_state(self) -> None:
        self.bottom_nav.set_active(self._workspace)

    def _is_locked(self) -> bool:
        return self.generation_worker is not None or self.action_worker is not None or self.pending_action_id is not None

    def _show_error(self, title: str, exc: Exception) -> None:
        LOGGER.exception(title, exc_info=exc)
        self._show_message_box(QMessageBox.Icon.Critical, title, self._normalize_error_message(exc))

    def _normalize_error_message(self, exc: Exception) -> str:
        if not isinstance(exc, ProviderError):
            return str(exc)
        detail = str(exc).strip().lower()
        if "local runtime" in detail or "not installed" in detail or "runtime binary" in detail:
            return self._t("setup_body_missing_runtime_local")
        if "connection failed" in detail or "timed out" in detail:
            return self._t("setup_body_generic_local_error")
        return self._t("setup_body_generic_local_error")

    def _configure_generation_controls(self) -> None:
        tooltip = self._t("settings_generation_locked_hint", max_tokens=str(DEFAULT_MAX_TOKENS))
        for widget, value in (
            (self.temperature_input, DEFAULT_TEMPERATURE),
            (self.top_p_input, DEFAULT_TOP_P),
            (self.max_tokens_input, DEFAULT_MAX_TOKENS),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.setReadOnly(True)
            widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            widget.setToolTip(tooltip)
            widget.blockSignals(False)
        for label in (self.temperature_label, self.top_p_label, self.max_tokens_label):
            label.setToolTip(tooltip)

    def _show_warning(self, title: str, message: str) -> None:
        self._show_message_box(QMessageBox.Icon.Warning, title, message)

    def _show_message_box(self, icon: QMessageBox.Icon, title: str, message: str) -> None:
        variant = "error" if icon == QMessageBox.Icon.Critical else "warning"
        dialog = SheetDialog(
            self,
            title=title,
            body=message,
            confirm_text="OK",
        )
        dialog.exec()
        self._show_alert(title, message, variant=variant, timeout_ms=4200)

    def _show_approval_sheet(self, action: AssistantAction) -> bool:
        details = json.dumps(action.payload, indent=2, ensure_ascii=False)
        body = (
            f"{action.description or self._t('approval_body')}\n\n"
            f"{self._t('approval_kind')}: {self._localized_action_kind(action.kind)}\n"
            f"{self._t('approval_target')}: {action.target}\n"
            f"{self._t('approval_risk')}: {self._localized_risk(action.risk)}"
        )
        dialog = SheetDialog(
            self,
            title=self._t("approval_title"),
            body=body,
            details=details,
            confirm_text=self._t("button_allow"),
            cancel_text=self._t("button_deny"),
            danger=action.risk == "high",
        )
        return dialog.exec() == int(dialog.DialogCode.Accepted)

    def _notify(self, title: str, message: str = "", variant: str = "info", timeout_ms: int = 3600) -> None:
        self._show_alert(title, message, variant=variant, timeout_ms=timeout_ms)

    def _show_alert(self, title: str, message: str = "", variant: str = "info", timeout_ms: int = 3600) -> None:
        self.notification_center.show_alert(title, message, variant=variant, timeout_ms=timeout_ms)

    def _show_event(
        self,
        event_id: str,
        title: str,
        message: str = "",
        variant: str = "info",
        progress: int | None = None,
        timeout_ms: int = 0,
    ) -> None:
        self.notification_center.show_event(
            event_id=event_id,
            title=title,
            message=message,
            variant=variant,
            progress=progress,
            auto_hide_ms=timeout_ms,
        )

    def _finish_event(
        self,
        event_id: str,
        title: str,
        message: str = "",
        variant: str = "success",
        progress: int | None = None,
        timeout_ms: int = 3200,
    ) -> None:
        self.notification_center.finish_event(
            event_id=event_id,
            title=title,
            message=message,
            variant=variant,
            progress=progress,
            auto_hide_ms=timeout_ms,
        )

    @staticmethod
    def _model_download_event_id(model_id: str) -> str:
        normalized = model_id.strip() if model_id.strip() else "active"
        return f"model-download:{normalized}"

    def _notification_label(self, value: str) -> str:
        mapping = {
            "Hide": "button_hide",
            "Unhide": "button_unhide",
        }
        return self._t(mapping.get(value, value))

    def _t(self, key: str, **kwargs: str) -> str:
        return self.localization.t(key, **kwargs)

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        if combo.isEditable():
            combo.setCurrentText(value)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_overlay_geometry()

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._is_closing = True
        self._stop_typing_indicator()
        self._background_refresh_timer.stop()
        if self.generation_worker is not None:
            self.generation_worker.cancel()
            if self.generation_thread is not None:
                self.generation_thread.quit()
                self.generation_thread.wait(1500)
        if self.action_thread is not None:
            self.action_thread.quit()
            self.action_thread.wait(1500)
        if self.runtime_refresh_thread is not None:
            self.runtime_refresh_thread.quit()
            self.runtime_refresh_thread.wait(1500)
        if self.installer_thread is not None:
            self.installer_thread.quit()
            self.installer_thread.wait(1500)
        if self.model_download_worker is not None:
            self.model_download_worker.cancel()
            if self.model_download_thread is not None:
                self.model_download_thread.quit()
                self.model_download_thread.wait(1500)
        self.service.runtime_service.stop()
        event.accept()
