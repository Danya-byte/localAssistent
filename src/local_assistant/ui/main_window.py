from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..actions.executor import ActionExecutor
from ..config import APP_NAME, DEFAULT_LANGUAGE, AppPaths
from ..exceptions import ActionError, ProviderError
from ..i18n import LocalizationManager
from ..models import AppSettings, AssistantAction, Language, MessageRecord, ProviderHealth
from ..services.chat_service import ChatService, PreparedGeneration
from .theme import APP_STYLESHEET
from .workers import ActionWorker, GenerationWorker


LOGGER = logging.getLogger(__name__)


class ComposerTextEdit(QPlainTextEdit):
    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            main_window = self.window()
            if hasattr(main_window, "_send_message"):
                main_window._send_message()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
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
        self._status_mode = "ready"
        self._updating_form = False
        self._conversation_items: dict[str, QListWidgetItem] = {}
        self._provider_descriptors = {item.provider_id: item for item in self.service.list_provider_descriptors()}
        self._rendered_provider_id: str | None = None
        self.provider_config_inputs: dict[str, QLineEdit] = {}

        self.setWindowTitle(APP_NAME)
        self.resize(1540, 940)
        self.setMinimumSize(1260, 780)
        self._setup_ui()
        self._apply_glass_effects()
        self._populate_providers()
        self._apply_settings_to_form(self.settings)
        self._populate_models()
        self._populate_conversations()
        self._restore_last_conversation()
        self._retranslate_ui()
        self._refresh_health_banner()
        self._update_interaction_state()

    def _setup_ui(self) -> None:
        app = QApplication.instance()
        assert app is not None
        app.setStyleSheet(APP_STYLESHEET)
        app.setFont(QFont("Segoe UI Variable", 10))

        central = QWidget()
        central.setObjectName("AppRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        self.header_card = QFrame()
        self.header_card.setObjectName("HeaderCard")
        header = QHBoxLayout(self.header_card)
        header.setContentsMargins(22, 18, 22, 18)
        header.setSpacing(18)

        header_copy = QVBoxLayout()
        self.header_title = QLabel()
        self.header_title.setObjectName("HeaderTitle")
        self.header_subtitle = QLabel()
        self.header_subtitle.setWordWrap(True)
        header_copy.addWidget(self.header_title)
        header_copy.addWidget(self.header_subtitle)
        header.addLayout(header_copy, 1)

        header_controls = QVBoxLayout()
        self.provider_header_label = QLabel()
        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self._handle_provider_change)
        self.model_header_label = QLabel()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.currentTextChanged.connect(self._handle_model_change)
        self.language_header_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self._handle_language_change)
        self.refresh_button = QPushButton()
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self._refresh_runtime_state)

        for label, widget in ((self.provider_header_label, self.provider_combo), (self.model_header_label, self.model_combo)):
            row = QHBoxLayout()
            row.addWidget(label)
            row.addWidget(widget, 1)
            header_controls.addLayout(row)
        language_row = QHBoxLayout()
        language_row.addWidget(self.language_header_label)
        language_row.addWidget(self.language_combo, 1)
        language_row.addWidget(self.refresh_button)
        header_controls.addLayout(language_row)
        header.addLayout(header_controls, 1)
        root.addWidget(self.header_card)

        self.health_banner = QLabel()
        self.health_banner.setWordWrap(True)
        root.addWidget(self.health_banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        self._build_sidebar(splitter)
        self._build_center(splitter)
        self._build_settings_panel(splitter)
        splitter.setSizes([280, 820, 360])

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().setSizeGripEnabled(False)
        self.file_menu = self.menuBar().addMenu("")
        self.export_md_action = QAction(self)
        self.export_md_action.triggered.connect(lambda: self._export_current("markdown"))
        self.export_json_action = QAction(self)
        self.export_json_action.triggered.connect(lambda: self._export_current("json"))
        self.file_menu.addAction(self.export_md_action)
        self.file_menu.addAction(self.export_json_action)

    def _apply_glass_effects(self) -> None:
        for widget, blur_radius, y_offset, alpha in (
            (self.sidebar_panel, 44, 16, 90),
            (self.center_shell, 48, 20, 70),
            (self.settings_panel, 44, 16, 90),
            (self.header_card, 34, 10, 50),
            (self.chat_surface, 30, 10, 42),
            (self.composer_card, 32, 12, 44),
            (self.approval_card, 36, 14, 54),
            (self.settings_intro_card, 28, 10, 40),
        ):
            effect = QGraphicsDropShadowEffect(widget)
            effect.setBlurRadius(blur_radius)
            effect.setOffset(0, y_offset)
            effect.setColor(QColor(15, 23, 42, alpha))
            widget.setGraphicsEffect(effect)

    def _build_sidebar(self, splitter: QSplitter) -> None:
        self.sidebar_panel = QFrame()
        self.sidebar_panel.setObjectName("Sidebar")
        layout = QVBoxLayout(self.sidebar_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        self.app_title_label = QLabel()
        self.app_title_label.setObjectName("AppTitle")
        self.sidebar_title_label = QLabel()
        self.sidebar_title_label.setObjectName("SectionTitle")
        self.conversation_list = QListWidget()
        self.conversation_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.conversation_list.currentItemChanged.connect(self._handle_conversation_selection)
        self.new_chat_button = QPushButton()
        self.new_chat_button.clicked.connect(self._start_new_chat)
        self.export_md_button = QPushButton()
        self.export_md_button.setProperty("secondary", True)
        self.export_md_button.clicked.connect(lambda: self._export_current("markdown"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.new_chat_button)
        buttons.addWidget(self.export_md_button)
        layout.addWidget(self.app_title_label)
        layout.addWidget(self.sidebar_title_label)
        layout.addWidget(self.conversation_list, 1)
        layout.addLayout(buttons)
        splitter.addWidget(self.sidebar_panel)

    def _build_center(self, splitter: QSplitter) -> None:
        self.center_shell = QFrame()
        self.center_shell.setObjectName("CenterShell")
        layout = QVBoxLayout(self.center_shell)
        layout.setContentsMargins(18, 18, 18, 18)
        header = QHBoxLayout()
        self.chat_title = QLabel()
        self.chat_title.setObjectName("HeaderTitle")
        self.status_chip = QLabel()
        self.status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.chat_title, 1)
        header.addWidget(self.status_chip)
        layout.addLayout(header)
        self.main_stack = QStackedWidget()
        layout.addWidget(self.main_stack, 1)
        self._build_chat_page()
        self._build_approval_page()
        splitter.addWidget(self.center_shell)

    def _build_settings_panel(self, splitter: QSplitter) -> None:
        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        layout = QVBoxLayout(self.settings_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        self.settings_intro_card = QFrame()
        self.settings_intro_card.setObjectName("SettingsIntroCard")
        intro_layout = QVBoxLayout(self.settings_intro_card)
        intro_layout.setContentsMargins(18, 18, 18, 18)
        intro_layout.setSpacing(10)
        self.settings_title_label = QLabel()
        self.settings_title_label.setObjectName("SectionTitle")
        self.provider_description_label = QLabel()
        self.provider_description_label.setObjectName("SectionTitle")
        self.provider_description_value = QLabel()
        self.provider_description_value.setWordWrap(True)
        intro_layout.addWidget(self.settings_title_label)
        intro_layout.addWidget(self.provider_description_label)
        intro_layout.addWidget(self.provider_description_value)
        layout.addWidget(self.settings_intro_card)
        self._build_settings_form(layout)
        splitter.addWidget(self.settings_panel)

    def _build_chat_page(self) -> None:
        self.chat_page = QWidget()
        layout = QVBoxLayout(self.chat_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.chat_surface = QFrame()
        self.chat_surface.setObjectName("ChatSurface")
        chat_layout = QVBoxLayout(self.chat_surface)
        chat_layout.setContentsMargins(18, 18, 18, 18)
        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(True)
        chat_layout.addWidget(self.chat_view, 1)
        layout.addWidget(self.chat_surface, 1)
        self.composer_card = QFrame()
        self.composer_card.setObjectName("ComposerCard")
        composer_layout = QVBoxLayout(self.composer_card)
        composer_layout.setContentsMargins(18, 18, 18, 18)
        composer_layout.setSpacing(14)
        self.composer = ComposerTextEdit(self.chat_page)
        self.composer.setFixedHeight(124)
        self.send_button = QPushButton()
        self.send_button.clicked.connect(self._send_message)
        self.cancel_button = QPushButton()
        self.cancel_button.setProperty("secondary", True)
        self.cancel_button.clicked.connect(self._cancel_generation)
        self.regenerate_button = QPushButton()
        self.regenerate_button.setProperty("secondary", True)
        self.regenerate_button.clicked.connect(self._regenerate_last)
        self.export_json_button = QPushButton()
        self.export_json_button.setProperty("secondary", True)
        self.export_json_button.clicked.connect(lambda: self._export_current("json"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.send_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.regenerate_button)
        buttons.addStretch(1)
        buttons.addWidget(self.export_json_button)
        composer_layout.addWidget(self.composer)
        composer_layout.addLayout(buttons)
        layout.addWidget(self.composer_card)
        self.main_stack.addWidget(self.chat_page)

    def _build_approval_page(self) -> None:
        self.approval_page = QWidget()
        page = QVBoxLayout(self.approval_page)
        page.setContentsMargins(22, 18, 22, 18)
        self.approval_card = QFrame()
        self.approval_card.setObjectName("ApprovalCard")
        layout = QVBoxLayout(self.approval_card)
        layout.setContentsMargins(22, 22, 22, 22)
        self.approval_title = QLabel()
        self.approval_title.setObjectName("HeaderTitle")
        self.approval_text = QLabel()
        self.approval_text.setWordWrap(True)
        self.approval_kind_label = QLabel()
        self.approval_kind_value = QLabel()
        self.approval_target_label = QLabel()
        self.approval_target_value = QLabel()
        self.approval_risk_label = QLabel()
        self.approval_risk_value = QLabel()
        self.approval_details_label = QLabel()
        self.approval_details_value = QLabel()
        self.approval_details_value.setWordWrap(True)
        self.approval_payload_label = QLabel()
        self.approval_payload_view = QPlainTextEdit()
        self.approval_payload_view.setObjectName("ApprovalPayloadView")
        self.approval_payload_view.setReadOnly(True)
        self.approval_payload_view.setFixedHeight(180)
        self.allow_button = QPushButton()
        self.allow_button.clicked.connect(self._allow_pending_action)
        self.deny_button = QPushButton()
        self.deny_button.setProperty("danger", True)
        self.deny_button.clicked.connect(self._deny_pending_action)
        for widget in (
            self.approval_title,
            self.approval_text,
            self.approval_kind_label,
            self.approval_kind_value,
            self.approval_target_label,
            self.approval_target_value,
            self.approval_risk_label,
            self.approval_risk_value,
            self.approval_details_label,
            self.approval_details_value,
            self.approval_payload_label,
            self.approval_payload_view,
        ):
            layout.addWidget(widget)
        buttons = QHBoxLayout()
        buttons.addWidget(self.allow_button)
        buttons.addWidget(self.deny_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        page.addWidget(self.approval_card)
        page.addStretch(1)
        self.main_stack.addWidget(self.approval_page)

    def _build_settings_form(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self.system_prompt_label = QLabel()
        self.system_prompt_input = QPlainTextEdit()
        self.system_prompt_input.setFixedHeight(120)
        self.system_prompt_input.textChanged.connect(self._persist_settings)
        self.temperature_label = QLabel()
        self.temperature_input = QDoubleSpinBox()
        self.temperature_input.setRange(0.0, 2.0)
        self.temperature_input.setSingleStep(0.1)
        self.temperature_input.valueChanged.connect(self._persist_settings)
        self.top_p_label = QLabel()
        self.top_p_input = QDoubleSpinBox()
        self.top_p_input.setRange(0.1, 1.0)
        self.top_p_input.setSingleStep(0.05)
        self.top_p_input.valueChanged.connect(self._persist_settings)
        self.max_tokens_label = QLabel()
        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(64, 8192)
        self.max_tokens_input.setSingleStep(64)
        self.max_tokens_input.valueChanged.connect(self._persist_settings)
        for label, widget in (
            (self.system_prompt_label, self.system_prompt_input),
            (self.temperature_label, self.temperature_input),
            (self.top_p_label, self.top_p_input),
            (self.max_tokens_label, self.max_tokens_input),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)

        self.provider_fields_title = QLabel()
        self.provider_fields_title.setObjectName("SectionTitle")
        layout.addWidget(self.provider_fields_title)
        self.provider_form_host = QWidget()
        self.provider_form_layout = QFormLayout(self.provider_form_host)
        layout.addWidget(self.provider_form_host)

        self.require_confirmation_checkbox = QCheckBox()
        self.require_confirmation_checkbox.stateChanged.connect(self._persist_settings)
        self.web_enabled_checkbox = QCheckBox()
        self.web_enabled_checkbox.stateChanged.connect(self._persist_settings)
        self.files_enabled_checkbox = QCheckBox()
        self.files_enabled_checkbox.stateChanged.connect(self._persist_settings)
        self.commands_enabled_checkbox = QCheckBox()
        self.commands_enabled_checkbox.stateChanged.connect(self._persist_settings)
        for box in (
            self.require_confirmation_checkbox,
            self.web_enabled_checkbox,
            self.files_enabled_checkbox,
            self.commands_enabled_checkbox,
        ):
            layout.addWidget(box)
        self.command_allowlist_label = QLabel()
        self.command_allowlist_input = QLineEdit()
        self.command_allowlist_input.setPlaceholderText("dir, echo, whoami")
        self.command_allowlist_input.textChanged.connect(self._persist_settings)
        layout.addWidget(self.command_allowlist_label)
        layout.addWidget(self.command_allowlist_input)
        layout.addStretch(1)

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._t("app_title"))
        self.app_title_label.setText(self._t("app_title"))
        self.sidebar_title_label.setText(self._t("sidebar_conversations"))
        self.header_title.setText(self._t("header_title"))
        self.header_subtitle.setText(self._t("header_subtitle"))
        self.provider_header_label.setText(self._t("settings_provider"))
        self.model_header_label.setText(self._t("settings_model"))
        self.language_header_label.setText(self._t("settings_language"))
        self.refresh_button.setText(self._t("button_refresh"))
        self.new_chat_button.setText(self._t("button_new_chat"))
        self.export_md_button.setText(self._t("button_export_md"))
        self.send_button.setText(self._t("button_send"))
        self.cancel_button.setText(self._t("button_cancel"))
        self.regenerate_button.setText(self._t("button_regenerate"))
        self.export_json_button.setText(self._t("button_export_json"))
        self.composer.setPlaceholderText(self._t("chat_placeholder"))
        self.approval_kind_label.setText(self._t("approval_kind"))
        self.approval_target_label.setText(self._t("approval_target"))
        self.approval_risk_label.setText(self._t("approval_risk"))
        self.approval_details_label.setText(self._t("approval_details"))
        self.approval_payload_label.setText(self._t("approval_payload"))
        self.allow_button.setText(self._t("button_allow"))
        self.deny_button.setText(self._t("button_deny"))
        self.settings_title_label.setText(self._t("settings_title"))
        self.provider_description_label.setText(self._t("settings_provider"))
        self.provider_fields_title.setText(self._t("provider_details"))
        self.system_prompt_label.setText(self._t("settings_system_prompt"))
        self.temperature_label.setText(self._t("settings_temperature"))
        self.top_p_label.setText(self._t("settings_top_p"))
        self.max_tokens_label.setText(self._t("settings_max_tokens"))
        self.require_confirmation_checkbox.setText(self._t("settings_require_confirmation"))
        self.web_enabled_checkbox.setText(self._t("settings_web_enabled"))
        self.files_enabled_checkbox.setText(self._t("settings_files_enabled"))
        self.commands_enabled_checkbox.setText(self._t("settings_commands_enabled"))
        self.command_allowlist_label.setText(self._t("settings_command_allowlist"))
        self.file_menu.setTitle(self._t("file_menu"))
        self.export_md_action.setText(self._t("menu_export_md"))
        self.export_json_action.setText(self._t("menu_export_json"))
        self._populate_language_choices(self._selected_language())
        self.provider_description_value.setText(self._provider_description(self._selected_provider_id()))
        self._render_provider_config_fields()
        self._refresh_activity_chip(self._status_mode)
        self._render_messages(self.service.load_messages(self.current_conversation_id) if self.current_conversation_id else [])

    def _populate_language_choices(self, current: str | None = None) -> None:
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(self._t("language_ru"), "ru")
        self.language_combo.addItem(self._t("language_en"), "en")
        self._set_combo_by_data(self.language_combo, current or self.localization.language)
        self.language_combo.blockSignals(False)

    def _populate_providers(self) -> None:
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for descriptor in self._provider_descriptors.values():
            self.provider_combo.addItem(descriptor.display_name, descriptor.provider_id)
        self._set_combo_by_data(self.provider_combo, self.settings.provider_id)
        self.provider_combo.blockSignals(False)

    def _populate_models(self) -> None:
        try:
            models = self.service.list_models(self._selected_provider_id())
        except Exception:  # noqa: BLE001
            models = []
        current = self.model_combo.currentText().strip() or self.settings.model
        unique: list[str] = []
        for name in [item.model_id or item.display_name for item in models] + [current]:
            if name and name not in unique:
                unique.append(name)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(unique)
        self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)

    def _apply_settings_to_form(self, settings: AppSettings) -> None:
        self._updating_form = True
        try:
            self.settings = settings
            self.state.settings = settings
            self._set_combo_by_data(self.provider_combo, settings.provider_id)
            self._populate_language_choices(settings.language)
            self._set_combo_by_data(self.language_combo, settings.language)
            self.model_combo.setCurrentText(settings.model)
            self.system_prompt_input.setPlainText(settings.system_prompt)
            self.temperature_input.setValue(settings.temperature)
            self.top_p_input.setValue(settings.top_p)
            self.max_tokens_input.setValue(settings.max_tokens)
            self.require_confirmation_checkbox.setChecked(settings.require_confirmation)
            self.web_enabled_checkbox.setChecked(settings.web_enabled)
            self.files_enabled_checkbox.setChecked(settings.files_enabled)
            self.commands_enabled_checkbox.setChecked(settings.commands_enabled)
            self.command_allowlist_input.setText(", ".join(settings.command_allowlist))
            self.provider_description_value.setText(self._provider_description(settings.provider_id))
            self._render_provider_config_fields()
        finally:
            self._updating_form = False

    def _render_provider_config_fields(self) -> None:
        while self.provider_form_layout.rowCount():
            self.provider_form_layout.removeRow(0)
        self.provider_config_inputs.clear()
        provider_id = self._selected_provider_id()
        descriptor = self._provider_descriptors.get(provider_id)
        self._rendered_provider_id = provider_id
        if descriptor is None:
            return
        current_config = dict(self.settings.provider_configs.get(provider_id, {}))
        for field in descriptor.config_fields:
            label = QLabel(self._t(field.label_key))
            widget = QLineEdit(current_config.get(field.name, ""))
            if field.placeholder_key:
                widget.setPlaceholderText(self._t(field.placeholder_key))
            if field.secret:
                widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.textChanged.connect(self._persist_settings)
            widget.editingFinished.connect(self._refresh_health_banner)
            self.provider_form_layout.addRow(label, widget)
            self.provider_config_inputs[field.name] = widget

    def _populate_conversations(self) -> None:
        selected = self.current_conversation_id
        self._conversation_items.clear()
        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()
        for conversation in self.service.load_conversations():
            item = QListWidgetItem(f"{conversation.title}\n{conversation.updated_at.astimezone():%Y-%m-%d %H:%M}")
            item.setData(Qt.ItemDataRole.UserRole, conversation.conversation_id)
            self.conversation_list.addItem(item)
            self._conversation_items[conversation.conversation_id] = item
        self.conversation_list.blockSignals(False)
        if selected and selected in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[selected])

    def _restore_last_conversation(self) -> None:
        if self.settings.last_conversation_id and self.settings.last_conversation_id in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[self.settings.last_conversation_id])
        elif self.conversation_list.count():
            self.conversation_list.setCurrentRow(0)
        else:
            self.chat_title.setText(self._t("chat_title_new"))
            self._render_messages([])

    def _handle_provider_change(self) -> None:
        if self._updating_form:
            return
        self._persist_settings()
        self.provider_description_value.setText(self._provider_description(self._selected_provider_id()))
        self._render_provider_config_fields()
        self._populate_models()
        self._refresh_health_banner()

    def _handle_model_change(self) -> None:
        if not self._updating_form:
            self._persist_settings()
            self._refresh_health_banner()

    def _handle_language_change(self) -> None:
        if self._updating_form:
            return
        self.localization.set_language(self._selected_language())
        self._persist_settings()
        self._retranslate_ui()
        self._refresh_health_banner()

    def _handle_conversation_selection(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if current is None:
            self.current_conversation_id = None
            self.chat_title.setText(self._t("chat_title_new"))
            self._render_messages([])
            self.settings = self.service.set_last_conversation(None)
            self.state.settings = self.settings
            self._update_interaction_state()
            return
        self.current_conversation_id = current.data(Qt.ItemDataRole.UserRole)
        self.settings = self.service.set_last_conversation(self.current_conversation_id)
        self.state.settings = self.settings
        self.chat_title.setText(current.text().splitlines()[0])
        self._render_messages(self.service.load_messages(self.current_conversation_id))
        self._update_interaction_state()

    def _start_new_chat(self) -> None:
        if self._is_locked():
            self._show_warning(self._t("warning_in_progress"), self._t("warning_finish_current_first"))
            return
        self.conversation_list.clearSelection()
        self.current_conversation_id = None
        self.chat_title.setText(self._t("chat_title_new"))
        self._render_messages([])
        self.composer.setFocus()
        self._persist_settings()

    def _send_message(self) -> None:
        if self._is_locked():
            self._show_warning(self._t("warning_in_progress"), self._t("warning_finish_current_first"))
            return
        text = self.composer.toPlainText().strip()
        if not text:
            return
        self._persist_settings()
        try:
            prepared = self.service.prepare_user_generation(self.current_conversation_id, text)
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_send"), exc)
            return
        self.composer.clear()
        self.current_conversation_id = prepared.conversation.conversation_id
        self.current_assistant_message_id = prepared.assistant_message.message_id
        self._populate_conversations()
        if self.current_conversation_id in self._conversation_items:
            self.conversation_list.setCurrentItem(self._conversation_items[self.current_conversation_id])
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
        self._render_messages(self.service.load_messages(prepared.conversation.conversation_id))
        self._start_generation(prepared)

    def _start_generation(self, prepared: PreparedGeneration) -> None:
        try:
            provider = self.service.providers.get(prepared.request.provider_id)
        except Exception as exc:  # noqa: BLE001
            self._show_error(self._t("error_generation"), exc)
            return
        self._refresh_activity_chip("busy")
        self.statusBar().showMessage(self._t("status_generation_with_model", model=prepared.request.model))
        self.generation_thread = QThread(self)
        self.generation_worker = GenerationWorker(provider, prepared.request)
        self.generation_worker.moveToThread(self.generation_thread)
        self.generation_thread.started.connect(self.generation_worker.run)
        self.generation_worker.chunk_received.connect(self._handle_generation_chunk)
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
        self.service.append_to_message(self.current_assistant_message_id, chunk)
        if self.current_conversation_id:
            self._render_messages(self.service.load_messages(self.current_conversation_id))

    def _handle_generation_completed(self) -> None:
        if self.current_assistant_message_id is None:
            return
        self.service.finalize_message(self.current_assistant_message_id)
        action = None
        try:
            action = self.service.parse_action_request(self.current_assistant_message_id)
        except ActionError as exc:
            self._show_error(self._t("error_action"), exc)
        if self.current_conversation_id:
            self._render_messages(self.service.load_messages(self.current_conversation_id))
        self._populate_conversations()
        if action is not None and action.action_id is not None:
            self.pending_action_id = action.action_id
            self._show_approval_page(action)
            self.statusBar().showMessage(self._t("status_waiting_approval"), 5000)
            self._refresh_activity_chip("waiting")
        else:
            self.statusBar().showMessage(self._t("status_response_completed"), 5000)
            self._refresh_activity_chip("ready")

    def _handle_generation_failed(self, error: str, cancelled: bool) -> None:
        if self.current_assistant_message_id is not None:
            self.service.fail_message(self.current_assistant_message_id, error, cancelled=cancelled)
            if self.current_conversation_id:
                self._render_messages(self.service.load_messages(self.current_conversation_id))
        if cancelled:
            self.statusBar().showMessage(self._t("status_generation_cancelled"), 5000)
        else:
            self._show_error(self._t("error_generation"), ProviderError(error))
        self._refresh_activity_chip("ready")

    def _generation_cleanup(self) -> None:
        self.generation_worker = None
        self.generation_thread = None
        self.current_assistant_message_id = None
        self._update_interaction_state()
        if self.pending_action_id is None and self.action_worker is None:
            self._refresh_health_banner()

    def _cancel_generation(self) -> None:
        if self.generation_worker is not None:
            self.generation_worker.cancel()
            self.statusBar().showMessage(self._t("status_cancelling"))

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
        self.statusBar().showMessage(self._t("status_action_denied"), 5000)
        self._continue_after_action(self.service.mark_action_denied(self.pending_action_id))

    def _start_action_execution(self, action: AssistantAction) -> None:
        self._refresh_activity_chip("executing")
        self.statusBar().showMessage(self._t("status_executing_action"))
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
            self.statusBar().showMessage(self._t("status_action_completed"), 5000)
            self._continue_after_action(self.service.mark_action_executed(self.pending_action_id, result_text))

    def _handle_action_failed(self, error: str) -> None:
        if self.pending_action_id is not None:
            self.statusBar().showMessage(self._t("status_action_failed"), 5000)
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
        if self._updating_form:
            return
        try:
            self.settings = self._collect_settings_from_form()
            self.state.settings = self.settings
            self.service.save_settings(self.settings)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Unable to persist settings")
            self._show_error(self._t("settings_title"), exc)

    def _collect_settings_from_form(self) -> AppSettings:
        provider_configs = {provider_id: dict(value) for provider_id, value in self.settings.provider_configs.items()}
        if self._rendered_provider_id:
            provider_configs.setdefault(self._rendered_provider_id, {})
            for name, widget in self.provider_config_inputs.items():
                provider_configs[self._rendered_provider_id][name] = widget.text().strip()
        allowlist = [item.strip() for item in self.command_allowlist_input.text().replace("\n", ",").split(",") if item.strip()]
        return AppSettings(
            provider_id=self._selected_provider_id(),
            model=self.model_combo.currentText().strip(),
            system_prompt=self.system_prompt_input.toPlainText().strip(),
            language=self._selected_language(),
            temperature=self.temperature_input.value(),
            top_p=self.top_p_input.value(),
            max_tokens=self.max_tokens_input.value(),
            last_conversation_id=self.current_conversation_id,
            provider_configs=provider_configs,
            web_enabled=self.web_enabled_checkbox.isChecked(),
            files_enabled=self.files_enabled_checkbox.isChecked(),
            commands_enabled=self.commands_enabled_checkbox.isChecked(),
            require_confirmation=self.require_confirmation_checkbox.isChecked(),
            command_allowlist=allowlist,
        )

    def _refresh_runtime_state(self) -> None:
        self._persist_settings()
        self._populate_models()
        self._refresh_health_banner()
        self.statusBar().showMessage(self._t("status_runtime_refreshed"), 5000)

    def _refresh_health_banner(self) -> None:
        try:
            health = self.service.get_provider_health(self._selected_provider_id(), self.model_combo.currentText().strip())
        except Exception as exc:  # noqa: BLE001
            health = ProviderHealth(status="error", detail=str(exc))
        self._apply_health(health)

    def _apply_health(self, health: ProviderHealth) -> None:
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
        if health.detail:
            parts.append(health.detail)
        models = ", ".join(item.model_id for item in health.models[:5] if item.model_id)
        if models:
            parts.append(f"{self._t('health_models_available')}: {models}")
        self.health_banner.setText(" ".join(parts))

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
        self.statusBar().showMessage(str(destination), 5000)

    def _render_messages(self, messages: list[MessageRecord]) -> None:
        if not messages:
            self.chat_view.setHtml(
                f"<div style='margin-top:94px;padding:0 28px;text-align:center;color:#4f6886;'><div style='display:inline-block;max-width:520px;background:rgba(255,255,255,0.72);border:1px solid rgba(214,226,239,0.9);border-radius:26px;padding:26px 30px;box-shadow:0 24px 40px rgba(15,23,42,0.08);'><h2 style='font-size:29px;margin:0 0 12px 0;color:#102033;'>{html.escape(self._t('chat_empty_title'))}</h2><p style='font-size:15px;line-height:1.6;margin:0;'>{html.escape(self._t('chat_empty_body'))}</p></div></div>"
            )
            return
        blocks = ["<html><body style=\"font-family:'Segoe UI Variable'; background:transparent; color:#102033; margin:0;\">"]
        for message in messages:
            is_user = message.role == "user"
            bubble_bg = "rgba(20, 42, 71, 0.92)" if is_user else "rgba(255, 255, 255, 0.84)"
            text_color = "#edf5ff" if is_user else "#102033"
            label_color = "#c9ddff" if is_user else "#5b6f88"
            border = "1px solid rgba(255,255,255,0.12)" if is_user else "1px solid rgba(205,218,234,0.86)"
            align = "right" if is_user else "left"
            status_suffix = ""
            if message.status in {"failed", "cancelled"} and message.error:
                status_suffix = f"<div style='font-size:12px;color:#b42318;margin-top:6px;'>{html.escape(message.error)}</div>"
            blocks.append(
                f"<div style='text-align:{align};margin:14px 0;'><div style='display:inline-block;max-width:78%;background:{bubble_bg};color:{text_color};border:{border};border-radius:22px;padding:15px 18px;box-shadow:0 16px 28px rgba(15,23,42,0.08);'><div style='font-size:12px;color:{label_color};margin-bottom:8px;font-weight:600;'>{html.escape(self._role_label(message.role))}</div><div style='white-space:pre-wrap;font-size:14px;line-height:1.58;'>{html.escape(message.content) or '&nbsp;'}</div>{status_suffix}</div></div>"
            )
        blocks.append("</body></html>")
        self.chat_view.setHtml("".join(blocks))
        scrollbar = self.chat_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _refresh_activity_chip(self, mode: str) -> None:
        self._status_mode = mode
        object_name, text = {
            "ready": ("StatusChipReady", self._t("status_ready")),
            "busy": ("StatusChipBusy", self._t("status_generating")),
            "waiting": ("StatusChipWarning", self._t("status_waiting_approval")),
            "executing": ("StatusChipBusy", self._t("status_executing_action")),
        }[mode]
        self.status_chip.setObjectName(object_name)
        self.status_chip.setText(text)
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)

    def _update_interaction_state(self) -> None:
        generating = self.generation_worker is not None
        executing = self.action_worker is not None
        waiting = self.pending_action_id is not None and not executing
        locked = generating or executing or waiting
        export_enabled = self.current_conversation_id is not None and not generating and not executing
        for widget, enabled in (
            (self.send_button, not locked),
            (self.cancel_button, generating),
            (self.new_chat_button, not locked),
            (self.regenerate_button, not locked and self.current_conversation_id is not None),
            (self.export_md_button, export_enabled),
            (self.export_json_button, export_enabled),
            (self.composer, not locked),
            (self.provider_combo, not locked),
            (self.model_combo, not locked),
            (self.language_combo, not locked),
            (self.refresh_button, not locked),
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
            (self.allow_button, waiting),
            (self.deny_button, waiting),
        ):
            widget.setEnabled(enabled)
        for widget in self.provider_config_inputs.values():
            widget.setEnabled(not locked)
        self.main_stack.setCurrentWidget(self.approval_page if self.pending_action_id else self.chat_page)

    def _provider_description(self, provider_id: str) -> str:
        descriptor = self._provider_descriptors.get(provider_id)
        return self._t(descriptor.description_key) if descriptor else ""

    def _role_label(self, role: str) -> str:
        return {"system": self._t("role_system"), "user": self._t("role_user"), "assistant": self._t("role_assistant")}.get(role, role)

    def _localized_action_kind(self, action_kind: str) -> str:
        return {"web_fetch": self._t("action_web_fetch"), "file_read": self._t("action_file_read"), "file_write": self._t("action_file_write"), "command_run": self._t("action_command_run")}.get(action_kind, action_kind)

    def _localized_risk(self, risk: str) -> str:
        return {"low": self._t("risk_low"), "medium": self._t("risk_medium"), "high": self._t("risk_high")}.get(risk, risk)

    def _selected_provider_id(self) -> str:
        provider_id = self.provider_combo.currentData()
        return provider_id if isinstance(provider_id, str) and provider_id else self.settings.provider_id

    def _selected_language(self) -> Language:
        language = self.language_combo.currentData()
        return language if language in {"en", "ru"} else self.localization.language

    def _is_locked(self) -> bool:
        return self.generation_worker is not None or self.action_worker is not None or self.pending_action_id is not None

    def _show_error(self, title: str, exc: Exception) -> None:
        LOGGER.exception(title, exc_info=exc)
        self._show_message_box(QMessageBox.Icon.Critical, title, str(exc))

    def _show_warning(self, title: str, message: str) -> None:
        self._show_message_box(QMessageBox.Icon.Warning, title, message)

    def _show_message_box(self, icon: QMessageBox.Icon, title: str, message: str) -> None:
        dialog = QMessageBox(self)
        dialog.setObjectName("GlassMessageBox")
        dialog.setWindowTitle(APP_NAME)
        dialog.setIcon(icon)
        dialog.setText(title)
        dialog.setInformativeText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

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

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        if self.generation_worker is not None:
            self.generation_worker.cancel()
            if self.generation_thread is not None:
                self.generation_thread.quit()
                self.generation_thread.wait(1500)
        if self.action_thread is not None:
            self.action_thread.quit()
            self.action_thread.wait(1500)
        event.accept()
