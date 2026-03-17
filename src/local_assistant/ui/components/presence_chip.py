from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy


class PresenceChip(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PresenceChip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 6, 11, 6)
        layout.setSpacing(7)

        self.dot = QLabel()
        self.dot.setObjectName("PresenceChipDot")
        self.dot.setFixedSize(12, 12)
        self.dot.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel()
        self.label.setObjectName("PresenceChipLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setMinimumWidth(98)
        self.setMaximumWidth(116)
        self.set_state("online", "Online")

    def set_state(self, state: str, text: str) -> None:
        if self.property("state") == state and self.label.text() == text:
            return
        self.setProperty("state", state)
        self.dot.setProperty("state", state)
        self.label.setProperty("state", state)
        self.label.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)
