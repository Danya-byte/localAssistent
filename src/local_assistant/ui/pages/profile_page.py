from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...config import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, DEFAULT_TOP_P
from ..components import SectionCard


class ProfilePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SettingsWorkspace")
        workspace_layout = QHBoxLayout(self)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setMinimumWidth(560)
        layout = QVBoxLayout(self.settings_panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.settings_intro_card = QFrame()
        self.settings_intro_card.setObjectName("SettingsIntroCard")
        intro_layout = QHBoxLayout(self.settings_intro_card)
        intro_layout.setContentsMargins(12, 12, 12, 12)
        intro_layout.setSpacing(10)

        self.profile_icon_label = QLabel()
        self.profile_icon_label.setObjectName("ProfileHeroIcon")
        self.profile_icon_label.setFixedSize(52, 52)
        self.profile_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro_layout.addWidget(self.profile_icon_label, 0, Qt.AlignmentFlag.AlignTop)

        intro_copy = QVBoxLayout()
        intro_copy.setContentsMargins(0, 0, 0, 0)
        intro_copy.setSpacing(8)

        self.settings_title_label = QLabel()
        self.settings_title_label.setObjectName("SectionTitle")
        self.provider_description_label = QLabel()
        self.provider_description_label.setObjectName("SectionTitle")
        self.provider_description_value = QLabel()
        self.provider_description_value.setWordWrap(True)

        intro_copy.addWidget(self.settings_title_label)
        intro_copy.addWidget(self.provider_description_label)
        intro_copy.addWidget(self.provider_description_value)
        intro_layout.addLayout(intro_copy, 1)

        self.support_menu_button = QToolButton()
        self.support_menu_button.setObjectName("SupportMenuButton")
        self.support_menu_button.setAutoRaise(False)
        self.support_menu_button.setFixedSize(38, 38)
        intro_layout.addWidget(self.support_menu_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.settings_intro_card)

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("SettingsScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.settings_content = QWidget()
        self.settings_content.setObjectName("SettingsContent")
        settings_content_layout = QVBoxLayout(self.settings_content)
        settings_content_layout.setContentsMargins(0, 0, 0, 88)
        settings_content_layout.setSpacing(10)

        self._build_form(settings_content_layout)
        self.settings_scroll.setWidget(self.settings_content)
        layout.addWidget(self.settings_scroll, 1)

        workspace_layout.addWidget(self.settings_panel, 1)

    def _build_form(self, layout: QVBoxLayout) -> None:
        self.assistant_card = SectionCard()
        self.assistant_title_label = self.assistant_card.title_label
        layout.addWidget(self.assistant_card)

        assistant_form = QFormLayout()
        assistant_form.setSpacing(8)
        assistant_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        assistant_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.default_source_label = QLabel()
        self.default_source_combo = QComboBox()
        self.default_source_combo.setMinimumWidth(160)
        self.provider_profile_label = QLabel()
        provider_row = QWidget()
        provider_row_layout = QHBoxLayout(provider_row)
        provider_row_layout.setContentsMargins(0, 0, 0, 0)
        provider_row_layout.setSpacing(8)

        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(180)
        self.refresh_button = QPushButton()
        self.refresh_button.setProperty("secondary", True)
        provider_row_layout.addWidget(self.provider_combo, 1)
        provider_row_layout.addWidget(self.refresh_button)

        self.model_profile_label = QLabel()
        model_row = QWidget()
        model_row_layout = QHBoxLayout(model_row)
        model_row_layout.setContentsMargins(0, 0, 0, 0)
        model_row_layout.setSpacing(8)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(220)
        model_row_layout.addWidget(self.model_combo, 1)

        self.system_prompt_label = QLabel()
        self.system_prompt_input = QPlainTextEdit()
        self.system_prompt_input.setFixedHeight(92)
        self.temperature_label = QLabel()
        self.temperature_input = QDoubleSpinBox()
        self.temperature_input.setRange(DEFAULT_TEMPERATURE, DEFAULT_TEMPERATURE)
        self.temperature_input.setValue(DEFAULT_TEMPERATURE)
        self.temperature_input.setReadOnly(True)
        self.temperature_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.top_p_label = QLabel()
        self.top_p_input = QDoubleSpinBox()
        self.top_p_input.setRange(DEFAULT_TOP_P, DEFAULT_TOP_P)
        self.top_p_input.setValue(DEFAULT_TOP_P)
        self.top_p_input.setReadOnly(True)
        self.top_p_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.max_tokens_label = QLabel()
        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(DEFAULT_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        self.max_tokens_input.setValue(DEFAULT_MAX_TOKENS)
        self.max_tokens_input.setReadOnly(True)
        self.max_tokens_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        assistant_form.addRow(self.default_source_label, self.default_source_combo)
        assistant_form.addRow(self.provider_profile_label, provider_row)
        assistant_form.addRow(self.model_profile_label, model_row)
        assistant_form.addRow(self.system_prompt_label, self.system_prompt_input)
        assistant_form.addRow(self.temperature_label, self.temperature_input)
        assistant_form.addRow(self.top_p_label, self.top_p_input)
        assistant_form.addRow(self.max_tokens_label, self.max_tokens_input)
        self.assistant_card.content_layout.addLayout(assistant_form)

        self.provider_card = SectionCard()
        self.provider_fields_title = self.provider_card.title_label
        layout.addWidget(self.provider_card)

        self.provider_form_host = QWidget()
        self.provider_form_layout = QFormLayout(self.provider_form_host)
        self.provider_form_layout.setSpacing(8)
        self.provider_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.provider_form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.provider_card.content_layout.addWidget(self.provider_form_host)

        self.api_card = SectionCard()
        self.api_title_label = self.api_card.title_label
        layout.addWidget(self.api_card)

        api_form = QFormLayout()
        api_form.setSpacing(8)
        api_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        api_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.api_model_label = QLabel()
        self.api_model_input = QLineEdit()
        self.reasoning_enabled_checkbox = QCheckBox()
        self.api_card.content_layout.addLayout(api_form)
        api_form.addRow(self.api_model_label, self.api_model_input)
        self.api_card.content_layout.addWidget(self.reasoning_enabled_checkbox)

        self.appearance_card = SectionCard()
        self.appearance_title_label = self.appearance_card.title_label
        layout.addWidget(self.appearance_card)

        appearance_form = QFormLayout()
        appearance_form.setSpacing(8)
        appearance_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.language_profile_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(132)
        self.theme_profile_label = QLabel()
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(132)
        appearance_form.addRow(self.language_profile_label, self.language_combo)
        appearance_form.addRow(self.theme_profile_label, self.theme_combo)
        self.appearance_card.content_layout.addLayout(appearance_form)

        self.local_models_card = SectionCard()
        self.local_models_title_label = self.local_models_card.title_label
        layout.addWidget(self.local_models_card)

        local_form = QFormLayout()
        local_form.setSpacing(8)
        local_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.local_model_label = QLabel()
        self.local_model_combo = QComboBox()
        self.local_model_combo.setMinimumWidth(220)
        self.local_model_status_label = QLabel()
        self.local_model_status_value = QLabel()
        self.local_model_status_value.setWordWrap(True)
        local_form.addRow(self.local_model_label, self.local_model_combo)
        local_form.addRow(self.local_model_status_label, self.local_model_status_value)
        self.local_models_card.content_layout.addLayout(local_form)

        local_actions = QHBoxLayout()
        local_actions.setContentsMargins(0, 0, 0, 0)
        local_actions.setSpacing(8)
        self.install_model_button = QPushButton()
        self.remove_model_button = QPushButton()
        self.remove_model_button.setProperty("secondary", True)
        local_actions.addWidget(self.install_model_button)
        local_actions.addWidget(self.remove_model_button)
        local_actions.addStretch(1)
        self.local_models_card.content_layout.addLayout(local_actions)

        self.updates_card = SectionCard()
        self.updates_title_label = self.updates_card.title_label
        layout.addWidget(self.updates_card)

        updates_form = QFormLayout()
        updates_form.setSpacing(8)
        updates_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.current_version_label = QLabel()
        self.current_version_value = QLabel()
        self.current_version_value.setObjectName("MutedLabel")
        self.update_status_label = QLabel()
        self.update_status_value = QLabel()
        self.update_status_value.setWordWrap(True)
        self.latest_version_label = QLabel()
        self.latest_version_value = QLabel()
        self.latest_version_value.setWordWrap(True)
        updates_form.addRow(self.current_version_label, self.current_version_value)
        updates_form.addRow(self.update_status_label, self.update_status_value)
        updates_form.addRow(self.latest_version_label, self.latest_version_value)
        self.updates_card.content_layout.addLayout(updates_form)

        updates_actions = QHBoxLayout()
        updates_actions.setContentsMargins(0, 0, 0, 0)
        updates_actions.setSpacing(8)
        self.open_release_button = QPushButton()
        self.open_release_button.setProperty("secondary", True)
        self.updates_refresh_button = QPushButton()
        self.updates_refresh_button.setProperty("secondary", True)
        updates_actions.addWidget(self.open_release_button)
        updates_actions.addWidget(self.updates_refresh_button)
        updates_actions.addStretch(1)
        self.updates_card.content_layout.addLayout(updates_actions)

        self.account_card = SectionCard()
        self.account_title_label = self.account_card.title_label
        layout.addWidget(self.account_card)
        self.telegram_status_label = QLabel()
        self.telegram_status_value = QLabel()
        self.telegram_status_value.setObjectName("AccountStatusPill")
        self.telegram_help_label = QLabel()
        self.telegram_help_label.setObjectName("MutedLabel")
        self.telegram_help_label.setWordWrap(True)
        self.account_card.content_layout.addWidget(self.telegram_status_label)
        self.account_card.content_layout.addWidget(self.telegram_status_value)
        self.account_card.content_layout.addWidget(self.telegram_help_label)

        self.permissions_card = SectionCard()
        self.permissions_title_label = self.permissions_card.title_label
        layout.addWidget(self.permissions_card)

        self.require_confirmation_checkbox = QCheckBox()
        self.web_enabled_checkbox = QCheckBox()
        self.files_enabled_checkbox = QCheckBox()
        self.commands_enabled_checkbox = QCheckBox()
        self.permissions_card.content_layout.addWidget(self.require_confirmation_checkbox)
        self.permissions_card.content_layout.addWidget(self.web_enabled_checkbox)
        self.permissions_card.content_layout.addWidget(self.files_enabled_checkbox)
        self.permissions_card.content_layout.addWidget(self.commands_enabled_checkbox)

        self.command_allowlist_label = QLabel()
        self.command_allowlist_input = QLineEdit()
        self.command_allowlist_input.setPlaceholderText("dir, echo, whoami")
        self.permissions_card.content_layout.addWidget(self.command_allowlist_label)
        self.permissions_card.content_layout.addWidget(self.command_allowlist_input)
        layout.addStretch(1)

    def apply_consumer_mode(self) -> None:
        for widget in (self.assistant_card, self.provider_card, self.api_card):
            widget.hide()
