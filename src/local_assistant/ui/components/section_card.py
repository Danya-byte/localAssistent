from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SectionCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ProfileSectionCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.title_label = QLabel()
        self.title_label.setObjectName("ProfileSectionTitle")
        layout.addWidget(self.title_label)

        self.description_label = QLabel()
        self.description_label.setObjectName("ProfileSectionBody")
        self.description_label.setWordWrap(True)
        self.description_label.hide()
        layout.addWidget(self.description_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        layout.addLayout(self.content_layout)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_description(self, text: str) -> None:
        self.description_label.setText(text)
        self.description_label.setVisible(bool(text.strip()))
