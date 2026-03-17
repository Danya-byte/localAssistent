from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap


class AvatarAssetStore:
    def __init__(self) -> None:
        self._html_cache: dict[tuple[str, int], str | None] = {}
        self._pixmap_cache: dict[tuple[str, int], QPixmap | None] = {}

    def avatar_html(self, asset_paths: list[Path], *, size: int = 44) -> str | None:
        for asset_path in asset_paths:
            cached = self._html_cache.get((str(asset_path), size))
            if cached is not None:
                return cached
            payload = self._build_avatar_html(asset_path, size=size)
            if payload is not None:
                self._html_cache[(str(asset_path), size)] = payload
                return payload
        return None

    def avatar_pixmap(self, asset_paths: list[Path], *, size: int = 44) -> QPixmap | None:
        for asset_path in asset_paths:
            key = (str(asset_path), size)
            cached = self._pixmap_cache.get(key)
            if cached is not None:
                return cached
            payload = self._build_avatar_pixmap(asset_path, size=size)
            if payload is not None:
                self._pixmap_cache[key] = payload
                return payload
        return None

    @staticmethod
    def _build_avatar_html(asset_path: Path, *, size: int) -> str | None:
        canvas = AvatarAssetStore._build_avatar_pixmap(asset_path, size=size)
        if canvas is None:
            return None
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            return None
        if not canvas.save(buffer, "PNG"):
            return None
        payload = base64.b64encode(bytes(buffer.data())).decode("ascii")
        return f"<img src='data:image/png;base64,{payload}' width='{size}' height='{size}' />"

    @staticmethod
    def _build_avatar_pixmap(asset_path: Path, *, size: int) -> QPixmap | None:
        if not asset_path.exists():
            return None
        source = QPixmap(str(asset_path))
        if source.isNull():
            return None
        scaled = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        clip_path = QPainterPath()
        clip_path.addEllipse(0, 0, size, size)
        painter.setClipPath(clip_path)
        offset_x = (scaled.width() - size) // 2
        offset_y = (scaled.height() - size) // 2
        painter.drawPixmap(-offset_x, -offset_y, scaled)
        painter.end()
        return canvas
