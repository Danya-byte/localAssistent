from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from .config import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, DEFAULT_TOP_P


Language = Literal["en", "ru"]
ThemeMode = Literal["light", "dark"]
ModelSource = Literal["local", "api"]
Role = Literal["system", "user", "assistant"]
MessageStatus = Literal["pending", "streaming", "completed", "failed", "cancelled"]
ProviderStatus = Literal["ready", "missing_runtime", "missing_configuration", "missing_model", "error"]
ActionKind = Literal["web_fetch", "file_read", "file_write", "command_run"]
ActionRisk = Literal["low", "medium", "high"]
ApprovalStatus = Literal["pending", "approved", "denied", "executed", "failed"]
DownloadStage = Literal["idle", "downloading", "verifying", "completed", "failed", "cancelled"]


@dataclass(slots=True)
class AppSettings:
    provider_id: str
    model: str
    system_prompt: str
    default_source: ModelSource = "local"
    api_model: str = ""
    reasoning_enabled: bool = True
    language: Language = "ru"
    theme: ThemeMode = "dark"
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    max_tokens: int = DEFAULT_MAX_TOKENS
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
    source_override: ModelSource | None = None


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
    metadata: dict[str, Any] = field(default_factory=dict)


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
    source: str = ""
    source_url: str = ""
    recommended: bool = False


@dataclass(slots=True)
class LocalModelDescriptor:
    model_id: str
    display_name: str
    description: str
    source: str
    download_url: str
    file_name: str
    size_hint: str
    quantization: str
    recommended_ram_gb: int
    context_length: int
    recommended: bool = False


@dataclass(slots=True)
class InstalledLocalModel:
    model_id: str
    file_path: str
    file_name: str
    source: str
    downloaded_at: str
    size_bytes: int = 0


@dataclass(slots=True)
class ModelDownloadProgress:
    model_id: str
    display_name: str
    stage: DownloadStage
    downloaded_bytes: int = 0
    total_bytes: int = 0
    message: str = ""
    error: str | None = None


@dataclass(slots=True)
class ProviderHealth:
    status: ProviderStatus
    detail: str
    models: list[ModelDescriptor] = field(default_factory=list)


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str
    reasoning_details: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class GenerationRequest:
    conversation_id: str
    assistant_message_id: str
    provider_id: str
    provider_config: dict[str, str]
    model: str
    messages: list[ChatMessage]
    reasoning_enabled: bool
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
