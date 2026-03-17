from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.models import MessageRecord, ProviderDescriptor, ProviderHealth
from local_assistant.providers.base import ModelProvider
from local_assistant.ui.components.avatar_assets import AvatarAssetStore
from local_assistant.ui.components.chat_rendering import ChatRenderer, build_message_bubble_html, typing_indicator_text


def get_app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _DummyProvider(ModelProvider):
    descriptor = ProviderDescriptor(provider_id="dummy", display_name="Dummy", description_key="dummy")

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        _ = provider_config
        _ = desired_model
        return ProviderHealth(status="ready", detail="ok")

    def list_models(self, provider_config: dict[str, str]):
        _ = provider_config
        return []

    def stream_chat(self, request, cancel_event):
        _ = request
        _ = cancel_event
        yield "chunk"


class MiscComponentsTests(unittest.TestCase):
    def test_avatar_asset_store_builds_pixmap_and_html_and_uses_cache(self) -> None:
        _ = get_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "avatar.png"
            image = QImage(8, 8, QImage.Format.Format_ARGB32)
            image.fill(0xFF336699)
            self.assertTrue(image.save(str(image_path)))

            store = AvatarAssetStore()
            pixmap = store.avatar_pixmap([image_path], size=12)
            self.assertIsNotNone(pixmap)
            self.assertEqual(pixmap.width(), 12)  # type: ignore[union-attr]
            self.assertIs(store.avatar_pixmap([image_path], size=12), pixmap)
            html = store.avatar_html([image_path], size=12)
            self.assertIn("data:image/png;base64,", html)
            self.assertEqual(store.avatar_html([Path("missing.png"), image_path], size=12), html)
            self.assertIsNone(AvatarAssetStore._build_avatar_pixmap(Path("missing.png"), size=12))  # noqa: SLF001

    def test_chat_renderer_helpers_and_fallback_avatars(self) -> None:
        renderer = ChatRenderer(lambda key: key)
        self.assertEqual(typing_indicator_text(0), "Typing.")
        self.assertEqual(typing_indicator_text(4), "Typing..")
        self.assertIn("border-radius:22px", build_message_bubble_html("hi", "", is_user=True, dark=True))

        record = MessageRecord(
            message_id="m1",
            conversation_id="c1",
            role="assistant",
            content="",
            status="failed",
            error="boom",
            created_at=__import__("datetime").datetime.now().astimezone(),
            updated_at=__import__("datetime").datetime.now().astimezone(),
            metadata={},
        )
        self.assertIn("boom", renderer._status_suffix(record))  # noqa: SLF001
        self.assertIn("chat_empty_title", renderer.render_document(messages=[], dark=True, typing_message_id=None, has_received_generation_chunk=False, typing_phase=0))
        with patch.object(renderer.avatar_store, "avatar_html", return_value=None):
            self.assertIn(">U</div>", renderer.user_avatar_html())
            self.assertIn(">AI</div>", renderer.assistant_avatar_html(dark=False))

    def test_provider_base_default_metadata(self) -> None:
        provider = _DummyProvider()
        self.assertEqual(provider.pop_response_metadata("m1"), {})
        self.assertEqual(list(provider.stream_chat(None, None)), ["chunk"])
