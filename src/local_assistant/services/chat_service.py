from __future__ import annotations

import json
from pathlib import Path

from ..actions import extract_action_request
from ..config import DEFAULT_MODEL, DEFAULT_PROVIDER_ID, DEFAULT_SYSTEM_PROMPT
from ..exceptions import ActionError, ProviderError
from ..models import (
    AppSettings,
    AppState,
    AssistantAction,
    ChatMessage,
    ConversationSummary,
    ModelDescriptor,
    PreparedGeneration,
    ProviderDescriptor,
    ProviderHealth,
)
from ..providers import ProviderRegistry
from ..storage import Storage


ACTION_PROTOCOL_PROMPT = """
You are allowed to request external actions, but you must never assume they were executed.
When you need a web request, file action, or command, output a single machine-readable block:
<ACTION_REQUEST>
{"kind":"web_fetch|file_read|file_write|command_run","title":"short title","description":"why you need it","target":"human-readable target","risk":"low|medium|high","payload":{...}}
</ACTION_REQUEST>
Wait for a system message with the action result before continuing.
""".strip()


class ChatService:
    def __init__(self, storage: Storage, providers: ProviderRegistry) -> None:
        self.storage = storage
        self.providers = providers

    def initialize(self) -> AppState:
        self.storage.initialize()
        return AppState(
            settings=self.storage.load_settings(),
            conversations=self.storage.list_conversations(),
            providers=self.providers.list_descriptors(),
        )

    def load_settings(self) -> AppSettings:
        return self.storage.load_settings()

    def save_settings(self, settings: AppSettings) -> None:
        self.storage.save_settings(settings)

    def list_provider_descriptors(self) -> list[ProviderDescriptor]:
        return self.providers.list_descriptors()

    def list_models(self, provider_id: str) -> list[ModelDescriptor]:
        settings = self.storage.load_settings()
        provider = self.providers.get(provider_id)
        return provider.list_models(settings.provider_configs.get(provider_id, {}))

    def get_provider_health(self, provider_id: str, model: str) -> ProviderHealth:
        settings = self.storage.load_settings()
        provider = self.providers.get(provider_id)
        return provider.health_check(settings.provider_configs.get(provider_id, {}), model)

    def load_conversations(self) -> list[ConversationSummary]:
        return self.storage.list_conversations()

    def load_messages(self, conversation_id: str):
        return self.storage.list_messages(conversation_id)

    def set_last_conversation(self, conversation_id: str | None) -> AppSettings:
        settings = self.storage.load_settings()
        settings.last_conversation_id = conversation_id
        self.storage.save_settings(settings)
        return settings

    def prepare_user_generation(self, conversation_id: str | None, user_text: str) -> PreparedGeneration:
        settings = self.storage.load_settings()
        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("User message cannot be empty.")

        conversation = self._ensure_conversation(conversation_id, normalized_text)
        self.storage.add_message(conversation.conversation_id, "user", normalized_text, status="completed")
        return self._prepare_assistant_generation(conversation.conversation_id, settings)

    def prepare_follow_up_generation(self, conversation_id: str, system_text: str) -> PreparedGeneration:
        self.storage.add_message(conversation_id, "system", system_text, status="completed")
        return self._prepare_assistant_generation(conversation_id, self.storage.load_settings())

    def append_to_message(self, message_id: str, chunk: str):
        current = self.storage.get_message(message_id)
        if current is None:
            raise ValueError(f"Message {message_id} not found.")
        self.storage.update_message(message_id, content=current.content + chunk, status="streaming", error=None)
        updated = self.storage.get_message(message_id)
        assert updated is not None
        return updated

    def finalize_message(self, message_id: str):
        self.storage.update_message(message_id, status="completed")
        updated = self.storage.get_message(message_id)
        assert updated is not None
        return updated

    def fail_message(self, message_id: str, error: str, cancelled: bool = False):
        current = self.storage.get_message(message_id)
        if current is None:
            raise ValueError(f"Message {message_id} not found.")
        self.storage.update_message(
            message_id,
            content=current.content if current.content else ("Generation cancelled." if cancelled else "Generation failed."),
            status="cancelled" if cancelled else "failed",
            error=error,
        )
        updated = self.storage.get_message(message_id)
        assert updated is not None
        return updated

    def regenerate_last_response(self, conversation_id: str) -> PreparedGeneration | None:
        messages = self.storage.list_messages(conversation_id)
        last_assistant = next((message for message in reversed(messages) if message.role == "assistant"), None)
        if last_assistant is None:
            return None
        previous_user = next((message for message in reversed(messages) if message.role == "user"), None)
        if previous_user is None:
            return None
        self.storage.delete_message(last_assistant.message_id)
        return self._prepare_assistant_generation(conversation_id, self.storage.load_settings())

    def parse_action_request(self, message_id: str) -> AssistantAction | None:
        message = self.storage.get_message(message_id)
        if message is None:
            raise ValueError(f"Message {message_id} not found.")
        parsed = extract_action_request(
            message.content,
            conversation_id=message.conversation_id,
            assistant_message_id=message.message_id,
        )
        visible_text = parsed.visible_text if parsed.action is not None else message.content
        self.storage.update_message(message.message_id, content=visible_text)
        if parsed.action is None:
            return None
        persisted = self.storage.create_action(
            conversation_id=parsed.action.conversation_id,
            assistant_message_id=parsed.action.assistant_message_id,
            kind=parsed.action.kind,
            title=parsed.action.title,
            description=parsed.action.description,
            target=parsed.action.target,
            risk=parsed.action.risk,
            payload=parsed.action.payload,
        )
        return persisted

    def get_action(self, action_id: str) -> AssistantAction | None:
        return self.storage.get_action(action_id)

    def mark_action_approved(self, action_id: str) -> AssistantAction:
        return self.storage.update_action(action_id, status="approved")

    def mark_action_denied(self, action_id: str) -> AssistantAction:
        return self.storage.update_action(action_id, status="denied", result_text="User denied the action.")

    def mark_action_executed(self, action_id: str, result_text: str) -> AssistantAction:
        return self.storage.update_action(action_id, status="executed", result_text=result_text, error=None)

    def mark_action_failed(self, action_id: str, error: str) -> AssistantAction:
        return self.storage.update_action(action_id, status="failed", result_text="", error=error)

    def build_action_follow_up(self, action: AssistantAction) -> PreparedGeneration:
        summary = self._format_action_summary(action)
        return self.prepare_follow_up_generation(action.conversation_id, summary)

    def export_conversation_markdown(self, conversation_id: str, destination: Path) -> Path:
        conversation = self.storage.get_conversation(conversation_id)
        messages = self.storage.list_messages(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")
        lines = [f"# {conversation.title}", ""]
        for message in messages:
            lines.append(f"## {message.role.capitalize()}")
            lines.append("")
            lines.append(message.content)
            lines.append("")
        destination.write_text("\n".join(lines), encoding="utf-8")
        return destination

    def export_conversation_json(self, conversation_id: str, destination: Path) -> Path:
        conversation = self.storage.get_conversation(conversation_id)
        messages = self.storage.list_messages(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")
        payload = {
            "conversation_id": conversation.conversation_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "message_id": message.message_id,
                    "role": message.role,
                    "content": message.content,
                    "status": message.status,
                    "error": message.error,
                    "created_at": message.created_at.isoformat(),
                    "updated_at": message.updated_at.isoformat(),
                }
                for message in messages
            ],
        }
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return destination

    def _prepare_assistant_generation(self, conversation_id: str, settings: AppSettings) -> PreparedGeneration:
        provider_id = settings.provider_id or DEFAULT_PROVIDER_ID
        provider = self.providers.get(provider_id)
        health = provider.health_check(settings.provider_configs.get(provider_id, {}), settings.model or DEFAULT_MODEL)
        if health.status != "ready":
            raise ProviderError(health.detail)

        assistant_message = self.storage.add_message(conversation_id, "assistant", "", status="streaming")
        request = self._build_generation_request(conversation_id, assistant_message.message_id, settings)
        conversation = self.storage.get_conversation(conversation_id)
        assert conversation is not None
        return PreparedGeneration(conversation=conversation, assistant_message=assistant_message, request=request)

    def _build_generation_request(self, conversation_id: str, assistant_message_id: str, settings: AppSettings):
        from ..models import GenerationRequest

        provider_id = settings.provider_id or DEFAULT_PROVIDER_ID
        request_messages = self._build_prompt_messages(conversation_id, settings)
        return GenerationRequest(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            provider_id=provider_id,
            provider_config=settings.provider_configs.get(provider_id, {}),
            model=settings.model or DEFAULT_MODEL,
            messages=request_messages,
            temperature=settings.temperature,
            top_p=settings.top_p,
            max_tokens=settings.max_tokens,
        )

    def _build_prompt_messages(self, conversation_id: str, settings: AppSettings) -> list[ChatMessage]:
        prompt_messages = [ChatMessage(role="system", content=self._compose_system_prompt(settings.system_prompt))]
        for message in self.storage.list_messages(conversation_id):
            if message.role == "assistant" and message.status in {"failed", "cancelled", "streaming"} and not message.content.strip():
                continue
            prompt_messages.append(ChatMessage(role=message.role, content=message.content))
        return prompt_messages

    def _compose_system_prompt(self, base_prompt: str) -> str:
        normalized = base_prompt.strip() if base_prompt.strip() else DEFAULT_SYSTEM_PROMPT
        return f"{normalized}\n\n{ACTION_PROTOCOL_PROMPT}"

    def _ensure_conversation(self, conversation_id: str | None, user_text: str) -> ConversationSummary:
        if conversation_id:
            conversation = self.storage.get_conversation(conversation_id)
            if conversation is not None:
                return conversation
        title = self._derive_title(user_text)
        conversation = self.storage.create_conversation(title)
        settings = self.storage.load_settings()
        settings.last_conversation_id = conversation.conversation_id
        self.storage.save_settings(settings)
        return conversation

    def _format_action_summary(self, action: AssistantAction) -> str:
        status = action.status.upper()
        details = action.result_text if action.result_text else (action.error or "")
        return (
            "ACTION_RESULT\n"
            f"kind: {action.kind}\n"
            f"target: {action.target}\n"
            f"status: {status}\n"
            f"details:\n{details.strip()}"
        )

    @staticmethod
    def _derive_title(text: str, limit: int = 48) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[: limit - 3].rstrip()}..."
