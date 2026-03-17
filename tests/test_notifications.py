from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.ui.components.notification_center import NotificationCenter, _variant_glyph
from local_assistant.ui.theme import build_stylesheet


def get_app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class NotificationCenterTests(unittest.TestCase):
    def test_variant_glyphs_use_stable_ascii_tokens(self) -> None:
        self.assertEqual(_variant_glyph("success"), "OK")
        self.assertEqual(_variant_glyph("warning"), "!")
        self.assertEqual(_variant_glyph("error"), "x")
        self.assertEqual(_variant_glyph("info"), "i")

    def setUp(self) -> None:
        self.app = get_app()
        self.host = QWidget()
        self.host.resize(960, 720)
        self.center = NotificationCenter(self.host, translator=lambda value: {"Hide": "Hide", "Unhide": "Unhide"}.get(value, value))
        self.center.set_host_geometry(QRect(0, 0, 960, 720))
        self.host.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.host.close()
        self.app.processEvents()

    def test_alerts_render_in_top_container(self) -> None:
        self.center.show_alert("Warning", "Body", variant="warning", timeout_ms=0)
        self.app.processEvents()

        self.assertTrue(self.center.top_container.isVisible())
        self.assertEqual(self.center.top_layout.count(), 1)
        self.assertFalse(self.center.bottom_container.isVisible())

    def test_events_render_in_bottom_container_and_can_collapse(self) -> None:
        self.center.show_event("download:model", "Downloading", "Fetching model", progress=48)
        self.app.processEvents()

        item = self.center._events["download:model"]  # noqa: SLF001
        self.assertTrue(self.center.bottom_container.isVisible())
        self.assertFalse(item.collapsed)
        self.assertTrue(item.card.isVisible())
        self.assertFalse(item.bar.isVisible())
        self.assertFalse(item.card.close_button.isVisible())

        QTest.mouseClick(item.card.hide_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()

        self.assertTrue(item.collapsed)
        self.assertFalse(item.card.isVisible())
        self.assertTrue(item.bar.isVisible())

        QTest.mouseClick(item.bar, Qt.MouseButton.LeftButton)
        self.app.processEvents()

        self.assertFalse(item.collapsed)
        self.assertTrue(item.card.isVisible())
        self.assertFalse(item.bar.isVisible())

    def test_alerts_keep_close_button(self) -> None:
        self.center.show_alert("Success", "Body", variant="success", timeout_ms=0)
        self.app.processEvents()

        alert = next(iter(self.center._alerts.values()))  # noqa: SLF001
        self.assertTrue(alert.close_button.isVisible())
        self.assertFalse(alert.hide_button.isVisible())
        self.assertEqual(alert.close_button.text(), "x")

    def test_alert_close_button_style_is_square_and_centered(self) -> None:
        light_stylesheet = build_stylesheet("light")
        dark_stylesheet = build_stylesheet("dark")

        for stylesheet in (light_stylesheet, dark_stylesheet):
            self.assertIn("QPushButton#NotificationInlineButton[role=\"close\"]", stylesheet)
            self.assertIn("min-width: 26px;", stylesheet)
            self.assertIn("max-height: 26px;", stylesheet)
            self.assertIn("padding: 0;", stylesheet)
            self.assertIn("text-align: center;", stylesheet)

    def test_finished_event_auto_hides(self) -> None:
        self.center.show_event("download:model", "Downloading", progress=90)
        self.center.finish_event("download:model", "Done", variant="success", progress=100, auto_hide_ms=40)
        QTest.qWait(80)
        self.app.processEvents()

        self.assertNotIn("download:model", self.center._events)  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
