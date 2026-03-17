from __future__ import annotations

import html
from pathlib import Path
from typing import Callable

from ...config import resolve_asset
from ...models import MessageRecord
from .avatar_assets import AvatarAssetStore


def typing_indicator_text(phase: int) -> str:
    return "Typing" + ("." * ((phase % 3) + 1))


def build_message_bubble_html(content: str, status_suffix: str, *, is_user: bool, dark: bool) -> str:
    if dark:
        bubble_bg = "rgba(31, 51, 79, 0.96)" if is_user else "rgba(18, 33, 52, 0.98)"
        text_color = "#f2f7ff"
        border_tone = "rgba(122, 167, 255, 0.26)" if is_user else "rgba(255,255,255,0.14)"
        shadow = "0 18px 30px rgba(3, 8, 15, 0.22)"
    else:
        bubble_bg = "rgba(232, 241, 255, 0.99)" if is_user else "rgba(255, 255, 255, 0.998)"
        text_color = "#14263f"
        border_tone = "rgba(117, 152, 214, 0.34)" if is_user else "rgba(219,227,238,0.96)"
        shadow = "0 14px 24px rgba(15, 23, 42, 0.09)"
    return (
        f"<div style='display:inline-block;width:auto;min-width:0;max-width:620px;"
        f"background:{bubble_bg};color:{text_color};border:1px solid {border_tone};"
        f"border-radius:22px;padding:11px 16px 12px 16px;box-shadow:{shadow};text-align:left;'>"
        f"<div style='white-space:pre-wrap;font-size:15px;line-height:1.62;text-align:left;'>{html.escape(content) or '&nbsp;'}</div>"
        f"{status_suffix}</div>"
    )


class ChatRenderer:
    def __init__(self, translator: Callable[[str], str], avatar_store: AvatarAssetStore | None = None) -> None:
        self._t = translator
        self._avatar_store = avatar_store or AvatarAssetStore()

    @property
    def avatar_store(self) -> AvatarAssetStore:
        return self._avatar_store

    def render_document(
        self,
        *,
        messages: list[MessageRecord],
        dark: bool,
        typing_message_id: str | None,
        has_received_generation_chunk: bool,
        typing_phase: int,
        bottom_spacer_px: int = 0,
    ) -> str:
        if not messages:
            return self._render_empty_state(dark)

        base_text = "#edf4ff" if dark else "#102033"
        assistant_avatar = self.assistant_avatar_html(dark)
        user_avatar = self.user_avatar_html()
        blocks = [
            f"<html><body style=\"font-family:'Segoe UI Variable'; background:transparent; color:{base_text}; margin:0;\">",
            "<div style='max-width:880px;margin:0 auto;padding:18px 24px 0 24px;'>",
        ]
        for message in messages:
            is_user = message.role == "user"
            status_suffix = self._status_suffix(message)
            content = message.content
            if (
                message.message_id == typing_message_id
                and not has_received_generation_chunk
                and message.role == "assistant"
                and message.status in {"pending", "streaming"}
                and not message.content.strip()
            ):
                content = typing_indicator_text(typing_phase)
            bubble_html = build_message_bubble_html(content, status_suffix, is_user=is_user, dark=dark)
            avatar_html = user_avatar if is_user else assistant_avatar
            if is_user:
                row_html = (
                    "<div style='margin:16px 0;'>"
                    "<table width='100%' cellspacing='0' cellpadding='0' style='border:none;'>"
                    "<tr>"
                    "<td width='52'></td>"
                    f"<td align='right' valign='top' style='text-align:right;'>{bubble_html}</td>"
                    f"<td width='58' valign='top' style='padding-left:12px;padding-top:4px;'>{avatar_html}</td>"
                    "</tr>"
                    "</table>"
                    "</div>"
                )
            else:
                row_html = (
                    "<div style='margin:16px 0;'>"
                    "<table width='100%' cellspacing='0' cellpadding='0' style='border:none;'>"
                    "<tr>"
                    f"<td width='58' valign='top' style='padding-right:12px;padding-top:4px;'>{avatar_html}</td>"
                    f"<td align='left' valign='top' style='text-align:left;'>{bubble_html}</td>"
                    "<td width='52'></td>"
                    "</tr>"
                    "</table>"
                    "</div>"
                )
            blocks.append(row_html)
        blocks.append(f"<div style='height:{max(0, bottom_spacer_px)}px;'></div>")
        blocks.append("</div></body></html>")
        return "".join(blocks)

    def user_avatar_html(self) -> str:
        avatar_html = self._avatar_store.avatar_html(
            [
                resolve_asset("assets", "photo", "user-avatar.png"),
                resolve_asset("assets", "photo", "default.webp"),
                resolve_asset("assets", "branding", "default-user-avatar.svg"),
            ]
        )
        if avatar_html is not None:
            return avatar_html
        return (
            "<div style='width:44px;height:44px;border-radius:22px;background:#5c6d80;color:white;"
            "font-size:13px;font-weight:700;line-height:44px;text-align:center;'>U</div>"
        )

    def assistant_avatar_html(self, dark: bool) -> str:
        avatar_html = self._avatar_store.avatar_html(
            [
                resolve_asset("assets", "branding", "assistant-avatar.png"),
                resolve_asset("assets", "branding", "assistant-avatar.svg"),
                resolve_asset("assets", "branding", "app-icon.png"),
            ]
        )
        if avatar_html is not None:
            return avatar_html
        if dark:
            background = "rgba(255,255,255,0.10)"
            border = "1px solid rgba(255,255,255,0.12)"
            text = "#edf4ff"
        else:
            background = "rgba(18, 32, 52, 0.08)"
            border = "1px solid rgba(205, 218, 235, 0.98)"
            text = "#18314d"
        return (
            f"<div style='width:44px;height:44px;border-radius:22px;background:{background};border:{border};"
            f"color:{text};font-size:13px;font-weight:700;line-height:44px;text-align:center;'>AI</div>"
        )

    def _render_empty_state(self, dark: bool) -> str:
        empty_card_bg = "rgba(12, 22, 36, 0.74)" if dark else "rgba(255, 255, 255, 0.84)"
        empty_card_border = "1px solid rgba(255,255,255,0.10)" if dark else "1px solid rgba(210,223,239,0.96)"
        empty_title = "#f3f7ff" if dark else "#10233c"
        empty_text = "#9eb1c7" if dark else "#5d7693"
        empty_pill_bg = "rgba(96, 159, 255, 0.16)" if dark else "rgba(75, 132, 234, 0.12)"
        empty_pill_text = "#dcecff" if dark else "#21456d"
        return (
            f"<div style='margin-top:92px;padding:0 30px;text-align:center;color:{empty_text};'>"
            f"<div style='display:inline-block;max-width:560px;background:{empty_card_bg};border:{empty_card_border};border-radius:34px;padding:34px 36px;box-shadow:0 30px 54px rgba(15,23,42,0.18);'>"
            f"<div style='display:inline-block;margin-bottom:16px;padding:8px 14px;border-radius:999px;background:{empty_pill_bg};font-size:12px;font-weight:700;letter-spacing:0.4px;color:{empty_pill_text};'>{html.escape(self._t('chat_empty_badge'))}</div>"
            f"<h2 style='font-size:30px;margin:0 0 14px 0;color:{empty_title};'>{html.escape(self._t('chat_empty_title'))}</h2>"
            f"<p style='font-size:15px;line-height:1.72;margin:0;'>{html.escape(self._t('chat_empty_body'))}</p>"
            f"</div></div>"
        )

    @staticmethod
    def _status_suffix(message: MessageRecord) -> str:
        if message.status in {"failed", "cancelled"} and message.error:
            return f"<div style='font-size:12px;color:#b42318;margin-top:6px;'>{html.escape(message.error)}</div>"
        return ""
