from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class SheetDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        body: str,
        details: str = "",
        confirm_text: str = "OK",
        cancel_text: str = "",
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AppSheetDialog")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Dialog, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        self.sheet_card = QFrame()
        self.sheet_card.setObjectName("SheetCard")
        card_layout = QVBoxLayout(self.sheet_card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(14)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("SheetTitle")
        card_layout.addWidget(self.title_label)

        self.body_label = QLabel(body)
        self.body_label.setObjectName("SheetBody")
        self.body_label.setWordWrap(True)
        card_layout.addWidget(self.body_label)

        self.details_view = QPlainTextEdit()
        self.details_view.setObjectName("SheetDetails")
        self.details_view.setReadOnly(True)
        self.details_view.setPlainText(details)
        self.details_view.setVisible(bool(details.strip()))
        self.details_view.setMinimumHeight(120)
        card_layout.addWidget(self.details_view)

        actions = QHBoxLayout()
        actions.addStretch(1)

        self.cancel_button = QPushButton(cancel_text or "")
        self.cancel_button.setProperty("secondary", True)
        self.cancel_button.setVisible(bool(cancel_text))
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)

        self.confirm_button = QPushButton(confirm_text)
        if danger:
            self.confirm_button.setProperty("danger", True)
        self.confirm_button.clicked.connect(self.accept)
        actions.addWidget(self.confirm_button)
        card_layout.addLayout(actions)

        layout.addStretch(1)
        layout.addWidget(self.sheet_card)
        layout.addStretch(1)

        self.resize(560, 360)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            parent_rect = parent.frameGeometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + parent_rect.height() - self.height() - 28
            self.move(x, y)
