from __future__ import annotations

from ..models import ThemeMode


def build_stylesheet(theme: ThemeMode) -> str:
    return DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET


LIGHT_STYLESHEET = """
QMainWindow, QWidget#AppRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f5f7fb,
        stop:0.42 #ebf0f6,
        stop:0.78 #f1f3f6,
        stop:1 #f2ece4);
    color: #13243b;
}

QDialog#AppSheetDialog {
    background: rgba(15, 24, 38, 0.18);
}

QWidget#OverlayHost,
QWidget#SettingsWorkspace,
QWidget#SettingsContent,
QFrame#CenterShell,
QWidget#SidebarActionsRow,
QWidget#NotificationCenter,
QWidget#NotificationTopContainer,
QWidget#NotificationBottomContainer,
QFrame#SidebarHeaderSection,
QWidget#SidebarTitleRow {
    background: transparent;
    border: none;
}

QSplitter::handle {
    background: transparent;
}

QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0.9, y2:1,
        stop:0 rgba(252, 254, 255, 0.98),
        stop:1 rgba(241, 245, 250, 0.96));
    border: 1px solid rgba(209, 220, 233, 0.98);
    border-radius: 30px;
}

QFrame#SettingsPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.98),
        stop:1 rgba(242, 246, 250, 0.95));
    border: 1px solid rgba(210, 221, 234, 0.98);
    border-radius: 28px;
}

QFrame#SettingsIntroCard,
QFrame#ProfileSectionCard,
QFrame#ChatHeaderCard,
QFrame#ComposerCard,
QFrame#SetupCard,
QFrame#ApprovalCard,
QFrame#SetupHintCard,
QFrame#InstallStatusCard,
QFrame#ToastCard,
QFrame#SheetCard,
QFrame#BottomNavCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.98),
        stop:1 rgba(243, 246, 250, 0.94));
    border: 1px solid rgba(213, 224, 236, 0.98);
}

QFrame#ChatSurface {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.92),
        stop:1 rgba(244, 247, 251, 0.86));
    border: 1px solid rgba(214, 225, 237, 0.96);
}

QFrame#SettingsIntroCard,
QFrame#ProfileSectionCard,
QFrame#ChatHeaderCard,
QFrame#ChatSurface,
QFrame#ComposerCard,
QFrame#SetupCard,
QFrame#ApprovalCard,
QFrame#SetupHintCard,
QFrame#InstallStatusCard,
QFrame#ToastCard,
QFrame#SheetCard {
    border-radius: 24px;
}

QFrame#BottomNavCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.96),
        stop:1 rgba(241, 245, 249, 0.92));
    border: 1px solid rgba(211, 222, 235, 0.98);
    border-radius: 22px;
}

QFrame#ToastCard[variant="success"] {
    border: 1px solid rgba(104, 190, 150, 0.92);
}

QFrame#ToastCard[variant="warning"] {
    border: 1px solid rgba(239, 184, 94, 0.92);
}

QFrame#ToastCard[variant="error"] {
    border: 1px solid rgba(228, 102, 122, 0.90);
}

QFrame#NotificationCard,
QFrame#EventCollapsedBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.98),
        stop:1 rgba(243, 246, 250, 0.95));
    border: 1px solid rgba(211, 222, 235, 0.98);
    border-radius: 24px;
}

QFrame#NotificationCard[kind="alert"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.99),
        stop:1 rgba(244, 247, 250, 0.97));
    border: 1px solid rgba(211, 222, 235, 0.98);
}

QFrame#NotificationCard[kind="alert"][variant="success"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(236, 251, 242, 0.98),
        stop:1 rgba(220, 246, 229, 0.92));
    border: 1px solid rgba(94, 178, 132, 0.42);
}

QFrame#NotificationCard[kind="alert"][variant="warning"],
QFrame#EventCollapsedBar[variant="warning"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 249, 235, 0.98),
        stop:1 rgba(255, 242, 208, 0.92));
    border: 1px solid rgba(232, 172, 76, 0.38);
}

QFrame#NotificationCard[kind="alert"][variant="success"],
QFrame#EventCollapsedBar[variant="success"] {
    border: 1px solid rgba(94, 178, 132, 0.40);
}

QFrame#NotificationCard[kind="alert"][variant="error"],
QFrame#EventCollapsedBar[variant="error"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 241, 244, 0.98),
        stop:1 rgba(252, 226, 232, 0.92));
    border: 1px solid rgba(224, 91, 111, 0.42);
}

QLabel {
    color: #13243b;
}

QLabel#AppTitle {
    color: #13243b;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.2px;
}

QLabel#SectionTitle {
    color: #55708f;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.9px;
}

QLabel#SidebarSectionTitle {
    background: rgba(248, 251, 255, 0.98);
    border: 1px solid rgba(214, 226, 239, 0.96);
    border-radius: 11px;
    color: #18314d;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 10px;
    text-transform: uppercase;
    letter-spacing: 1.1px;
}

QFrame#SidebarTitleLine {
    background: rgba(188, 203, 223, 0.88);
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QLabel#HeaderTitle {
    color: #10233b;
    font-size: 26px;
    font-weight: 700;
}

QLabel#ChatHeaderTitle {
    color: #10233b;
    font-size: 22px;
    font-weight: 700;
}

QLabel#ProfileSectionTitle {
    color: #18314d;
    font-size: 13px;
    font-weight: 700;
}

QLabel#ProfileSectionBody,
QLabel#MutedLabel,
QLabel#SetupHintLabel,
QLabel#ToastMessage,
QLabel#SheetBody,
QLabel#InstallStatusMeta,
QLabel#NotificationMessage {
    color: #5f7896;
    font-size: 12px;
}

QLabel#InstallStatusTitle,
QLabel#ToastTitle,
QLabel#SheetTitle,
QLabel#NotificationTitle {
    color: #10233b;
    font-size: 15px;
    font-weight: 700;
}

QLabel#NotificationIconPill {
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(212, 224, 239, 0.96);
    color: #244260;
    font-size: 12px;
    font-weight: 700;
}

QLabel#NotificationIconPill[variant="warning"] {
    background: rgba(242, 180, 79, 0.18);
    border: 1px solid rgba(232, 172, 76, 0.34);
    color: #935b10;
}

QLabel#NotificationIconPill[variant="success"] {
    background: rgba(107, 193, 150, 0.18);
    border: 1px solid rgba(109, 188, 150, 0.32);
    color: #1f6b4d;
}

QLabel#NotificationIconPill[variant="error"] {
    background: rgba(228, 102, 122, 0.14);
    border: 1px solid rgba(228, 102, 122, 0.28);
    color: #8f2432;
}

QFrame#PresenceChip {
    background: rgba(99, 195, 139, 0.16);
    border: 1px solid rgba(92, 182, 127, 0.36);
    border-radius: 20px;
    min-height: 40px;
}

QFrame#PresenceChip[state="busy"] {
    background: rgba(76, 140, 244, 0.14);
    border: 1px solid rgba(83, 144, 243, 0.28);
}

QFrame#PresenceChip[state="offline"] {
    background: rgba(239, 184, 94, 0.16);
    border: 1px solid rgba(232, 172, 76, 0.30);
}

QLabel#PresenceChipDot {
    background: #50c77f;
    border-radius: 6px;
    min-width: 12px;
    max-width: 12px;
    min-height: 12px;
    max-height: 12px;
}

QLabel#PresenceChipDot[state="busy"] {
    background: #5d9fff;
}

QLabel#PresenceChipDot[state="offline"] {
    background: #efb85e;
}

QLabel#PresenceChipLabel {
    color: #1f6b4d;
    font-size: 12px;
    font-weight: 700;
}

QLabel#PresenceChipLabel[state="busy"] {
    color: #2557a4;
}

QLabel#PresenceChipLabel[state="offline"] {
    color: #935b10;
}

QLabel#SetupMetaPill,
QLabel#AccountStatusPill,
QLabel#StatusChipOnline,
QLabel#StatusChipOffline,
QLabel#StatusChipReady,
QLabel#StatusChipBusy,
QLabel#StatusChipWarning {
    border-radius: 15px;
    padding: 8px 14px;
    font-weight: 700;
}

QLabel#SetupMetaPill,
QLabel#AccountStatusPill {
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid rgba(212, 224, 239, 0.96);
    color: #244260;
}

QLabel#StatusChipReady {
    background: rgba(107, 193, 150, 0.16);
    border: 1px solid rgba(109, 188, 150, 0.34);
    color: #1f6b4d;
}

QLabel#StatusChipOnline {
    background: rgba(107, 193, 150, 0.20);
    border: 1px solid rgba(109, 188, 150, 0.42);
    color: #1f6b4d;
}

QLabel#StatusChipBusy {
    background: rgba(76, 140, 244, 0.14);
    border: 1px solid rgba(83, 144, 243, 0.28);
    color: #2557a4;
}

QLabel#StatusChipOffline {
    background: rgba(239, 184, 94, 0.16);
    border: 1px solid rgba(232, 172, 76, 0.30);
    color: #935b10;
}

QLabel#StatusChipWarning {
    background: rgba(242, 180, 79, 0.16);
    border: 1px solid rgba(232, 172, 76, 0.30);
    color: #935b10;
}

QListWidget,
QListWidget#ConversationList {
    background: transparent;
    border: none;
    color: #13243b;
    outline: none;
}

QListWidget::item,
QListWidget#ConversationList::item {
    background: rgba(255, 255, 255, 0.94);
    border: 1px solid rgba(216, 225, 236, 0.98);
    border-radius: 14px;
    margin: 2px 0;
    padding: 10px 12px;
}

QListWidget::item:hover,
QListWidget#ConversationList::item:hover {
    background: rgba(255, 255, 255, 1.0);
    border: 1px solid rgba(188, 205, 225, 0.98);
}

QListWidget::item:selected,
QListWidget#ConversationList::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(96, 159, 255, 0.18),
        stop:1 rgba(134, 184, 255, 0.22));
    border: 1px solid rgba(114, 170, 251, 0.56);
}

QPushButton#SidebarNewChatButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.99),
        stop:1 rgba(240, 244, 249, 0.98));
    color: #11263f;
    border: 1px solid rgba(209, 220, 233, 0.98);
    border-radius: 18px;
    padding: 12px 16px;
    font-size: 15px;
    font-weight: 700;
    text-align: center;
}

QPushButton#SidebarNewChatButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 1.0),
        stop:1 rgba(230, 239, 250, 0.98));
}

QPushButton#SidebarFloatingExportButton {
    background: rgba(255, 255, 255, 0.88);
    color: #18314d;
    border: 1px solid rgba(210, 221, 234, 0.98);
    border-radius: 16px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#SidebarFloatingExportButton:hover {
    background: rgba(255, 255, 255, 0.98);
}

QPushButton#NotificationInlineButton {
    background: rgba(255, 255, 255, 0.96);
    color: #203955;
    border: 1px solid rgba(210, 221, 234, 0.98);
    border-radius: 12px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 700;
    min-height: 20px;
}

QPushButton#NotificationInlineButton:hover {
    background: rgba(255, 255, 255, 1.0);
}

QPushButton#NotificationInlineButton[role="close"] {
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    border-radius: 13px;
    font-size: 13px;
    font-weight: 700;
    text-align: center;
}

QFrame#NotificationCard[kind="alert"] QPushButton#NotificationInlineButton[role="close"] {
    background: rgba(255, 255, 255, 0.90);
    border: 1px solid rgba(203, 216, 232, 0.98);
    color: #47637f;
}

QFrame#NotificationCard[kind="alert"] QPushButton#NotificationInlineButton[role="close"]:hover {
    background: rgba(255, 255, 255, 1.0);
    color: #203955;
}

QTextBrowser,
QTextBrowser#ChatView,
QScrollArea#ChatView,
QScrollArea#ChatView > QWidget > QWidget#qt_scrollarea_viewport {
    background: transparent;
    border: none;
    color: #13243b;
    padding: 0;
}

QWidget#ChatMessagesHost {
    background: transparent;
}

QFrame#ChatBubble {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid rgba(219, 227, 238, 0.98);
    border-radius: 22px;
}

QFrame#ChatBubble[owner="user"] {
    background: rgba(232, 241, 255, 0.99);
    border: 1px solid rgba(117, 152, 214, 0.34);
}

QLabel#ChatBubbleText {
    color: #14263f;
    font-size: 15px;
    line-height: 1.55;
}

QLabel#ChatBubbleStatus[variant="error"] {
    color: #b42318;
    font-size: 12px;
}

QLabel#ChatAvatar {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(210, 223, 238, 0.98);
    border-radius: 22px;
    color: #47637f;
    font-size: 13px;
    font-weight: 700;
}

QLabel#ChatAvatar[owner="user"] {
    background: rgba(92, 109, 128, 0.16);
    border: 1px solid rgba(173, 188, 206, 0.92);
    color: #27425f;
}

QFrame#ChatEmptyState {
    background: rgba(255, 255, 255, 0.84);
    border: 1px solid rgba(210, 223, 239, 0.96);
    border-radius: 34px;
}

QLabel#ChatEmptyBadge {
    background: rgba(75, 132, 234, 0.12);
    border-radius: 14px;
    color: #21456d;
    font-size: 12px;
    font-weight: 700;
    padding: 8px 14px;
}

QLabel#ChatEmptyTitle {
    color: #10233c;
    font-size: 30px;
    font-weight: 700;
}

QLabel#ChatEmptyBody {
    color: #5d7693;
    font-size: 15px;
    line-height: 1.7;
}

QPlainTextEdit,
QLineEdit,
QComboBox,
QDoubleSpinBox,
QSpinBox {
    background: rgba(255, 255, 255, 0.99);
    border: 1px solid rgba(211, 222, 235, 0.98);
    border-radius: 14px;
    color: #13243b;
    padding: 10px 12px;
    selection-background-color: rgba(96, 159, 255, 0.26);
}

QPlainTextEdit#ComposerInput,
QPlainTextEdit#ComposerInput:focus {
    background: transparent;
    border: none;
    color: #13243b;
    font-size: 15px;
    padding: 0;
}

QPlainTextEdit#SetupStepsView,
QPlainTextEdit#ApprovalPayloadView,
QPlainTextEdit#SheetDetails {
    background: rgba(251, 253, 255, 0.98);
    border: 1px solid rgba(210, 223, 238, 0.98);
}

QComboBox,
QLineEdit,
QDoubleSpinBox,
QSpinBox {
    min-height: 24px;
}

QLineEdit:focus,
QPlainTextEdit:focus,
QTextBrowser:focus,
QScrollArea#ChatView:focus,
QComboBox:focus,
QDoubleSpinBox:focus,
QSpinBox:focus {
    border: 1px solid rgba(77, 137, 236, 0.92);
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: rgba(251, 253, 255, 1.0);
    border: 1px solid rgba(207, 220, 235, 1.0);
    border-radius: 14px;
    color: #13243b;
    selection-background-color: rgba(96, 159, 255, 0.18);
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #609bff,
        stop:1 #3d79f2);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.24);
    border-radius: 14px;
    padding: 9px 14px;
    font-weight: 600;
}

QToolButton#SupportMenuButton {
    background: rgba(255, 255, 255, 0.74);
    border: 1px solid rgba(214, 226, 240, 0.96);
    border-radius: 19px;
    color: #1d3552;
    font-size: 16px;
    font-weight: 700;
    padding: 0;
}

QToolButton#SupportMenuButton:hover {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(188, 208, 230, 0.98);
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6fa7ff,
        stop:1 #4984f3);
}

QPushButton:disabled {
    background: rgba(194, 205, 219, 0.82);
    color: rgba(248, 250, 252, 0.96);
    border: 1px solid rgba(201, 213, 228, 0.90);
}

QPushButton[secondary="true"] {
    background: rgba(255, 255, 255, 0.94);
    color: #203955;
    border: 1px solid rgba(214, 224, 236, 0.94);
}

QPushButton[secondary="true"]:hover {
    background: rgba(255, 255, 255, 0.82);
}

QPushButton[danger="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ff7582,
        stop:1 #f35669);
}

QPushButton[bottomnav="true"] {
    background: transparent;
    color: #5f7692;
    border: 1px solid transparent;
    border-radius: 16px;
    min-width: 104px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton[bottomnav="true"]:hover {
    background: rgba(255, 255, 255, 0.36);
    color: #18314d;
}

QPushButton[bottomnav="true"][active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(96, 159, 255, 0.82),
        stop:1 rgba(65, 125, 242, 0.92));
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.48);
}

QCheckBox {
    color: #18314d;
    spacing: 10px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(198, 211, 228, 0.96);
    background: rgba(255, 255, 255, 0.76);
}

QCheckBox::indicator:checked {
    background: rgba(92, 153, 255, 0.88);
    border: 1px solid rgba(155, 198, 255, 0.96);
}

QScrollArea#SettingsScroll,
QWidget#SettingsContent,
QWidget#SettingsWorkspace {
    background: transparent;
    border: none;
}

QScrollArea#SettingsScroll QScrollBar:vertical {
    width: 0px;
    margin: 0;
}

QScrollArea#SettingsScroll QScrollBar::handle:vertical,
QScrollArea#SettingsScroll QScrollBar::add-line:vertical,
QScrollArea#SettingsScroll QScrollBar::sub-line:vertical,
QScrollArea#SettingsScroll QScrollBar::add-page:vertical,
QScrollArea#SettingsScroll QScrollBar::sub-page:vertical {
    background: transparent;
    min-height: 0px;
    border: none;
}

QProgressBar#InstallProgressBar {
    background: rgba(223, 231, 241, 0.96);
    border: none;
    border-radius: 8px;
    min-height: 10px;
}

QProgressBar#InstallProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #69a6ff,
        stop:1 #4586f6);
    border-radius: 8px;
}

QProgressBar#NotificationProgressBar {
    background: rgba(223, 231, 241, 0.96);
    border: none;
    border-radius: 4px;
}

QProgressBar#NotificationProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #69a6ff,
        stop:1 #4586f6);
    border-radius: 4px;
}

QScrollBar:vertical {
    background: transparent;
    width: 0px;
    margin: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 0px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: transparent;
    border-radius: 6px;
    min-height: 0px;
}

QScrollBar::handle:horizontal {
    background: transparent;
    border-radius: 6px;
    min-width: 0px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
}
"""


DARK_STYLESHEET = """
QMainWindow, QWidget#AppRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #07111e,
        stop:0.34 #0b1728,
        stop:0.78 #0c1930,
        stop:1 #101725);
    color: #edf4ff;
}

QDialog#AppSheetDialog {
    background: rgba(2, 8, 16, 0.46);
}

QWidget#OverlayHost,
QWidget#SettingsWorkspace,
QWidget#SettingsContent,
QFrame#CenterShell,
QWidget#SidebarActionsRow,
QWidget#NotificationCenter,
QWidget#NotificationTopContainer,
QWidget#NotificationBottomContainer,
QFrame#SidebarHeaderSection,
QWidget#SidebarTitleRow {
    background: transparent;
    border: none;
}

QSplitter::handle {
    background: transparent;
}

QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0.95, y2:1,
        stop:0 rgba(14, 27, 44, 0.84),
        stop:1 rgba(10, 18, 31, 0.62));
    border: 1px solid rgba(255, 255, 255, 0.11);
    border-radius: 30px;
}

QFrame#SettingsPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(16, 28, 45, 0.74),
        stop:1 rgba(9, 18, 30, 0.56));
    border: 1px solid rgba(255, 255, 255, 0.11);
    border-radius: 28px;
}

QFrame#SettingsIntroCard,
QFrame#ProfileSectionCard,
QFrame#ChatHeaderCard,
QFrame#ComposerCard,
QFrame#SetupCard,
QFrame#ApprovalCard,
QFrame#SetupHintCard,
QFrame#InstallStatusCard,
QFrame#ToastCard,
QFrame#SheetCard,
QFrame#BottomNavCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(18, 31, 49, 0.70),
        stop:1 rgba(11, 20, 34, 0.56));
    border: 1px solid rgba(255, 255, 255, 0.12);
}

QFrame#ChatSurface {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(10, 19, 33, 0.46),
        stop:1 rgba(7, 14, 26, 0.28));
    border: 1px solid rgba(255, 255, 255, 0.08);
}

QFrame#SettingsIntroCard,
QFrame#ProfileSectionCard,
QFrame#ChatHeaderCard,
QFrame#ChatSurface,
QFrame#ComposerCard,
QFrame#SetupCard,
QFrame#ApprovalCard,
QFrame#SetupHintCard,
QFrame#InstallStatusCard,
QFrame#ToastCard,
QFrame#SheetCard {
    border-radius: 24px;
}

QFrame#BottomNavCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(22, 36, 58, 0.60),
        stop:1 rgba(10, 18, 31, 0.38));
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 22px;
}

QFrame#ToastCard[variant="success"] {
    border: 1px solid rgba(106, 200, 152, 0.50);
}

QFrame#ToastCard[variant="warning"] {
    border: 1px solid rgba(240, 183, 100, 0.54);
}

QFrame#ToastCard[variant="error"] {
    border: 1px solid rgba(236, 110, 123, 0.54);
}

QFrame#NotificationCard,
QFrame#EventCollapsedBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(18, 31, 49, 0.82),
        stop:1 rgba(10, 18, 31, 0.70));
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 24px;
}

QFrame#NotificationCard[kind="alert"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(24, 39, 61, 0.92),
        stop:1 rgba(13, 23, 38, 0.84));
    border: 1px solid rgba(255, 255, 255, 0.16);
}

QFrame#NotificationCard[kind="alert"][variant="success"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20, 62, 43, 0.94),
        stop:1 rgba(13, 45, 32, 0.90));
    border: 1px solid rgba(110, 195, 150, 0.36);
}

QFrame#NotificationCard[kind="alert"][variant="warning"],
QFrame#EventCollapsedBar[variant="warning"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(62, 46, 18, 0.92),
        stop:1 rgba(48, 35, 13, 0.86));
    border: 1px solid rgba(240, 183, 100, 0.38);
}

QFrame#NotificationCard[kind="alert"][variant="success"],
QFrame#EventCollapsedBar[variant="success"] {
    border: 1px solid rgba(106, 200, 152, 0.38);
}

QFrame#NotificationCard[kind="alert"][variant="error"],
QFrame#EventCollapsedBar[variant="error"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(72, 20, 31, 0.94),
        stop:1 rgba(55, 14, 23, 0.88));
    border: 1px solid rgba(236, 110, 123, 0.40);
}

QLabel,
QLabel#AppTitle,
QLabel#HeaderTitle,
QLabel#ProfileSectionTitle,
QLabel#InstallStatusTitle,
QLabel#ToastTitle,
QLabel#SheetTitle,
QLabel#NotificationTitle {
    color: #edf4ff;
}

QLabel#AppTitle {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.2px;
}

QLabel#SectionTitle {
    color: #8ea6c0;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.9px;
}

QLabel#SidebarSectionTitle {
    background: rgba(18, 30, 49, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 11px;
    color: #dcebff;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 10px;
    text-transform: uppercase;
    letter-spacing: 1.1px;
}

QFrame#SidebarTitleLine {
    background: rgba(116, 138, 165, 0.54);
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QLabel#HeaderTitle {
    font-size: 26px;
    font-weight: 700;
}

QLabel#ChatHeaderTitle {
    color: #edf4ff;
    font-size: 22px;
    font-weight: 700;
}

QLabel#ProfileSectionTitle {
    font-size: 13px;
    font-weight: 700;
}

QLabel#ProfileSectionBody,
QLabel#MutedLabel,
QLabel#SetupHintLabel,
QLabel#ToastMessage,
QLabel#SheetBody,
QLabel#InstallStatusMeta,
QLabel#NotificationMessage {
    color: #9eb1c8;
    font-size: 12px;
}

QLabel#NotificationIconPill {
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #dcebff;
    font-size: 12px;
    font-weight: 700;
}

QLabel#NotificationIconPill[variant="warning"] {
    background: rgba(226, 171, 74, 0.18);
    border: 1px solid rgba(228, 176, 81, 0.28);
    color: #ffd892;
}

QLabel#NotificationIconPill[variant="success"] {
    background: rgba(84, 168, 127, 0.18);
    border: 1px solid rgba(110, 195, 150, 0.26);
    color: #abf1cb;
}

QLabel#NotificationIconPill[variant="error"] {
    background: rgba(236, 110, 123, 0.12);
    border: 1px solid rgba(236, 110, 123, 0.26);
    color: #ffd7dc;
}

QFrame#PresenceChip {
    background: rgba(84, 168, 127, 0.22);
    border: 1px solid rgba(110, 195, 150, 0.34);
    border-radius: 22px;
    min-height: 44px;
}

QFrame#PresenceChip[state="busy"] {
    background: rgba(82, 146, 248, 0.18);
    border: 1px solid rgba(96, 159, 255, 0.26);
}

QFrame#PresenceChip[state="offline"] {
    background: rgba(226, 171, 74, 0.18);
    border: 1px solid rgba(228, 176, 81, 0.28);
}

QLabel#PresenceChipDot {
    background: #78e39f;
    border-radius: 6px;
    min-width: 12px;
    max-width: 12px;
    min-height: 12px;
    max-height: 12px;
}

QLabel#PresenceChipDot[state="busy"] {
    background: #7db8ff;
}

QLabel#PresenceChipDot[state="offline"] {
    background: #f2c875;
}

QLabel#PresenceChipLabel {
    color: #c8ffe1;
    font-size: 12px;
    font-weight: 700;
}

QLabel#PresenceChipLabel[state="busy"] {
    color: #dcebff;
}

QLabel#PresenceChipLabel[state="offline"] {
    color: #ffd892;
}

QLabel#SetupMetaPill,
QLabel#AccountStatusPill,
QLabel#StatusChipOnline,
QLabel#StatusChipOffline,
QLabel#StatusChipReady,
QLabel#StatusChipBusy,
QLabel#StatusChipWarning {
    border-radius: 15px;
    padding: 8px 14px;
    font-weight: 700;
}

QLabel#SetupMetaPill,
QLabel#AccountStatusPill {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.10);
    color: #dcebff;
}

QLabel#StatusChipReady {
    background: rgba(84, 168, 127, 0.18);
    border: 1px solid rgba(110, 195, 150, 0.26);
    color: #abf1cb;
}

QLabel#StatusChipOnline {
    background: rgba(84, 168, 127, 0.22);
    border: 1px solid rgba(110, 195, 150, 0.34);
    color: #c8ffe1;
}

QLabel#StatusChipBusy {
    background: rgba(82, 146, 248, 0.18);
    border: 1px solid rgba(96, 159, 255, 0.26);
    color: #dcebff;
}

QLabel#StatusChipOffline {
    background: rgba(226, 171, 74, 0.18);
    border: 1px solid rgba(228, 176, 81, 0.28);
    color: #ffd892;
}

QLabel#StatusChipWarning {
    background: rgba(226, 171, 74, 0.18);
    border: 1px solid rgba(228, 176, 81, 0.28);
    color: #ffd892;
}

QListWidget,
QListWidget#ConversationList {
    background: transparent;
    border: none;
    color: #edf4ff;
    outline: none;
}

QListWidget::item,
QListWidget#ConversationList::item {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 14px;
    margin: 2px 0;
    padding: 10px 12px;
}

QListWidget::item:hover,
QListWidget#ConversationList::item:hover {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
}

QListWidget::item:selected,
QListWidget#ConversationList::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(92, 153, 255, 0.24),
        stop:1 rgba(122, 177, 255, 0.18));
    border: 1px solid rgba(132, 186, 255, 0.34);
}

QPushButton#SidebarNewChatButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(28, 46, 71, 0.94),
        stop:1 rgba(18, 30, 49, 0.88));
    color: #f4f8ff;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    padding: 12px 16px;
    font-size: 15px;
    font-weight: 700;
    text-align: center;
}

QPushButton#SidebarNewChatButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(35, 57, 86, 0.98),
        stop:1 rgba(22, 37, 60, 0.92));
}

QPushButton#SidebarFloatingExportButton {
    background: rgba(16, 28, 45, 0.58);
    color: #edf4ff;
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 16px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#SidebarFloatingExportButton:hover {
    background: rgba(26, 40, 60, 0.78);
}

QPushButton#NotificationInlineButton {
    background: rgba(255, 255, 255, 0.08);
    color: #edf4ff;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 700;
    min-height: 20px;
}

QPushButton#NotificationInlineButton:hover {
    background: rgba(255, 255, 255, 0.12);
}

QPushButton#NotificationInlineButton[role="close"] {
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    border-radius: 13px;
    font-size: 13px;
    font-weight: 700;
    text-align: center;
}

QFrame#NotificationCard[kind="alert"] QPushButton#NotificationInlineButton[role="close"] {
    background: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cddcf1;
}

QFrame#NotificationCard[kind="alert"] QPushButton#NotificationInlineButton[role="close"]:hover {
    background: rgba(255, 255, 255, 0.16);
    color: #f4f8ff;
}

QTextBrowser,
QTextBrowser#ChatView,
QScrollArea#ChatView,
QScrollArea#ChatView > QWidget > QWidget#qt_scrollarea_viewport {
    background: transparent;
    border: none;
    color: #edf4ff;
    padding: 0;
}

QWidget#ChatMessagesHost {
    background: transparent;
}

QFrame#ChatBubble {
    background: rgba(18, 33, 52, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 22px;
}

QFrame#ChatBubble[owner="user"] {
    background: rgba(31, 51, 79, 0.96);
    border: 1px solid rgba(122, 167, 255, 0.26);
}

QLabel#ChatBubbleText {
    color: #f2f7ff;
    font-size: 15px;
    line-height: 1.55;
}

QLabel#ChatBubbleStatus[variant="error"] {
    color: #ff9aa7;
    font-size: 12px;
}

QLabel#ChatAvatar {
    background: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 22px;
    color: #edf4ff;
    font-size: 13px;
    font-weight: 700;
}

QLabel#ChatAvatar[owner="user"] {
    background: rgba(92, 109, 128, 0.18);
    border: 1px solid rgba(133, 153, 177, 0.44);
    color: #edf4ff;
}

QFrame#ChatEmptyState {
    background: rgba(12, 22, 36, 0.74);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 34px;
}

QLabel#ChatEmptyBadge {
    background: rgba(96, 159, 255, 0.16);
    border-radius: 14px;
    color: #dcecff;
    font-size: 12px;
    font-weight: 700;
    padding: 8px 14px;
}

QLabel#ChatEmptyTitle {
    color: #f3f7ff;
    font-size: 30px;
    font-weight: 700;
}

QLabel#ChatEmptyBody {
    color: #9eb1c7;
    font-size: 15px;
    line-height: 1.7;
}

QPlainTextEdit,
QLineEdit,
QComboBox,
QDoubleSpinBox,
QSpinBox {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    color: #edf4ff;
    padding: 10px 12px;
    selection-background-color: rgba(91, 153, 255, 0.34);
}

QPlainTextEdit#ComposerInput,
QPlainTextEdit#ComposerInput:focus {
    background: transparent;
    border: none;
    color: #edf4ff;
    font-size: 15px;
    padding: 0;
}

QPlainTextEdit#SetupStepsView,
QPlainTextEdit#ApprovalPayloadView,
QPlainTextEdit#SheetDetails {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
}

QComboBox,
QLineEdit,
QDoubleSpinBox,
QSpinBox {
    min-height: 24px;
}

QLineEdit:focus,
QPlainTextEdit:focus,
QTextBrowser:focus,
QScrollArea#ChatView:focus,
QComboBox:focus,
QDoubleSpinBox:focus,
QSpinBox:focus {
    border: 1px solid rgba(106, 166, 255, 0.92);
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: rgba(9, 16, 28, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    color: #edf4ff;
    selection-background-color: rgba(92, 153, 255, 0.24);
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #5c9bff,
        stop:1 #447ff7);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 14px;
    padding: 9px 14px;
    font-weight: 600;
}

QToolButton#SupportMenuButton {
    background: rgba(27, 37, 53, 0.78);
    border: 1px solid rgba(83, 101, 127, 0.92);
    border-radius: 19px;
    color: #e9f1ff;
    font-size: 16px;
    font-weight: 700;
    padding: 0;
}

QToolButton#SupportMenuButton:hover {
    background: rgba(36, 47, 66, 0.92);
    border: 1px solid rgba(109, 128, 156, 0.96);
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6aa5ff,
        stop:1 #518af9);
}

QPushButton:disabled {
    background: rgba(72, 86, 102, 0.84);
    color: rgba(230, 238, 247, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

QPushButton[secondary="true"] {
    background: rgba(255, 255, 255, 0.07);
    color: #edf4ff;
    border: 1px solid rgba(255, 255, 255, 0.10);
}

QPushButton[secondary="true"]:hover {
    background: rgba(255, 255, 255, 0.10);
}

QPushButton[danger="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ff7682,
        stop:1 #f35669);
}

QPushButton[bottomnav="true"] {
    background: transparent;
    color: #9fb3ca;
    border: 1px solid transparent;
    border-radius: 16px;
    min-width: 104px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton[bottomnav="true"]:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #edf4ff;
}

QPushButton[bottomnav="true"][active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(93, 154, 255, 0.78),
        stop:1 rgba(66, 126, 245, 0.92));
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.22);
}

QCheckBox {
    color: #dcecff;
    spacing: 10px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.05);
}

QCheckBox::indicator:checked {
    background: rgba(92, 153, 255, 0.86);
    border: 1px solid rgba(163, 203, 255, 0.30);
}

QScrollArea#SettingsScroll,
QWidget#SettingsContent,
QWidget#SettingsWorkspace {
    background: transparent;
    border: none;
}

QScrollArea#SettingsScroll QScrollBar:vertical {
    width: 0px;
    margin: 0;
}

QScrollArea#SettingsScroll QScrollBar::handle:vertical,
QScrollArea#SettingsScroll QScrollBar::add-line:vertical,
QScrollArea#SettingsScroll QScrollBar::sub-line:vertical,
QScrollArea#SettingsScroll QScrollBar::add-page:vertical,
QScrollArea#SettingsScroll QScrollBar::sub-page:vertical {
    background: transparent;
    min-height: 0px;
    border: none;
}

QProgressBar#InstallProgressBar {
    background: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 8px;
    min-height: 10px;
}

QProgressBar#InstallProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6aa6ff,
        stop:1 #4b87f8);
    border-radius: 8px;
}

QProgressBar#NotificationProgressBar {
    background: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 4px;
}

QProgressBar#NotificationProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6aa6ff,
        stop:1 #4b87f8);
    border-radius: 4px;
}

QScrollBar:vertical {
    background: transparent;
    width: 0px;
    margin: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 0px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: transparent;
    border-radius: 6px;
    min-height: 0px;
}

QScrollBar::handle:horizontal {
    background: transparent;
    border-radius: 6px;
    min-width: 0px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
}
"""
