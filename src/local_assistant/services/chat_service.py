from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from ..actions import extract_action_request
from ..config import (
    APP_VERSION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
)
from ..exceptions import ProviderError
from ..models import (
    AppSettings,
    AppState,
    AssistantAction,
    ChatMessage,
    ConversationSummary,
    InstalledLocalModel,
    LocalModelDescriptor,
    ModelDescriptor,
    PreparedGeneration,
    ProviderDescriptor,
    ProviderHealth,
)
from ..providers import ProviderRegistry
from ..storage import Storage, utcnow
from .local_runtime_service import LocalRuntimeService
from .model_catalog_service import ModelCatalogService
from .model_download_service import ModelDownloadService
from .update_service import InstallerLaunchPlan, PatchLaunchPlan, RuntimeRefreshResult, RuntimeStatus, UpdateService


ACTION_PROTOCOL_PROMPT = """
You are allowed to request external actions, but you must never assume they were executed.
When you need a web request, file action, or command, output a single machine-readable block:
<ACTION_REQUEST>
{"kind":"web_fetch","title":"Open the source page","description":"Need to read the original content","target":"https://example.com/article","risk":"low","payload":{"url":"https://example.com/article"}}
</ACTION_REQUEST>
Use `web_fetch` as the canonical kind. `web_request` is accepted only for compatibility.
Keep JSON keys and machine fields in English. `risk` must stay `low`, `medium`, or `high`.
For local desktop apps such as Telegram, never use `web_fetch`, never use localhost URLs, and never pretend the app was opened.
Use `command_run` only when you can name one concrete local command that the user can explicitly approve first.
If you cannot safely express the action as one concrete command, do not output ACTION_REQUEST at all. Reply in plain text and ask for the exact local script or command path.
If you cannot produce a fully valid action block, do not output ACTION_REQUEST at all. Reply with normal text instead.
Wait for a system message with the action result before continuing.
""".strip()

CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁё]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


class ChatService:
    def __init__(
        self,
        storage: Storage,
        providers: ProviderRegistry,
        update_service: UpdateService,
        catalog_service: ModelCatalogService | None = None,
        runtime_service: LocalRuntimeService | None = None,
        download_service: ModelDownloadService | None = None,
    ) -> None:
        self.storage = storage
        self.providers = providers
        self.update_service = update_service
        self.catalog_service = catalog_service or ModelCatalogService()
        self.runtime_service = runtime_service or LocalRuntimeService(
            paths=type("RuntimePaths", (), {
                "logs_dir": Path(gettempdir()),
                "runtime_dir": Path(gettempdir()),
                "models_dir": Path(gettempdir()),
            })()
        )
        self.download_service = download_service or ModelDownloadService(Path(gettempdir()))

    def initialize(self) -> AppState:
        self.storage.initialize()
        self._sync_installed_models_with_disk()
        return AppState(
            settings=self.storage.load_settings(),
            conversations=self.storage.list_conversations(),
            providers=self.providers.list_descriptors(),
        )

    def load_settings(self) -> AppSettings:
        return self.storage.load_settings()

    def save_settings(self, settings: AppSettings) -> None:
        self.storage.save_settings(settings)

    def get_runtime_status(self) -> RuntimeStatus:
        release_state = self.storage.load_release_state()
        return RuntimeStatus(
            current_version=APP_VERSION,
            latest_version=release_state.get("latest_version", ""),
            release_url=release_state.get("release_url", ""),
            installer_url=release_state.get("installer_url", ""),
            patch_url=release_state.get("patch_url", ""),
            manifest_url=release_state.get("manifest_url", ""),
            installer_available=bool(release_state.get("installer_available", False)),
            patch_available=bool(release_state.get("patch_available", False)),
            update_kind=str(release_state.get("update_kind", "installer") or "installer"),
            last_check_status=release_state.get("last_check_status", "idle"),
            last_check_error=release_state.get("last_check_error", ""),
            last_checked_at=release_state.get("last_checked_at", ""),
            update_available=bool(release_state.get("update_available", False)),
            repair_required=bool(release_state.get("repair_required", False)),
            repair_reason=release_state.get("repair_reason", ""),
        )

    def refresh_runtime_configuration(self) -> RuntimeRefreshResult:
        self._sync_installed_models_with_disk()
        release_check = self.update_service.check_latest_release()
        local_status, local_detail, active_model_id, runtime_ready, repair_required, repair_reason = self._refresh_local_runtime()
        provider_models = self.list_models("local_llama")
        local_models = self.list_local_models()
        installed_local_models = self.list_installed_local_models()
        provider_health = ProviderHealth(
            status=local_status if local_status in {"ready", "missing_runtime", "missing_model"} else "error",
            detail=local_detail,
            models=provider_models,
        )
        release_error = release_check.error.strip()
        status = RuntimeStatus(
            current_version=APP_VERSION,
            latest_version=release_check.latest_version,
            release_url=release_check.release_url,
            installer_url=release_check.installer_url,
            patch_url=release_check.patch_url,
            manifest_url=release_check.manifest_url,
            installer_available=release_check.installer_available,
            patch_available=release_check.patch_available,
            update_kind=release_check.update_kind,
            last_check_status="update_available" if release_check.update_available else ("error" if release_error else "ok"),
            last_check_error=release_error,
            last_checked_at=utcnow(),
            update_available=release_check.update_available,
            repair_required=repair_required or release_check.requires_runtime_replace,
            repair_reason=repair_reason,
        )
        self.storage.save_release_state(
            {
                "latest_version": status.latest_version,
                "release_url": status.release_url,
                "installer_url": status.installer_url,
                "patch_url": status.patch_url,
                "manifest_url": status.manifest_url,
                "installer_available": status.installer_available,
                "patch_available": status.patch_available,
                "update_kind": status.update_kind,
                "last_check_status": status.last_check_status,
                "last_check_error": status.last_check_error,
                "last_checked_at": status.last_checked_at,
                "update_available": status.update_available,
                "repair_required": status.repair_required,
                "repair_reason": status.repair_reason,
            }
        )
        return RuntimeRefreshResult(
            status=status,
            update_available=status.update_available,
            local_status=local_status,
            local_detail=local_detail,
            active_model_id=active_model_id,
            runtime_ready=runtime_ready,
            installer_url=status.installer_url,
            patch_url=status.patch_url,
            manifest_url=status.manifest_url,
            installer_available=status.installer_available,
            patch_available=status.patch_available,
            update_kind=status.update_kind,
            repair_required=status.repair_required,
            repair_reason=status.repair_reason,
            error=release_error,
            provider_health=provider_health,
            provider_models=provider_models,
            local_models=local_models,
            installed_local_models=installed_local_models,
            runtime_binary_available=local_status != "missing_runtime",
        )

    def _refresh_local_runtime(self) -> tuple[str, str, str, bool, bool, str]:
        try:
            self.providers.get("local_llama")
        except Exception:  # noqa: BLE001
            return "error", "", "", False, False, ""

        settings = self.storage.load_settings()
        active_model_id = settings.model.strip() or DEFAULT_MODEL
        installed = self.storage.get_installed_model(active_model_id)
        if installed is None:
            return "missing_model", "Selected local model is not installed.", active_model_id, False, False, ""

        runtime_verification = self.runtime_service.verify_runtime_bundle()
        if runtime_verification.status != "ready":
            detail = runtime_verification.detail or "Bundled local runtime is missing from this installation."
            status = "missing_runtime" if runtime_verification.status == "missing_binary" else "error"
            return status, detail, active_model_id, False, True, detail

        descriptor = self.catalog_service.get_model(active_model_id)
        context_length = descriptor.context_length if descriptor else 8192
        try:
            self.runtime_service.ensure_runtime(installed.file_path, int(context_length))
        except ProviderError as exc:
            detail = str(exc).strip()
            lowered = detail.lower()
            if "missing" in lowered or "not installed" in lowered:
                return "missing_runtime", detail, active_model_id, False, True, detail
            return "error", detail or "Local runtime could not start.", active_model_id, False, True, detail or "Local runtime could not start."
        return "ready", "Local runtime is ready.", active_model_id, True, False, ""

    def prepare_installer_handoff(self, *, prefer_latest: bool = False) -> InstallerLaunchPlan:
        status = self.get_runtime_status()
        return self.update_service.prepare_installer(
            status.installer_url,
            status.manifest_url,
            prefer_latest=prefer_latest,
        )

    def prepare_patch_handoff(self) -> PatchLaunchPlan:
        status = self.get_runtime_status()
        return self.update_service.prepare_patch(
            status.patch_url,
            status.manifest_url,
            current_version=APP_VERSION,
        )

    def launch_installer(self, installer_path: Path) -> None:
        self.update_service.launch_installer(installer_path)

    def launch_patch_update(self, patch_path: Path, *, current_pid: int) -> None:
        self.update_service.launch_patch_updater(patch_path, current_pid=current_pid)

    def list_provider_descriptors(self) -> list[ProviderDescriptor]:
        return self.providers.list_descriptors()

    def list_models(self, provider_id: str) -> list[ModelDescriptor]:
        settings = self.storage.load_settings()
        provider = self.providers.get(provider_id)
        return provider.list_models(self._provider_config(settings, provider_id))

    def list_local_models(self) -> list[LocalModelDescriptor]:
        return self.catalog_service.list_models()

    def list_installed_local_models(self) -> list[InstalledLocalModel]:
        return self.storage.list_installed_models()

    def get_installed_local_model(self, model_id: str) -> InstalledLocalModel | None:
        return self.storage.get_installed_model(model_id)

    def install_local_model(self, model_id: str, cancel_event, progress_callback) -> InstalledLocalModel:
        descriptor = self.catalog_service.get_model(model_id)
        if descriptor is None:
            raise ProviderError(f"Unknown local model: {model_id}")
        discover_existing = getattr(self.download_service, "discover_existing", None)
        existing = discover_existing(descriptor) if callable(discover_existing) else None
        if existing is not None:
            self.storage.save_installed_model(existing)
            settings = self.storage.load_settings()
            settings.model = existing.model_id
            self.storage.save_settings(settings)
            return existing
        installed = self.download_service.download(descriptor, cancel_event, progress_callback)
        self.storage.save_installed_model(installed)
        settings = self.storage.load_settings()
        settings.model = installed.model_id
        self.storage.save_settings(settings)
        return installed

    def install_recommended_local_model(self, cancel_event, progress_callback) -> InstalledLocalModel:
        descriptor = self.catalog_service.get_recommended_model()
        if descriptor is None:
            raise ProviderError("No recommended local model is available in the bundled catalog.")
        return self.install_local_model(descriptor.model_id, cancel_event, progress_callback)

    def remove_local_model(self, model_id: str) -> None:
        removed = self.storage.remove_installed_model(model_id)
        self.download_service.remove(removed)
        if removed:
            self.runtime_service.stop()
            if self.storage.load_settings().model == model_id:
                settings = self.storage.load_settings()
                fallback = next(iter(self.storage.list_installed_models()), None)
                settings.model = fallback.model_id if fallback else DEFAULT_MODEL
                self.storage.save_settings(settings)

    def get_provider_health(self, provider_id: str, model: str) -> ProviderHealth:
        settings = self.storage.load_settings()
        provider = self.providers.get(provider_id)
        return provider.health_check(self._provider_config(settings, provider_id), model)

    def get_source_health(self, source: str = "local") -> ProviderHealth:
        _ = source
        settings = self.storage.load_settings()
        provider_id, model = self._resolve_provider_and_model(settings)
        provider = self.providers.get(provider_id)
        return provider.health_check(self._provider_config(settings, provider_id), model)

    def get_chat_source(self, conversation_id: str | None, draft_source: str | None = None) -> str:
        _ = conversation_id
        _ = draft_source
        return "local"

    def set_conversation_source(self, conversation_id: str, source_override: str | None) -> ConversationSummary:
        _ = source_override
        return self.storage.update_conversation_source(conversation_id, None)

    def load_conversations(self) -> list[ConversationSummary]:
        return self.storage.list_conversations()

    def load_messages(self, conversation_id: str):
        return self.storage.list_messages(conversation_id)

    def set_last_conversation(self, conversation_id: str | None) -> AppSettings:
        settings = self.storage.load_settings()
        settings.last_conversation_id = conversation_id
        self.storage.save_settings(settings)
        return settings

    def prepare_user_generation(
        self,
        conversation_id: str | None,
        user_text: str,
        source_override: str | None = None,
    ) -> PreparedGeneration:
        settings = self.storage.load_settings()
        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("User message cannot be empty.")

        conversation = self._ensure_conversation(conversation_id, normalized_text)
        _ = source_override
        detected_language = self._detect_message_language(normalized_text, settings.language, conversation.conversation_id)
        self.storage.add_message(
            conversation.conversation_id,
            "user",
            normalized_text,
            status="completed",
            metadata={"detected_language": detected_language},
        )
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

    def update_message_metadata(self, message_id: str, metadata: dict[str, Any]) -> None:
        current = self.storage.get_message(message_id)
        if current is None:
            raise ValueError(f"Message {message_id} not found.")
        merged = dict(current.metadata)
        merged.update(metadata)
        self.storage.update_message(message_id, metadata=merged)

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
        visible_text = parsed.visible_text if parsed.had_action_block else message.content
        metadata = dict(message.metadata)
        if parsed.had_action_block:
            metadata["action_block_seen"] = True
            if parsed.action_parse_error:
                metadata["action_parse_error"] = parsed.action_parse_error
            if parsed.action_autofixed:
                metadata["action_autofixed"] = True
        if parsed.had_action_block and parsed.action is None and not visible_text.strip():
            visible_text = self._invalid_action_fallback_for_error(message.conversation_id, parsed.action_parse_error)
        self.storage.update_message(message.message_id, content=visible_text, metadata=metadata)
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
                    "metadata": message.metadata,
                    "created_at": message.created_at.isoformat(),
                    "updated_at": message.updated_at.isoformat(),
                }
                for message in messages
            ],
        }
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return destination

    def _prepare_assistant_generation(self, conversation_id: str, settings: AppSettings) -> PreparedGeneration:
        provider_id, model = self._resolve_provider_and_model(settings)
        provider = self.providers.get(provider_id)
        health = provider.health_check(self._provider_config(settings, provider_id), model)
        if health.status != "ready":
            raise ProviderError(health.detail)

        assistant_message = self.storage.add_message(conversation_id, "assistant", "", status="streaming")
        request = self._build_generation_request(conversation_id, assistant_message.message_id, settings)
        conversation = self.storage.get_conversation(conversation_id)
        assert conversation is not None
        return PreparedGeneration(conversation=conversation, assistant_message=assistant_message, request=request)

    def _build_generation_request(
        self,
        conversation_id: str,
        assistant_message_id: str,
        settings: AppSettings,
    ):
        from ..models import GenerationRequest

        provider_id, model = self._resolve_provider_and_model(settings)
        request_messages = self._build_prompt_messages(conversation_id, settings)
        return GenerationRequest(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            provider_id=provider_id,
            provider_config=self._provider_config(settings, provider_id),
            model=model,
            messages=request_messages,
            reasoning_enabled=settings.reasoning_enabled,
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_tokens=DEFAULT_MAX_TOKENS,
        )

    def _build_prompt_messages(self, conversation_id: str, settings: AppSettings) -> list[ChatMessage]:
        target_language = self._resolve_conversation_language(conversation_id, settings.language)
        prompt_messages = [ChatMessage(role="system", content=self._compose_system_prompt(settings.system_prompt, target_language))]
        for message in self.storage.list_messages(conversation_id):
            if message.role == "assistant" and message.status in {"failed", "cancelled", "streaming"} and not message.content.strip():
                continue
            prompt_messages.append(
                ChatMessage(
                    role=message.role,
                    content=message.content,
                    reasoning_details=message.metadata.get("reasoning_details") if message.role == "assistant" else None,
                )
            )
        return prompt_messages

    def _compose_system_prompt(self, base_prompt: str, response_language: str) -> str:
        normalized = base_prompt.strip() if base_prompt.strip() else DEFAULT_SYSTEM_PROMPT
        return f"{normalized}\n\n{self._language_lock_prompt(response_language)}\n\n{ACTION_PROTOCOL_PROMPT}"

    def _resolve_conversation_language(self, conversation_id: str, fallback_language: str) -> str:
        messages = self.storage.list_messages(conversation_id)
        for message in reversed(messages):
            if message.role != "user":
                continue
            detected = str(message.metadata.get("detected_language", "")).strip()
            if detected in {"ru", "en"}:
                return detected
            if message.content.strip():
                return self._detect_message_language(message.content, fallback_language, conversation_id)
        return fallback_language if fallback_language in {"ru", "en"} else "en"

    def _detect_message_language(self, text: str, fallback_language: str, conversation_id: str | None = None) -> str:
        cyrillic_count = len(CYRILLIC_PATTERN.findall(text))
        latin_count = len(LATIN_PATTERN.findall(text))
        if cyrillic_count and latin_count:
            for char in text:
                if CYRILLIC_PATTERN.match(char):
                    return "ru"
                if LATIN_PATTERN.match(char):
                    return "en"
        if cyrillic_count > latin_count:
            return "ru"
        if latin_count > cyrillic_count:
            return "en"
        if conversation_id:
            previous_language = self._last_detected_user_language(conversation_id)
            if previous_language:
                return previous_language
        return fallback_language if fallback_language in {"ru", "en"} else "en"

    def _last_detected_user_language(self, conversation_id: str) -> str | None:
        for message in reversed(self.storage.list_messages(conversation_id)):
            if message.role != "user":
                continue
            detected = str(message.metadata.get("detected_language", "")).strip()
            if detected in {"ru", "en"}:
                return detected
        return None

    def _invalid_action_fallback(self, conversation_id: str) -> str:
        language = self._resolve_conversation_language(conversation_id, self.storage.load_settings().language)
        if language == "ru":
            return "Не удалось корректно подготовить действие. Попробуйте сформулировать запрос обычным текстом еще раз."
        return "I could not prepare that action correctly. Please try the request again in plain text."

    def _invalid_action_fallback_for_error(self, conversation_id: str, parse_error: str = "") -> str:
        normalized_error = parse_error.strip().lower()
        language = self._resolve_conversation_language(conversation_id, self.storage.load_settings().language)
        if "localhost" in normalized_error or "loopback" in normalized_error or "127.0.0.1" in normalized_error:
            if language == "ru":
                return (
                    "Эта сборка не открывает локальные приложения через web_fetch. "
                    "Для действий в Telegram нужна конкретная локальная команда и явное подтверждение пользователя."
                )
            return (
                "This build cannot open local desktop apps through web_fetch. "
                "Telegram actions require one concrete local command and explicit user approval."
            )
        if language == "ru":
            return "Не удалось корректно подготовить действие. Попробуйте сформулировать запрос обычным текстом ещё раз."
        return "I could not prepare that action correctly. Please try the request again in plain text."

    @staticmethod
    def _language_lock_prompt(response_language: str) -> str:
        if response_language == "ru":
            return (
                "Respond only in Russian because the user's latest natural-language message is in Russian. "
                "Do not switch to English unless the user explicitly switches language. "
                "Do not translate code, file paths, URLs, commands, JSON keys, or model identifiers."
            )
        return (
            "Respond only in English because the user's latest natural-language message is in English. "
            "Do not switch to Russian unless the user explicitly switches language. "
            "Do not translate code, file paths, URLs, commands, JSON keys, or model identifiers."
        )

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

    @staticmethod
    def _resolve_provider_and_model(settings: AppSettings) -> tuple[str, str]:
        return "local_llama", settings.model.strip() or DEFAULT_MODEL

    def _provider_config(self, settings: AppSettings, provider_id: str) -> dict[str, str]:
        provider_config = dict(settings.provider_configs.get(provider_id, {}))
        if provider_id == "local_llama":
            descriptor = self.catalog_service.get_model(settings.model.strip() or DEFAULT_MODEL)
            provider_config["context_length"] = str(descriptor.context_length if descriptor else 8192)
        return provider_config

    def _sync_installed_models_with_disk(self) -> None:
        known_models = {item.model_id: item for item in self.storage.list_installed_models()}
        discovered_any = False
        for descriptor in self.catalog_service.list_models():
            if descriptor.model_id in known_models:
                continue
            discover_existing = getattr(self.download_service, "discover_existing", None)
            discovered = discover_existing(descriptor) if callable(discover_existing) else None
            if discovered is None:
                continue
            self.storage.save_installed_model(discovered)
            discovered_any = True
        if not discovered_any:
            return
        settings = self.storage.load_settings()
        installed_models = self.storage.list_installed_models()
        installed_ids = {item.model_id for item in installed_models}
        if settings.model not in installed_ids:
            fallback = next((item.model_id for item in installed_models), DEFAULT_MODEL)
            settings.model = fallback
            self.storage.save_settings(settings)
