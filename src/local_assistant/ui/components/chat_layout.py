from __future__ import annotations

from PySide6.QtCore import QRect, QSize


def compute_chat_composer_geometry(
    *,
    surface_size: QSize,
    composer_height: int,
    side_margin: int,
    min_width: int,
    max_width: int,
    bottom_clearance: int,
) -> QRect | None:
    available_width = max(0, surface_size.width() - (side_margin * 2))
    if available_width <= 0:
        return None
    width = min(max_width, max(min_width, available_width))
    width = min(width, available_width)
    if width <= 0:
        return None
    x = max(side_margin, (surface_size.width() - width) // 2)
    y = max(side_margin, surface_size.height() - bottom_clearance - composer_height)
    return QRect(x, y, width, composer_height)

def compute_chat_composer_bottom_clearance(
    *,
    surface_bottom: int,
    nav_top: int,
    minimum_clearance: int = 14,
    gap: int = 8,
) -> int:
    overlap = max(0, surface_bottom - nav_top)
    return max(minimum_clearance, overlap + gap)
