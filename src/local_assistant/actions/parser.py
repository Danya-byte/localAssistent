from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ..exceptions import ActionError
from ..models import ActionKind, ActionRisk, AssistantAction


ACTION_BLOCK_PATTERN = re.compile(r"<ACTION_REQUEST>\s*(\{.*?\})\s*</ACTION_REQUEST>", re.DOTALL)


@dataclass(slots=True)
class ParsedActionRequest:
    visible_text: str
    action: AssistantAction | None
    had_action_block: bool = False
    action_parse_error: str = ""
    action_autofixed: bool = False


def extract_action_request(
    text: str,
    *,
    conversation_id: str,
    assistant_message_id: str,
) -> ParsedActionRequest:
    match = ACTION_BLOCK_PATTERN.search(text)
    if not match:
        return ParsedActionRequest(
            visible_text=text,
            action=None,
            had_action_block=False,
            action_parse_error="",
            action_autofixed=False,
        )

    visible_text = ACTION_BLOCK_PATTERN.sub("", text).strip()
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return ParsedActionRequest(
            visible_text=visible_text,
            action=None,
            had_action_block=True,
            action_parse_error=f"Invalid action JSON: {exc.msg}",
            action_autofixed=False,
        )

    try:
        kind = _normalize_kind(_required_str(payload, "kind"))
        if kind not in {"web_fetch", "file_read", "file_write", "command_run"}:
            raise ActionError(f"Unsupported action kind: {kind}")

        title = payload.get("title") or _default_title(kind)
        description = payload.get("description") or ""
        target = payload.get("target") or _default_target(kind, payload)
        risk = payload.get("risk") or _default_risk(kind)
        action_payload = payload.get("payload") or {}
        action_autofixed = False

        if not isinstance(action_payload, dict):
            raise ActionError("Action payload must be an object.")

        action_payload, autofixed_url = _normalize_action_payload(kind, action_payload, target)
        action_autofixed = action_autofixed or autofixed_url
        risk, autofixed_risk = _normalize_risk(kind, risk)
        action_autofixed = action_autofixed or autofixed_risk
        _validate_action_payload(kind, action_payload)

        action = AssistantAction(
            action_id=None,
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            kind=kind,
            title=title,
            description=description,
            target=target,
            risk=risk,
            payload=action_payload,
        )
        return ParsedActionRequest(
            visible_text=visible_text,
            action=action,
            had_action_block=True,
            action_parse_error="",
            action_autofixed=action_autofixed,
        )
    except ActionError as exc:
        return ParsedActionRequest(
            visible_text=visible_text,
            action=None,
            had_action_block=True,
            action_parse_error=str(exc),
            action_autofixed=False,
        )


def _normalize_kind(kind: str) -> str:
    normalized = kind.strip()
    if normalized == "web_request":
        return "web_fetch"
    return normalized


def _validate_action_payload(kind: ActionKind, payload: dict[str, Any]) -> None:
    required_fields = {
        "web_fetch": ["url"],
        "file_read": ["path"],
        "file_write": ["path", "content"],
        "command_run": ["command"],
    }[kind]
    for field in required_fields:
        if not isinstance(payload.get(field), str) or not payload.get(field):
            raise ActionError(f"Action payload field `{field}` is required.")
    if kind == "web_fetch":
        _validate_web_url(payload["url"])


def _required_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ActionError(f"Assistant action is missing `{field_name}`.")
    return value


def _default_title(kind: ActionKind) -> str:
    return {
        "web_fetch": "Fetch web content",
        "file_read": "Read file",
        "file_write": "Write file",
        "command_run": "Run command",
    }[kind]


def _default_risk(kind: ActionKind) -> ActionRisk:
    return {
        "web_fetch": "low",
        "file_read": "medium",
        "file_write": "high",
        "command_run": "high",
    }[kind]


def _default_target(kind: ActionKind, payload: dict[str, Any]) -> str:
    return {
        "web_fetch": payload.get("payload", {}).get("url", ""),
        "file_read": payload.get("payload", {}).get("path", ""),
        "file_write": payload.get("payload", {}).get("path", ""),
        "command_run": payload.get("payload", {}).get("command", ""),
    }[kind]


def _normalize_action_payload(kind: ActionKind, payload: dict[str, Any], target: str) -> tuple[dict[str, Any], bool]:
    normalized = dict(payload)
    autofixed = False
    if kind == "web_fetch":
        url = normalized.get("url")
        if (not isinstance(url, str) or not url.strip()) and _is_valid_web_target(target):
            normalized["url"] = target.strip()
            autofixed = True
    return normalized, autofixed


def _normalize_risk(kind: ActionKind, risk: Any) -> tuple[ActionRisk, bool]:
    if not isinstance(risk, str) or not risk.strip():
        return _default_risk(kind), True
    normalized = risk.strip()
    if normalized not in {"low", "medium", "high"}:
        raise ActionError("Action risk must be `low`, `medium`, or `high`.")
    return normalized, False


def _validate_web_url(url: str) -> None:
    if not _is_valid_web_target(url):
        raise ActionError("Action payload field `url` must be a valid http(s) URL.")
    if _is_localhost_url(url):
        raise ActionError("Loopback or localhost URLs are not valid for web_fetch. Use command_run for local app actions.")


def _is_valid_web_target(value: str) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    if lowered in {"human-readable target", "target", "url", "link"}:
        return False
    parsed = urlparse(candidate)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_localhost_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False
    return hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"} or hostname.startswith("127.")
