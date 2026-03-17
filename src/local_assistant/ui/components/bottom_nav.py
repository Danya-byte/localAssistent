from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSizePolicy, QWidget


class BottomNav(QFrame):
    chat_requested = Signal()
    profile_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomNavCard")
        self.setMaximumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._theme = "dark"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.chat_button = self._build_button()
        self.chat_button.clicked.connect(self.chat_requested.emit)

        self.profile_button = self._build_button()
        self.profile_button.clicked.connect(self.profile_requested.emit)

        layout.addWidget(self.chat_button)
        layout.addWidget(self.profile_button)

    def set_labels(self, chat_label: str, profile_label: str) -> None:
        self.chat_button.setText(chat_label)
        self.profile_button.setText(profile_label)
        self.adjustSize()

    def set_active(self, workspace: str) -> None:
        for button, active in (
            (self.chat_button, workspace == "chat"),
            (self.profile_button, workspace == "profile"),
        ):
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)
        self._update_icons()

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._update_icons()

    def _build_button(self) -> QPushButton:
        button = QPushButton()
        button.setProperty("bottomnav", True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(42)
        button.setMinimumWidth(110)
        button.setIconSize(QSize(18, 18))
        return button

    def _update_icons(self) -> None:
        icon_specs = (
            (self.chat_button, "chat"),
            (self.profile_button, "profile"),
        )
        for button, icon_kind in icon_specs:
            active = button.property("active") is True
            button.setIcon(self._make_icon(icon_kind, active))

    def _make_icon(self, icon_kind: str, active: bool) -> QIcon:
        color = self._icon_color(active)
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        if icon_kind == "chat":
            bubble_rect = QRectF(3.5, 4.0, 15.0, 11.0)
            bubble_path = QPainterPath()
            bubble_path.addRoundedRect(bubble_rect, 5.0, 5.0)
            painter.drawPath(bubble_path)
            painter.drawLine(QPointF(8.2, 14.3), QPointF(6.6, 17.5))
            painter.drawLine(QPointF(6.6, 17.5), QPointF(10.0, 15.8))
        else:
            painter.drawEllipse(QRectF(7.1, 3.6, 7.8, 7.8))
            shoulders = QPainterPath()
            shoulders.moveTo(4.4, 17.1)
            shoulders.cubicTo(5.9, 13.6, 8.3, 12.2, 11.0, 12.2)
            shoulders.cubicTo(13.7, 12.2, 16.1, 13.6, 17.6, 17.1)
            painter.drawPath(shoulders)

        painter.end()
        return QIcon(pixmap)

    def _icon_color(self, active: bool) -> QColor:
        if active:
            return QColor("#ffffff")
        if self._theme == "light":
            return QColor("#5f7692")
        return QColor("#a1b4cb")
