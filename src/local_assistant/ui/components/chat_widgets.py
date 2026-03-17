from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ...config import resolve_asset
from ...models import MessageRecord
from .avatar_assets import AvatarAssetStore


class ChatEmptyState(QFrame):
    def __init__(self, badge: str, title: str, body: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatEmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.badge_label = QLabel(badge)
        self.badge_label.setObjectName("ChatEmptyBadge")
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("ChatEmptyTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.body_label = QLabel(body)
        self.body_label.setObjectName("ChatEmptyBody")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.badge_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)


class ChatMessageRow(QWidget):
    AVATAR_SIZE = 44
    BUBBLE_MAX_WIDTH = 620

    def __init__(
        self,
        *,
        message: MessageRecord,
        visible_content: str,
        avatar_store: AvatarAssetStore,
        dark: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ChatMessageRow")
        is_user = message.role == "user"
        owner = "user" if is_user else "assistant"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        avatar = self._build_avatar(owner=owner, avatar_store=avatar_store, dark=dark)
        bubble = self._build_bubble(message=message, visible_content=visible_content, owner=owner)

        if is_user:
            layout.addStretch(1)
            layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        else:
            layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            layout.addStretch(1)

    def _build_bubble(self, *, message: MessageRecord, visible_content: str, owner: str) -> QFrame:
        bubble = QFrame()
        bubble.setObjectName("ChatBubble")
        bubble.setProperty("owner", owner)
        bubble.setMaximumWidth(self.BUBBLE_MAX_WIDTH)
        bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        bubble_layout.setSpacing(6)

        body_label = QLabel(visible_content or " ")
        body_label.setObjectName("ChatBubbleText")
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_label.setMaximumWidth(self.BUBBLE_MAX_WIDTH - 32)
        body_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        bubble_layout.addWidget(body_label)

        if message.status in {"failed", "cancelled"} and message.error:
            status_label = QLabel(message.error)
            status_label.setObjectName("ChatBubbleStatus")
            status_label.setProperty("variant", "error")
            status_label.setWordWrap(True)
            status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            bubble_layout.addWidget(status_label)

        return bubble

    def _build_avatar(self, *, owner: str, avatar_store: AvatarAssetStore, dark: bool) -> QLabel:
        avatar = QLabel()
        avatar.setObjectName("ChatAvatar")
        avatar.setProperty("owner", owner)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(self.AVATAR_SIZE, self.AVATAR_SIZE)

        pixmap = self._avatar_pixmap(owner=owner, avatar_store=avatar_store)
        if pixmap is not None and not pixmap.isNull():
            avatar.setPixmap(pixmap)
            avatar.setScaledContents(True)
            avatar.setText("")
        else:
            avatar.setText("U" if owner == "user" else "AI")
            if dark:
                avatar.setProperty("theme", "dark")
        avatar.style().unpolish(avatar)
        avatar.style().polish(avatar)
        return avatar

    def _avatar_pixmap(self, *, owner: str, avatar_store: AvatarAssetStore) -> QPixmap | None:
        if owner == "user":
            asset_paths = [
                resolve_asset("assets", "photo", "user-avatar.png"),
                resolve_asset("assets", "photo", "default.webp"),
                resolve_asset("assets", "branding", "default-user-avatar.svg"),
            ]
        else:
            asset_paths = [
                resolve_asset("assets", "branding", "assistant-avatar.png"),
                resolve_asset("assets", "branding", "assistant-avatar.svg"),
                resolve_asset("assets", "branding", "app-icon.png"),
            ]
        return avatar_store.avatar_pixmap(asset_paths, size=self.AVATAR_SIZE)
