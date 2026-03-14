from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..exceptions import ActionError
from ..models import ActionKind, ActionRisk, AssistantAction


ACTION_BLOCK_PATTERN = re.compile(r"<ACTION_REQUEST>\s*(\{.*?\})\s*</ACTION_REQUEST>", re.DOTALL)


@dataclass(slots=True)
class ParsedActionRequest:
    visible_text: str
    action: AssistantAction | None


def extract_action_request(
    text: str,
    *,
    conversation_id: str,
    assistant_message_id: str,
) -> ParsedActionRequest:
    match = ACTION_BLOCK_PATTERN.search(text)
    if not match:
        return ParsedActionRequest(visible_text=text, action=None)

    visible_text = ACTION_BLOCK_PATTERN.sub("", text).strip()
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ActionError("Assistant returned an invalid action payload.") from exc

    kind = _required_str(payload, "kind")
    if kind not in {"web_fetch", "file_read", "file_write", "command_run"}:
        raise ActionError(f"Unsupported action kind: {kind}")

    title = payload.get("title") or _default_title(kind)
    description = payload.get("description") or ""
    target = payload.get("target") or _default_target(kind, payload)
    risk = payload.get("risk") or _default_risk(kind)
    action_payload = payload.get("payload") or {}

    if not isinstance(action_payload, dict):
        raise ActionError("Action payload must be an object.")

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
    return ParsedActionRequest(visible_text=visible_text, action=action)


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
