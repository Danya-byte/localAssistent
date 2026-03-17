from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QMargins, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem, QWidget


CONVERSATION_ID_ROLE = int(Qt.ItemDataRole.UserRole)
CONVERSATION_TITLE_ROLE = CONVERSATION_ID_ROLE + 1
CONVERSATION_TIMESTAMP_ROLE = CONVERSATION_ID_ROLE + 2


class ConversationListDelegate(QStyledItemDelegate):
    def __init__(self, timestamp_formatter: Callable[[object], str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.timestamp_formatter = timestamp_formatter
        self._title_font = QFont()
        self._title_font.setPointSize(10)
        self._title_font.setWeight(QFont.Weight.DemiBold)
        self._meta_font = QFont()
        self._meta_font.setPointSize(9)
        self._meta_font.setWeight(QFont.Weight.Medium)
        self._padding = QMargins(12, 10, 12, 10)
        self._gap = 10
        self._radius = 14

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # type: ignore[override]
        _ = option
        _ = index
        return QSize(0, 44)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        title = str(index.data(CONVERSATION_TITLE_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
        timestamp_value = index.data(CONVERSATION_TIMESTAMP_ROLE)
        timestamp_text = self.timestamp_formatter(timestamp_value)

        if not title:
            return super().paint(painter, option, index)

        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""

        painter.save()
        style = style_option.widget.style() if style_option.widget is not None else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, style_option, painter, style_option.widget)
        else:
            super().paint(painter, style_option, index)

        content_rect = option.rect.marginsRemoved(self._padding)
        timestamp_width = 0
        timestamp_rect = QRect()
        if timestamp_text:
            painter.setFont(self._meta_font)
            timestamp_width = painter.fontMetrics().horizontalAdvance(timestamp_text)
            timestamp_rect = QRect(
                content_rect.right() - timestamp_width,
                content_rect.top(),
                timestamp_width,
                content_rect.height(),
            )
        title_right = timestamp_rect.left() - self._gap if timestamp_width else content_rect.right()
        title_rect = QRect(
            content_rect.left(),
            content_rect.top(),
            max(0, title_right - content_rect.left()),
            content_rect.height(),
        )

        painter.setPen(self._title_color(option.palette, option.state))
        painter.setFont(self._title_font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._elide(painter, title, title_rect.width()))

        if timestamp_text:
            painter.setPen(self._meta_color(option.palette, option.state))
            painter.setFont(self._meta_font)
            painter.drawText(timestamp_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, timestamp_text)
        painter.restore()

    def _elide(self, painter: QPainter, text: str, width: int) -> str:
        if width <= 0:
            return ""
        return painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width)

    @staticmethod
    def _title_color(palette: QPalette, state: QStyle.StateFlag) -> QColor:
        if state & QStyle.StateFlag.State_Selected:
            return palette.color(QPalette.ColorRole.Text)
        return palette.color(QPalette.ColorRole.Text)

    @staticmethod
    def _meta_color(palette: QPalette, state: QStyle.StateFlag) -> QColor:
        base = palette.color(QPalette.ColorRole.PlaceholderText)
        if base.isValid():
            return base
        text = palette.color(QPalette.ColorRole.Text)
        return QColor(text.red(), text.green(), text.blue(), 170)
