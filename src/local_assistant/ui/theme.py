APP_STYLESHEET = """
QMainWindow, QWidget#AppRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f4fbff,
        stop:0.35 #edf4ff,
        stop:0.7 #eef5f3,
        stop:1 #f9f2ea);
    color: #102033;
}

QMenuBar {
    background: rgba(255, 255, 255, 0.44);
    border: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: 14px;
    color: #0f2136;
    margin: 0 12px 6px 12px;
    padding: 6px 8px;
}

QMenuBar::item {
    background: transparent;
    border-radius: 10px;
    padding: 6px 10px;
}

QMenuBar::item:selected {
    background: rgba(255, 255, 255, 0.7);
}

QMenu {
    background: rgba(247, 251, 255, 0.96);
    border: 1px solid rgba(184, 202, 222, 0.8);
    border-radius: 14px;
    color: #102033;
    padding: 8px;
}

QMenu::item {
    border-radius: 10px;
    padding: 8px 12px;
}

QMenu::item:selected {
    background: rgba(189, 224, 255, 0.44);
}

QStatusBar {
    background: rgba(255, 255, 255, 0.36);
    border-top: 1px solid rgba(255, 255, 255, 0.38);
    color: #19304b;
    padding: 4px 10px;
}

QSplitter::handle {
    background: transparent;
    width: 10px;
}

QFrame#Sidebar, QFrame#SettingsPanel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(16, 34, 58, 0.92),
        stop:1 rgba(10, 22, 40, 0.94));
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 28px;
}

QFrame#CenterShell {
    background: rgba(252, 254, 255, 0.36);
    border: 1px solid rgba(255, 255, 255, 0.5);
    border-radius: 28px;
}

QFrame#HeaderCard,
QFrame#ApprovalCard,
QFrame#ChatSurface,
QFrame#ComposerCard,
QFrame#SettingsIntroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.92),
        stop:1 rgba(245, 250, 255, 0.78));
    border: 1px solid rgba(255, 255, 255, 0.74);
    border-radius: 24px;
}

QFrame#ComposerCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 255, 255, 0.94),
        stop:1 rgba(235, 246, 255, 0.82));
}

QLabel#AppTitle {
    color: #f8fbff;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.4px;
}

QLabel#SectionTitle {
    color: #f3f8ff;
    font-size: 15px;
    font-weight: 600;
}

QLabel#HeaderTitle {
    color: #102033;
    font-size: 24px;
    font-weight: 700;
}

QLabel#StatusChipReady, QLabel#StatusChipBusy, QLabel#StatusChipWarning {
    border-radius: 14px;
    padding: 8px 14px;
    font-weight: 700;
    border: 1px solid rgba(255, 255, 255, 0.42);
}

QLabel#HealthBannerReady, QLabel#HealthBannerWarning, QLabel#HealthBannerError {
    border-radius: 18px;
    padding: 13px 16px;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.52);
}

QLabel#StatusChipReady {
    background: rgba(223, 245, 232, 0.92);
    color: #1d6040;
}

QLabel#StatusChipBusy {
    background: rgba(255, 236, 203, 0.94);
    color: #7d4c07;
}

QLabel#StatusChipWarning {
    background: rgba(255, 223, 218, 0.94);
    color: #8f2432;
}

QLabel#HealthBannerReady {
    background: rgba(226, 247, 235, 0.78);
    color: #205940;
}

QLabel#HealthBannerWarning {
    background: rgba(255, 241, 211, 0.78);
    color: #7b5514;
}

QLabel#HealthBannerError {
    background: rgba(255, 225, 225, 0.82);
    color: #8a2230;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4c8dff,
        stop:1 #3273f6);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 14px;
    padding: 11px 16px;
    font-weight: 700;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #5b99ff,
        stop:1 #3f7ef7);
}

QPushButton:pressed {
    padding-top: 12px;
}

QPushButton:disabled {
    background: rgba(188, 199, 214, 0.86);
    color: rgba(245, 247, 250, 0.9);
}

QPushButton[secondary="true"] {
    background: rgba(255, 255, 255, 0.76);
    color: #17304a;
    border: 1px solid rgba(184, 204, 228, 0.75);
}

QPushButton[secondary="true"]:hover {
    background: rgba(255, 255, 255, 0.9);
}

QPushButton[danger="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ff6d7b,
        stop:1 #f5506a);
}

QPushButton[danger="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ff7c88,
        stop:1 #f75e76);
}

QListWidget {
    background: transparent;
    color: #eef5ff;
    border: none;
    outline: none;
}

QListWidget::item {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid transparent;
    border-radius: 14px;
    margin: 5px 0;
    padding: 11px 12px;
}

QListWidget::item:selected {
    background: rgba(160, 205, 255, 0.18);
    border: 1px solid rgba(191, 224, 255, 0.34);
}

QTextBrowser,
QPlainTextEdit,
QLineEdit,
QComboBox,
QDoubleSpinBox,
QSpinBox {
    background: rgba(255, 255, 255, 0.74);
    border: 1px solid rgba(197, 212, 230, 0.85);
    border-radius: 16px;
    color: #102033;
    padding: 10px 12px;
    selection-background-color: rgba(76, 141, 255, 0.3);
}

QTextBrowser {
    padding: 16px;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: rgba(248, 251, 255, 0.98);
    border: 1px solid rgba(197, 212, 230, 0.88);
    border-radius: 12px;
    color: #102033;
    selection-background-color: rgba(189, 224, 255, 0.48);
}

QCheckBox {
    spacing: 10px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.38);
    background: rgba(255, 255, 255, 0.16);
}

QCheckBox::indicator:checked {
    background: rgba(118, 181, 255, 0.86);
    border: 1px solid rgba(194, 225, 255, 0.82);
}

QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 4px 0;
}

QScrollBar::handle:vertical {
    background: rgba(137, 164, 196, 0.48);
    border-radius: 6px;
    min-height: 28px;
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

QLabel {
    color: #102033;
}

QFrame#Sidebar QLabel,
QFrame#SettingsPanel QLabel,
QFrame#Sidebar QCheckBox,
QFrame#SettingsPanel QCheckBox {
    color: #eef6ff;
}

QFrame#SettingsIntroCard QLabel {
    color: #102033;
}

QFrame#SettingsPanel QPlainTextEdit,
QFrame#SettingsPanel QLineEdit,
QFrame#SettingsPanel QComboBox,
QFrame#SettingsPanel QDoubleSpinBox,
QFrame#SettingsPanel QSpinBox {
    background: rgba(255, 255, 255, 0.12);
    color: #f8fbff;
    border: 1px solid rgba(255, 255, 255, 0.18);
}

QFrame#SettingsPanel QComboBox QAbstractItemView {
    background: rgba(17, 32, 50, 0.98);
    color: #f8fbff;
    border: 1px solid rgba(255, 255, 255, 0.18);
}

QMessageBox#GlassMessageBox {
    background: rgba(248, 251, 255, 0.96);
}

QMessageBox#GlassMessageBox QLabel {
    color: #102033;
    min-width: 280px;
}
"""
