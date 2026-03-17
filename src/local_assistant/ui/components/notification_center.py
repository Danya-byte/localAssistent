from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _apply_shadow(widget: QWidget, alpha: int = 34) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(26)
    effect.setOffset(0, 10)
    effect.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(effect)


def _variant_glyph(variant: str) -> str:
    return {
        "success": "OK",
        "warning": "!",
        "error": "x",
        "info": "i",
    }.get(variant, "i")


class NotificationCard(QFrame):
    dismiss_requested = Signal(str)
    collapse_requested = Signal(str)

    def __init__(self, item_id: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.kind = kind
        self.hide_label = "Hide"

        self.setObjectName("NotificationCard")
        self.setProperty("kind", kind)
        self.setProperty("variant", "info")
        self.setProperty("compact", kind == "event")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("NotificationIconPill")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(24, 24)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(3)

        self.title_label = QLabel()
        self.title_label.setObjectName("NotificationTitle")
        self.title_label.setWordWrap(True)

        self.message_label = QLabel()
        self.message_label.setObjectName("NotificationMessage")
        self.message_label.setWordWrap(True)

        copy_layout.addWidget(self.title_label)
        copy_layout.addWidget(self.message_label)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        self.hide_button = QPushButton()
        self.hide_button.setObjectName("NotificationInlineButton")
        self.hide_button.clicked.connect(lambda: self.collapse_requested.emit(self.item_id))

        self.close_button = QPushButton("x")
        self.close_button.setObjectName("NotificationInlineButton")
        self.close_button.setProperty("role", "close")
        self.close_button.clicked.connect(lambda: self.dismiss_requested.emit(self.item_id))

        actions_layout.addWidget(self.hide_button)
        actions_layout.addWidget(self.close_button)

        top_row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        top_row.addLayout(copy_layout, 1)
        top_row.addLayout(actions_layout, 0)
        root.addLayout(top_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("NotificationProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        _apply_shadow(self)

    def set_translations(self, hide_label: str) -> None:
        self.hide_label = hide_label
        self.hide_button.setText(hide_label)

    def set_payload(
        self,
        title: str,
        message: str = "",
        variant: str = "info",
        progress: int | None = None,
        collapsible: bool = False,
        dismissible: bool = True,
    ) -> None:
        self.setProperty("variant", variant)
        self.icon_label.setProperty("variant", variant)
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.message_label.setVisible(bool(message.strip()))
        self.icon_label.setText(_variant_glyph(variant))

        is_event = self.kind == "event"
        self.setProperty("compact", is_event)
        self.hide_button.setVisible(collapsible and is_event)
        self.hide_button.setText(self.hide_label)
        self.close_button.setVisible(dismissible and not is_event)
        self.setProperty("dismissible", dismissible)

        if progress is None:
            self.progress_bar.hide()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.show()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(max(0, min(100, progress)))

        self.style().unpolish(self)
        self.style().polish(self)
        self.icon_label.style().unpolish(self.icon_label)
        self.icon_label.style().polish(self.icon_label)
        self.close_button.style().unpolish(self.close_button)
        self.close_button.style().polish(self.close_button)


class CollapsedEventBar(QFrame):
    restore_requested = Signal(str)

    def __init__(self, item_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.show_label = "Unhide"

        self.setObjectName("EventCollapsedBar")
        self.setProperty("variant", "info")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.title_label = QLabel()
        self.title_label.setObjectName("NotificationTitle")
        self.title_label.setWordWrap(True)

        self.restore_button = QPushButton()
        self.restore_button.setObjectName("NotificationInlineButton")
        self.restore_button.clicked.connect(lambda: self.restore_requested.emit(self.item_id))

        row.addWidget(self.title_label, 1)
        row.addWidget(self.restore_button)
        root.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("NotificationProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _apply_shadow(self, alpha=28)

    def set_translations(self, show_label: str) -> None:
        self.show_label = show_label
        self.restore_button.setText(show_label)

    def set_payload(self, title: str, variant: str = "info", progress: int | None = None) -> None:
        self.setProperty("variant", variant)
        self.title_label.setText(title)
        self.restore_button.setText(self.show_label)
        if progress is None:
            self.progress_bar.hide()
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.show()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(max(0, min(100, progress)))
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.restore_requested.emit(self.item_id)


class EventNotificationItem(QWidget):
    layout_changed = Signal()
    dismissed = Signal(str)

    def __init__(self, item_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.collapsed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.dismissed.emit(self.item_id))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.card = NotificationCard(item_id, kind="event", parent=self)
        self.card.collapse_requested.connect(lambda _item_id: self.set_collapsed(True))

        self.bar = CollapsedEventBar(item_id, parent=self)
        self.bar.restore_requested.connect(lambda _item_id: self.set_collapsed(False))
        self.bar.hide()

        layout.addWidget(self.card)
        layout.addWidget(self.bar)

    def set_translations(self, hide_label: str, show_label: str) -> None:
        self.card.set_translations(hide_label)
        self.bar.set_translations(show_label)

    def set_payload(
        self,
        title: str,
        message: str = "",
        variant: str = "info",
        progress: int | None = None,
        dismissible: bool = True,
        auto_hide_ms: int = 0,
    ) -> None:
        self.card.set_payload(
            title=title,
            message=message,
            variant=variant,
            progress=progress,
            collapsible=True,
            dismissible=dismissible,
        )
        self.bar.set_payload(
            title=title,
            variant=variant,
            progress=progress,
        )
        if auto_hide_ms > 0:
            self.timer.start(auto_hide_ms)
        else:
            self.timer.stop()

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed
        self.card.setVisible(not collapsed)
        self.bar.setVisible(collapsed)
        self.layout_changed.emit()


class NotificationCenter(QWidget):
    layout_changed = Signal()

    def __init__(self, parent: QWidget | None = None, translator: Callable[[str], str] | None = None) -> None:
        super().__init__(parent)
        self.translator = translator or (lambda value: value)
        self._alerts: dict[str, NotificationCard] = {}
        self._alert_timers: dict[str, QTimer] = {}
        self._events: dict[str, EventNotificationItem] = {}
        self._alert_counter = 0
        self.setObjectName("NotificationCenter")
        self.hide()
        self._host_rect = None

        host = parent
        self.top_container = QWidget(host)
        self.top_container.setObjectName("NotificationTopContainer")
        self.top_layout = QVBoxLayout(self.top_container)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(10)
        self.top_container.hide()

        self.bottom_container = QWidget(host)
        self.bottom_container.setObjectName("NotificationBottomContainer")
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(10)
        self.bottom_container.hide()
        self.retranslate()

    def retranslate(self) -> None:
        self.hide_label = self.translator("Hide")
        self.show_label = self.translator("Unhide")
        for alert in self._alerts.values():
            alert.set_translations(self.hide_label)
        for event in self._events.values():
            event.set_translations(self.hide_label, self.show_label)

    def show_alert(
        self,
        title: str,
        message: str = "",
        variant: str = "info",
        timeout_ms: int = 3600,
        dismissible: bool = True,
    ) -> str:
        self._alert_counter += 1
        item_id = f"alert-{self._alert_counter}"
        card = NotificationCard(item_id, kind="alert", parent=self.top_container)
        card.set_translations(self.hide_label)
        card.dismiss_requested.connect(self.dismiss_alert)
        card.set_payload(
            title=title,
            message=message,
            variant=variant,
            dismissible=dismissible,
        )
        self.top_layout.insertWidget(0, card)
        self._alerts[item_id] = card
        if timeout_ms > 0:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda item=item_id: self.dismiss_alert(item))
            timer.start(timeout_ms)
            self._alert_timers[item_id] = timer
        self._emit_layout_change()
        return item_id

    def dismiss_alert(self, item_id: str) -> None:
        card = self._alerts.pop(item_id, None)
        timer = self._alert_timers.pop(item_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        if card is None:
            return
        self.top_layout.removeWidget(card)
        card.deleteLater()
        self._emit_layout_change()

    def show_event(
        self,
        event_id: str,
        title: str,
        message: str = "",
        variant: str = "info",
        progress: int | None = None,
        auto_hide_ms: int = 0,
        dismissible: bool = True,
    ) -> None:
        item = self._events.get(event_id)
        if item is None:
            item = EventNotificationItem(event_id, parent=self.bottom_container)
            item.set_translations(self.hide_label, self.show_label)
            item.dismissed.connect(self.dismiss_event)
            item.layout_changed.connect(self._emit_layout_change)
            self._events[event_id] = item
            self.bottom_layout.insertWidget(0, item)
        item.set_payload(
            title=title,
            message=message,
            variant=variant,
            progress=progress,
            dismissible=dismissible,
            auto_hide_ms=auto_hide_ms,
        )
        self._emit_layout_change()

    def finish_event(
        self,
        event_id: str,
        title: str,
        message: str = "",
        variant: str = "success",
        progress: int | None = None,
        auto_hide_ms: int = 3200,
        dismissible: bool = True,
    ) -> None:
        self.show_event(
            event_id=event_id,
            title=title,
            message=message,
            variant=variant,
            progress=progress,
            auto_hide_ms=auto_hide_ms,
            dismissible=dismissible,
        )

    def dismiss_event(self, event_id: str) -> None:
        item = self._events.pop(event_id, None)
        if item is None:
            return
        item.timer.stop()
        self.bottom_layout.removeWidget(item)
        item.deleteLater()
        self._emit_layout_change()

    def _emit_layout_change(self) -> None:
        self.top_container.setVisible(bool(self._alerts))
        self.bottom_container.setVisible(bool(self._events))
        self._reposition_containers()
        self.layout_changed.emit()

    def set_host_geometry(self, rect) -> None:
        self._host_rect = rect
        self._reposition_containers()

    def _reposition_containers(self) -> None:
        if self._host_rect is None:
            return
        right_margin = 22
        top_margin = 20
        bottom_margin = 28
        if self.top_container.isVisible():
            self.top_container.adjustSize()
            top_size = self.top_container.sizeHint()
            self.top_container.setGeometry(
                max(0, self._host_rect.width() - right_margin - top_size.width()),
                top_margin,
                top_size.width(),
                top_size.height(),
            )
            self.top_container.raise_()
        if self.bottom_container.isVisible():
            self.bottom_container.adjustSize()
            bottom_size = self.bottom_container.sizeHint()
            self.bottom_container.setGeometry(
                max(0, self._host_rect.width() - right_margin - bottom_size.width()),
                max(0, self._host_rect.height() - bottom_margin - bottom_size.height()),
                bottom_size.width(),
                bottom_size.height(),
            )
            self.bottom_container.raise_()
