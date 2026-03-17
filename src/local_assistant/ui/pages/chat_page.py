from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..components.chat_layout import compute_chat_composer_geometry


class ComposerTextEdit(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._minimum_editor_height = 30
        self._maximum_editor_height = 104
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.textChanged.connect(self.sync_height_to_document)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.insertPlainText("\n")
                self.sync_height_to_document()
                return
            if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self.parent().window()._send_message()  # type: ignore[attr-defined]
                return
        super().keyPressEvent(event)

    def set_height_range(self, minimum_height: int, maximum_height: int) -> None:
        self._minimum_editor_height = minimum_height
        self._maximum_editor_height = maximum_height
        self.sync_height_to_document()

    def sync_height_to_document(self) -> None:
        document_height = self.document().documentLayout().documentSize().height()
        block_height = self.blockCount() * self.fontMetrics().lineSpacing()
        document_height = max(document_height, block_height)
        chrome_height = self.contentsMargins().top() + self.contentsMargins().bottom() + (self.frameWidth() * 2) + 4
        target_height = int(document_height + chrome_height)
        target_height = max(self._minimum_editor_height, min(target_height, self._maximum_editor_height))
        self.setFixedHeight(target_height)


class ChatWorkspace(QWidget):
    chat_composer_geometry_changed = Signal()

    SIDEBAR_EXPORT_SIDE_MARGIN = 14
    SIDEBAR_EXPORT_BOTTOM_MARGIN = 14
    SIDEBAR_EXPORT_MIN_WIDTH = 132
    SIDEBAR_EXPORT_VIEWPORT_INSET = 0
    SIDEBAR_BOTTOM_RESERVED = 86
    CHAT_COMPOSER_SIDE_MARGIN = 18
    CHAT_COMPOSER_MIN_WIDTH = 360
    CHAT_COMPOSER_MAX_WIDTH = 760
    CHAT_COMPOSER_MIN_BOTTOM_CLEARANCE = 14
    CHAT_VIEW_COMPOSER_GAP = 12

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ChatWorkspace")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.chat_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.chat_splitter.setObjectName("ChatSplitter")
        self.chat_splitter.setChildrenCollapsible(False)
        self.chat_splitter.setHandleWidth(6)
        layout.addWidget(self.chat_splitter, 1)

        self._build_sidebar()
        self._build_center()

        self.sidebar_panel.setMinimumWidth(220)
        self.sidebar_panel.setMaximumWidth(284)
        self.center_shell.setMinimumWidth(560)
        self.chat_splitter.setStretchFactor(0, 0)
        self.chat_splitter.setStretchFactor(1, 1)
        self.chat_splitter.setSizes([248, 1012])
        self.sidebar_panel.installEventFilter(self)
        self._chat_composer_bottom_clearance = self.CHAT_COMPOSER_MIN_BOTTOM_CLEARANCE
        self._chat_view_bottom_inset = 0
        self.chat_splitter.splitterMoved.connect(self._position_sidebar_export_button)
        self._position_sidebar_export_button()
        self._position_chat_composer_card()

    def _build_sidebar(self) -> None:
        self.sidebar_panel = QFrame()
        self.sidebar_panel.setObjectName("Sidebar")
        layout = QVBoxLayout(self.sidebar_panel)
        layout.setContentsMargins(14, 14, 14, self.SIDEBAR_BOTTOM_RESERVED)
        layout.setSpacing(12)

        self.sidebar_header_section = QFrame()
        self.sidebar_header_section.setObjectName("SidebarHeaderSection")
        header_layout = QVBoxLayout(self.sidebar_header_section)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.sidebar_title_row = QWidget()
        self.sidebar_title_row.setObjectName("SidebarTitleRow")
        title_row_layout = QHBoxLayout(self.sidebar_title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(10)

        self.sidebar_title_line_left = QFrame()
        self.sidebar_title_line_left.setObjectName("SidebarTitleLine")
        self.sidebar_title_line_left.setFrameShape(QFrame.Shape.HLine)
        self.sidebar_title_line_left.setFrameShadow(QFrame.Shadow.Plain)

        self.sidebar_title_label = QLabel()
        self.sidebar_title_label.setObjectName("SidebarSectionTitle")
        self.sidebar_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sidebar_title_line_right = QFrame()
        self.sidebar_title_line_right.setObjectName("SidebarTitleLine")
        self.sidebar_title_line_right.setFrameShape(QFrame.Shape.HLine)
        self.sidebar_title_line_right.setFrameShadow(QFrame.Shadow.Plain)

        title_row_layout.addWidget(self.sidebar_title_line_left, 1)
        title_row_layout.addWidget(self.sidebar_title_label, 0)
        title_row_layout.addWidget(self.sidebar_title_line_right, 1)

        self.new_chat_button = QPushButton()
        self.new_chat_button.setObjectName("SidebarNewChatButton")
        self.new_chat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_button.setMinimumHeight(46)

        header_layout.addWidget(self.sidebar_title_row)
        header_layout.addWidget(self.new_chat_button)

        self.conversation_list = QListWidget()
        self.conversation_list.setObjectName("ConversationList")
        self.conversation_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.conversation_list.setSpacing(2)
        self.conversation_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.conversation_list.setWordWrap(False)
        self.conversation_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.conversation_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.conversation_list.setViewportMargins(0, 0, 0, self.SIDEBAR_EXPORT_VIEWPORT_INSET)

        self.export_md_button = QPushButton(self.sidebar_panel)
        self.export_md_button.setObjectName("SidebarFloatingExportButton")
        self.export_md_button.setProperty("secondary", True)
        self.export_md_button.setMinimumHeight(38)
        self.export_md_button.raise_()

        layout.addWidget(self.sidebar_header_section)
        layout.addWidget(self.conversation_list, 1)

        self.chat_splitter.addWidget(self.sidebar_panel)

    def _position_sidebar_export_button(self) -> None:
        if not hasattr(self, "export_md_button") or not hasattr(self, "sidebar_panel"):
            return
        button_height = self.export_md_button.sizeHint().height()
        side_margin = self.SIDEBAR_EXPORT_SIDE_MARGIN
        bottom_margin = self.SIDEBAR_EXPORT_BOTTOM_MARGIN
        width = max(self.SIDEBAR_EXPORT_MIN_WIDTH, self.sidebar_panel.width() - (side_margin * 2))
        y = max(side_margin, self.sidebar_panel.height() - button_height - bottom_margin)
        self.export_md_button.setGeometry(QRect(side_margin, y, width, button_height))
        self.export_md_button.raise_()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_sidebar_export_button()
        self._position_chat_composer_card()

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if watched is self.sidebar_panel and event.type() in {QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest}:
            self._position_sidebar_export_button()
        if watched is getattr(self, "chat_surface", None) and event.type() in {QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest}:
            self._position_chat_composer_card()
        return super().eventFilter(watched, event)

    def set_chat_composer_bottom_clearance(self, clearance: int) -> None:
        self._chat_composer_bottom_clearance = max(self.CHAT_COMPOSER_MIN_BOTTOM_CLEARANCE, clearance)
        self._position_chat_composer_card()

    def _position_chat_composer_card(self) -> None:
        if not hasattr(self, "chat_surface") or not hasattr(self, "composer_card"):
            return
        self.composer_card.adjustSize()
        height = self.composer_card.sizeHint().height()
        geometry = compute_chat_composer_geometry(
            surface_size=self.chat_surface.size(),
            composer_height=height,
            side_margin=self.CHAT_COMPOSER_SIDE_MARGIN,
            min_width=self.CHAT_COMPOSER_MIN_WIDTH,
            max_width=self.CHAT_COMPOSER_MAX_WIDTH,
            bottom_clearance=self._chat_composer_bottom_clearance,
        )
        if geometry is None:
            return
        previous_geometry = self.composer_card.geometry()
        previous_inset = self._chat_view_bottom_inset
        self.composer_card.setGeometry(geometry)
        overlap = max(0, self.chat_surface.height() - geometry.y())
        self._chat_view_bottom_inset = overlap + self.CHAT_VIEW_COMPOSER_GAP
        self.chat_view.setViewportMargins(0, 0, 0, self._chat_view_bottom_inset)
        self.composer_card.raise_()
        if geometry != previous_geometry or self._chat_view_bottom_inset != previous_inset:
            self.chat_composer_geometry_changed.emit()

    @property
    def chat_composer_geometry(self) -> QRect:
        return self.composer_card.geometry()

    @property
    def chat_view_bottom_inset(self) -> int:
        return self._chat_view_bottom_inset

    def _build_center(self) -> None:
        self.center_shell = QFrame()
        self.center_shell.setObjectName("CenterShell")
        layout = QVBoxLayout(self.center_shell)
        layout.setContentsMargins(8, 16, 16, 16)
        layout.setSpacing(12)

        self.main_stack = QStackedWidget()
        layout.addWidget(self.main_stack, 1)
        self._build_chat_page()
        self._build_setup_page()
        self._build_approval_page()

        self.chat_splitter.addWidget(self.center_shell)

    def _build_chat_page(self) -> None:
        self.chat_page = QWidget()
        layout = QVBoxLayout(self.chat_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.chat_header_card = QFrame()
        self.chat_header_card.setObjectName("ChatHeaderCard")
        header_layout = QHBoxLayout(self.chat_header_card)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(16)

        header_copy = QVBoxLayout()
        header_copy.setContentsMargins(0, 0, 0, 0)
        header_copy.setSpacing(4)
        self.chat_title = QLabel()
        self.chat_title.setObjectName("ChatHeaderTitle")
        self.chat_title.show()
        header_copy.addWidget(self.chat_title)
        header_layout.addLayout(header_copy, 1)

        self.chat_header_actions = QWidget()
        self.chat_header_actions.setObjectName("ChatHeaderActions")
        self.chat_header_actions_layout = QHBoxLayout(self.chat_header_actions)
        self.chat_header_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_header_actions_layout.setSpacing(10)

        self.chat_source_row = QWidget()
        self.chat_source_row.setObjectName("ChatSourceRow")
        source_row_layout = QHBoxLayout(self.chat_source_row)
        source_row_layout.setContentsMargins(0, 0, 0, 0)
        source_row_layout.setSpacing(8)
        self.chat_source_label = QLabel()
        self.chat_source_label.setObjectName("SectionTitle")
        self.chat_source_value = QLabel()
        self.chat_source_value.setObjectName("SetupMetaPill")
        self.chat_source_combo = QComboBox()
        self.chat_source_combo.setMinimumWidth(118)
        source_row_layout.addWidget(self.chat_source_label)
        source_row_layout.addWidget(self.chat_source_value)
        source_row_layout.addWidget(self.chat_source_combo)

        self.chat_header_actions_layout.addWidget(self.chat_source_row)
        header_layout.addWidget(self.chat_header_actions, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.chat_header_card)

        self.chat_surface = QFrame()
        self.chat_surface.setObjectName("ChatSurface")
        self.chat_surface.installEventFilter(self)
        chat_layout = QVBoxLayout(self.chat_surface)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self.chat_view = QScrollArea()
        self.chat_view.setObjectName("ChatView")
        self.chat_view.setWidgetResizable(True)
        self.chat_view.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_messages_host = QWidget()
        self.chat_messages_host.setObjectName("ChatMessagesHost")
        self.chat_messages_layout = QVBoxLayout(self.chat_messages_host)
        self.chat_messages_layout.setContentsMargins(0, 18, 0, 18)
        self.chat_messages_layout.setSpacing(0)
        self.chat_messages_layout.addStretch(1)
        self.chat_view.setWidget(self.chat_messages_host)
        chat_layout.addWidget(self.chat_view, 1)
        layout.addWidget(self.chat_surface, 1)

        self.composer_card = QFrame(self.chat_surface)
        self.composer_card.setObjectName("ComposerCard")
        composer_layout = QVBoxLayout(self.composer_card)
        composer_layout.setContentsMargins(10, 6, 10, 6)
        composer_layout.setSpacing(3)

        self.composer = ComposerTextEdit(self.composer_card)
        self.composer.setObjectName("ComposerInput")
        self.composer.set_height_range(30, 104)
        self.composer.sync_height_to_document()
        self.composer.textChanged.connect(self._position_chat_composer_card)

        self.send_button = QPushButton()
        self.send_button.hide()
        self.cancel_button = QPushButton()
        self.cancel_button.setProperty("secondary", True)
        self.regenerate_button = QPushButton()
        self.regenerate_button.setProperty("secondary", True)
        self.export_json_button = QPushButton()
        self.export_json_button.setProperty("secondary", True)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.regenerate_button)
        buttons.addWidget(self.export_json_button)

        composer_layout.addWidget(self.composer)
        composer_layout.addLayout(buttons)
        self.composer_card.raise_()

        self.main_stack.addWidget(self.chat_page)

    def _build_setup_page(self) -> None:
        self.setup_page = QWidget()
        page = QVBoxLayout(self.setup_page)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        self.setup_card = QFrame()
        self.setup_card.setObjectName("SetupCard")
        self.setup_card.setMaximumWidth(760)
        layout = QVBoxLayout(self.setup_card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        self.setup_title = QLabel()
        self.setup_title.setObjectName("HeaderTitle")
        self.setup_body = QLabel()
        self.setup_body.setWordWrap(True)
        self.setup_provider_summary = QLabel()
        self.setup_provider_summary.setObjectName("SetupMetaPill")
        self.setup_model_summary = QLabel()
        self.setup_model_summary.setObjectName("SetupMetaPill")

        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        meta_row.addWidget(self.setup_provider_summary)
        meta_row.addWidget(self.setup_model_summary)
        meta_row.addStretch(1)

        self.setup_steps_label = QLabel()
        self.setup_steps_label.setObjectName("SectionTitle")
        self.setup_steps_view = QPlainTextEdit()
        self.setup_steps_view.setObjectName("SetupStepsView")
        self.setup_steps_view.setReadOnly(True)
        self.setup_steps_view.setMinimumHeight(140)
        self.setup_hint_card = QFrame()
        self.setup_hint_card.setObjectName("SetupHintCard")
        hint_layout = QVBoxLayout(self.setup_hint_card)
        hint_layout.setContentsMargins(12, 10, 12, 10)
        hint_layout.setSpacing(0)
        self.setup_hint_label = QLabel()
        self.setup_hint_label.setObjectName("SetupHintLabel")
        self.setup_hint_label.setWordWrap(True)
        hint_layout.addWidget(self.setup_hint_label)
        self.setup_hint_card.hide()

        self.setup_refresh_button = QPushButton()
        self.setup_profile_button = QPushButton()
        self.setup_profile_button.setProperty("secondary", True)
        self.setup_copy_button = QPushButton()
        self.setup_copy_button.setProperty("secondary", True)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(self.setup_refresh_button)
        buttons.addWidget(self.setup_profile_button)
        buttons.addStretch(1)
        buttons.addWidget(self.setup_copy_button)

        layout.addWidget(self.setup_title)
        layout.addWidget(self.setup_body)
        layout.addLayout(meta_row)
        layout.addWidget(self.setup_steps_label)
        layout.addWidget(self.setup_steps_view)
        layout.addWidget(self.setup_hint_card)
        layout.addLayout(buttons)

        card_row = QHBoxLayout()
        card_row.setContentsMargins(0, 0, 0, 0)
        card_row.addStretch(1)
        card_row.addWidget(self.setup_card)
        card_row.addStretch(1)

        page.addStretch(1)
        page.addLayout(card_row)
        page.addStretch(1)
        self.main_stack.addWidget(self.setup_page)

    def _build_approval_page(self) -> None:
        self.approval_page = QWidget()
        page = QVBoxLayout(self.approval_page)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        self.approval_card = QFrame()
        self.approval_card.setObjectName("ApprovalCard")
        self.approval_card.setMaximumWidth(760)
        layout = QVBoxLayout(self.approval_card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

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
        self.approval_payload_view.setFixedHeight(220)
        self.allow_button = QPushButton()
        self.deny_button = QPushButton()
        self.deny_button.setProperty("danger", True)

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
        buttons.setSpacing(10)
        buttons.addWidget(self.allow_button)
        buttons.addWidget(self.deny_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        card_row = QHBoxLayout()
        card_row.setContentsMargins(0, 0, 0, 0)
        card_row.addStretch(1)
        card_row.addWidget(self.approval_card)
        card_row.addStretch(1)

        page.addStretch(1)
        page.addLayout(card_row)
        page.addStretch(1)
        self.main_stack.addWidget(self.approval_page)
