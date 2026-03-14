from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


Language = Literal["en", "ru"]
Role = Literal["system", "user", "assistant"]
MessageStatus = Literal["pending", "streaming", "completed", "failed", "cancelled"]
ProviderStatus = Literal["ready", "missing_runtime", "missing_configuration", "missing_model", "error"]
ActionKind = Literal["web_fetch", "file_read", "file_write", "command_run"]
ActionRisk = Literal["low", "medium", "high"]
ApprovalStatus = Literal["pending", "approved", "denied", "executed", "failed"]


@dataclass(slots=True)
class AppSettings:
    provider_id: str
    model: str
    system_prompt: str
    language: Language = "ru"
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 1024
    last_conversation_id: str | None = None
    provider_configs: dict[str, dict[str, str]] = field(default_factory=dict)
    web_enabled: bool = True
    files_enabled: bool = True
    commands_enabled: bool = True
    require_confirmation: bool = True
    command_allowlist: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConversationSummary:
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MessageRecord:
    message_id: str
    conversation_id: str
    role: Role
    content: str
    status: MessageStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None


@dataclass(slots=True)
class ProviderField:
    name: str
    label_key: str
    placeholder_key: str = ""
    secret: bool = False


@dataclass(slots=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    description_key: str
    config_fields: list[ProviderField] = field(default_factory=list)


@dataclass(slots=True)
class ModelDescriptor:
    model_id: str
    display_name: str
    description: str = ""


@dataclass(slots=True)
class ProviderHealth:
    status: ProviderStatus
    detail: str
    models: list[ModelDescriptor] = field(default_factory=list)


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(slots=True)
class GenerationRequest:
    conversation_id: str
    assistant_message_id: str
    provider_id: str
    provider_config: dict[str, str]
    model: str
    messages: list[ChatMessage]
    temperature: float
    top_p: float
    max_tokens: int


@dataclass(slots=True)
class AssistantAction:
    action_id: str | None
    conversation_id: str
    assistant_message_id: str
    kind: ActionKind
    title: str
    description: str
    target: str
    risk: ActionRisk
    payload: dict[str, Any]
    status: ApprovalStatus = "pending"
    result_text: str = ""
    error: str | None = None


@dataclass(slots=True)
class PreparedGeneration:
    conversation: ConversationSummary
    assistant_message: MessageRecord
    request: GenerationRequest


@dataclass(slots=True)
class AppState:
    settings: AppSettings
    conversations: list[ConversationSummary]
    providers: list[ProviderDescriptor]
