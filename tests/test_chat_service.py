from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.config import DEFAULT_MODEL
from local_assistant.exceptions import ProviderError
from local_assistant.models import AssistantAction, GenerationRequest, InstalledLocalModel, ModelDescriptor, ProviderDescriptor, ProviderHealth
from local_assistant.services import ChatService
from local_assistant.services.update_service import PatchLaunchPlan, ReleaseCheck, RuntimeManifest, UpdateService
from local_assistant.storage import Storage


class FakeProvider:
    descriptor = ProviderDescriptor(
        provider_id="local_llama",
        display_name="Local Qwen",
        description_key="provider_local_desc",
    )

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        if not desired_model.strip():
            return ProviderHealth(status="missing_model", detail="missing model", models=[])
        return ProviderHealth(
            status="ready",
            detail="ready",
            models=[ModelDescriptor(model_id=desired_model, display_name=desired_model)],
        )

    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        return [ModelDescriptor(model_id="demo-model", display_name="demo-model")]

    def stream_chat(self, request: GenerationRequest, cancel_event: Event):
        _ = request
        _ = cancel_event
        yield "chunk-1"
        yield "chunk-2"


class FakeRegistry:
    def __init__(self) -> None:
        self.providers = {"local_llama": FakeProvider()}

    def list_descriptors(self) -> list[ProviderDescriptor]:
        return [provider.descriptor for provider in self.providers.values()]

    def get(self, provider_id: str) -> FakeProvider:
        provider = self.providers.get(provider_id)
        if provider is None:
            raise KeyError(provider_id)
        return provider


class FakeUpdateService(UpdateService):
    def __init__(self) -> None:
        super().__init__(manifest_path=Path("unused.json"))
        self.release_check = ReleaseCheck(current_version="0.1.0")
        self.remote_manifest = RuntimeManifest(source="remote")
        self.prepared_installer = Path("C:/temp/LocalAssistantSetup.exe")

    def load_bundled_manifest(self) -> RuntimeManifest:
        return RuntimeManifest(source="bundled")

    def fetch_runtime_manifest(self) -> RuntimeManifest:
        return self.remote_manifest

    def check_latest_release(self) -> ReleaseCheck:
        return self.release_check

    def prepare_installer(self, installer_url: str = "", manifest_url: str = "", *, prefer_latest: bool = False):
        _ = installer_url
        _ = manifest_url
        _ = prefer_latest
        from local_assistant.services.update_service import InstallerLaunchPlan

        return InstallerLaunchPlan(installer_path=self.prepared_installer, source="local")

    def launch_installer(self, installer_path: Path) -> None:
        self.launched_installer = installer_path

    def prepare_patch(self, patch_url: str = "", manifest_url: str = "", *, current_version: str = ""):
        _ = patch_url
        _ = manifest_url
        _ = current_version
        return PatchLaunchPlan(patch_path=Path("C:/temp/LocalAssistantPatch.zip"), source="downloaded")

    def launch_patch_updater(self, patch_path: Path, *, current_pid: int) -> None:
        self.launched_patch = (patch_path, current_pid)


class FakeRuntimeService:
    def __init__(self, *, binary_available: bool = False, ensure_error: str | None = None) -> None:
        self.binary_available = binary_available
        self.ensure_error = ensure_error
        self.ensure_calls: list[tuple[str, int]] = []

    def runtime_binary_path(self):
        return Path("runtime/llama-server.exe") if self.binary_available else None

    def is_binary_available(self) -> bool:
        return self.binary_available

    def verify_runtime_bundle(self):
        from local_assistant.services.local_runtime_service import RuntimeVerification

        if self.binary_available:
            return RuntimeVerification(status="ready", binary_path=Path("runtime/llama-server.exe"))
        return RuntimeVerification(status="missing_binary", detail="Bundled local runtime is missing from this installation.")

    def ensure_runtime(self, model_path: str, context_length: int = 8192) -> None:
        self.ensure_calls.append((model_path, context_length))
        if self.ensure_error:
            from local_assistant.exceptions import ProviderError

            raise ProviderError(self.ensure_error)

    def stop(self) -> None:
        return


class ChatServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "app.sqlite3"
        storage = Storage(db_path)
        self.service = ChatService(
            storage=storage,
            providers=FakeRegistry(),
            update_service=FakeUpdateService(),
        )
        self.service.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_prepare_user_generation_uses_local_provider_and_model(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Explain WAL mode.")

        self.assertEqual(prepared.assistant_message.status, "streaming")
        self.assertEqual(prepared.request.provider_id, "local_llama")
        self.assertTrue(prepared.request.model)
        self.assertEqual(prepared.request.messages[-1].content, "Explain WAL mode.")

    def test_chat_source_is_always_local(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Use local model.")

        self.assertEqual(prepared.request.provider_id, "local_llama")
        self.assertEqual(self.service.get_chat_source(prepared.conversation.conversation_id), "local")
        self.assertIsNone(prepared.conversation.source_override)

    def test_refresh_runtime_configuration_reports_missing_model_cleanly(self) -> None:
        result = self.service.refresh_runtime_configuration()

        self.assertEqual(result.local_status, "missing_model")
        self.assertFalse(result.runtime_ready)
        self.assertIsNotNone(result.provider_health)
        self.assertIsInstance(result.provider_models, list)
        self.assertIsInstance(result.local_models, list)
        self.assertIsInstance(result.installed_local_models, list)

    def test_install_local_model_sets_active_model(self) -> None:
        class FakeCatalog:
            def get_model(self, model_id: str):
                return type("Descriptor", (), {"model_id": model_id, "context_length": 8192})()

            def list_models(self):
                return []

            def to_provider_models(self):
                return []

            def get_recommended_model(self):
                return None

        class FakeDownload:
            def download(self, descriptor, cancel_event, progress_callback):
                _ = descriptor
                _ = cancel_event
                _ = progress_callback
                return InstalledLocalModel(
                    model_id="demo-installed",
                    file_path="C:/models/demo.gguf",
                    file_name="demo.gguf",
                    source="hf",
                    downloaded_at="2026-03-16T00:00:00+00:00",
                    size_bytes=123,
                )

        self.service.catalog_service = FakeCatalog()
        self.service.download_service = FakeDownload()

        self.service.install_local_model("demo-installed", Event(), lambda _progress: None)

        self.assertEqual(self.service.load_settings().model, "demo-installed")

    def test_install_recommended_local_model_uses_catalog_recommended_entry(self) -> None:
        class FakeCatalog:
            def __init__(self) -> None:
                self.requested_model_id = None

            def get_model(self, model_id: str):
                self.requested_model_id = model_id
                return type("Descriptor", (), {"model_id": model_id, "context_length": 8192})()

            def get_recommended_model(self):
                return type("Descriptor", (), {"model_id": "recommended-model"})()

            def list_models(self):
                return []

            def to_provider_models(self):
                return []

        class FakeDownload:
            def download(self, descriptor, cancel_event, progress_callback):
                _ = cancel_event
                _ = progress_callback
                return InstalledLocalModel(
                    model_id=descriptor.model_id,
                    file_path="C:/models/recommended.gguf",
                    file_name="recommended.gguf",
                    source="hf",
                    downloaded_at="2026-03-16T00:00:00+00:00",
                    size_bytes=456,
                )

        fake_catalog = FakeCatalog()
        self.service.catalog_service = fake_catalog
        self.service.download_service = FakeDownload()

        installed = self.service.install_recommended_local_model(Event(), lambda _progress: None)

        self.assertEqual(installed.model_id, "recommended-model")
        self.assertEqual(fake_catalog.requested_model_id, "recommended-model")
        self.assertEqual(self.service.load_settings().model, "recommended-model")

    def test_prepare_user_generation_stores_detected_russian_language(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Привет, расскажи кратко про SQLite.")
        user_messages = self.service.load_messages(prepared.conversation.conversation_id)

        self.assertEqual(user_messages[0].metadata.get("detected_language"), "ru")
        self.assertIn("Respond only in Russian", prepared.request.messages[0].content)

    def test_prepare_user_generation_stores_detected_english_language(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Explain SQLite briefly.")
        user_messages = self.service.load_messages(prepared.conversation.conversation_id)

        self.assertEqual(user_messages[0].metadata.get("detected_language"), "en")
        self.assertIn("Respond only in English", prepared.request.messages[0].content)

    def test_mixed_message_prefers_main_natural_language(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Сделай summary for this SQL query.")
        user_messages = self.service.load_messages(prepared.conversation.conversation_id)

        self.assertEqual(user_messages[0].metadata.get("detected_language"), "ru")
        self.assertIn("Respond only in Russian", prepared.request.messages[0].content)

    def test_follow_up_generation_uses_last_user_language(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Explain SQLite briefly.")

        follow_up = self.service.prepare_follow_up_generation(prepared.conversation.conversation_id, "ACTION_RESULT\nstatus: EXECUTED")

        self.assertIn("Respond only in English", follow_up.request.messages[0].content)

    def test_parse_action_request_preserves_visible_text_on_invalid_block(self) -> None:
        conversation = self.service.storage.create_conversation("Broken action")
        self.service.storage.add_message(
            conversation.conversation_id,
            "user",
            "Объясни ответ обычным текстом.",
            status="completed",
            metadata={"detected_language": "ru"},
        )
        message = self.service.storage.add_message(
            conversation.conversation_id,
            "assistant",
            'Нормальный ответ.\n<ACTION_REQUEST>{"kind":"web_request","title":"Привет","description":"Приветствен!""}</ACTION_REQUEST>',
            status="completed",
        )

        action = self.service.parse_action_request(message.message_id)
        updated = self.service.storage.get_message(message.message_id)

        self.assertIsNone(action)
        assert updated is not None
        self.assertEqual(updated.content, "Нормальный ответ.")
        self.assertIn("action_parse_error", updated.metadata)

    def test_parse_action_request_adds_ru_fallback_for_invalid_action_only_response(self) -> None:
        conversation = self.service.storage.create_conversation("Broken action only")
        self.service.storage.add_message(
            conversation.conversation_id,
            "user",
            "Сходи на сайт и проверь.",
            status="completed",
            metadata={"detected_language": "ru"},
        )
        message = self.service.storage.add_message(
            conversation.conversation_id,
            "assistant",
            '<ACTION_REQUEST>{"kind":"web_request","title":"привет","description":"кто вы","target":"human-readable target","risk":"low","payload":{}}</ACTION_REQUEST>',
            status="completed",
        )

        action = self.service.parse_action_request(message.message_id)
        updated = self.service.storage.get_message(message.message_id)

        self.assertIsNone(action)
        assert updated is not None
        self.assertIn("Не удалось корректно подготовить действие", updated.content)
        self.assertIn("action_parse_error", updated.metadata)

    def test_parse_action_request_marks_safe_autofix_metadata(self) -> None:
        conversation = self.service.storage.create_conversation("Autofix action")
        message = self.service.storage.add_message(
            conversation.conversation_id,
            "assistant",
            '<ACTION_REQUEST>{"kind":"web_request","title":"Fetch page","description":"Need source","target":"https://example.com","payload":{}}</ACTION_REQUEST>',
            status="completed",
        )

        action = self.service.parse_action_request(message.message_id)
        updated = self.service.storage.get_message(message.message_id)

        assert action is not None
        assert updated is not None
        self.assertEqual(action.payload["url"], "https://example.com")
        self.assertTrue(updated.metadata.get("action_autofixed"))

    def test_parse_action_request_uses_telegram_local_command_fallback_for_localhost_web_fetch(self) -> None:
        conversation = self.service.storage.create_conversation("Telegram action")
        self.service.storage.add_message(
            conversation.conversation_id,
            "user",
            "Открой Telegram и отправь сообщение.",
            status="completed",
            metadata={"detected_language": "ru"},
        )
        message = self.service.storage.add_message(
            conversation.conversation_id,
            "assistant",
            '<ACTION_REQUEST>{"kind":"web_fetch","title":"Open Telegram","description":"Need to interact with Telegram application","target":"http://127.0.0.1:1313","risk":"low","payload":{"url":"http://127.0.0.1:1313"}}</ACTION_REQUEST>',
            status="completed",
        )

        action = self.service.parse_action_request(message.message_id)
        updated = self.service.storage.get_message(message.message_id)

        self.assertIsNone(action)
        assert updated is not None
        self.assertIn("Telegram", updated.content)
        self.assertIn("команда", updated.content)
        self.assertIn("action_parse_error", updated.metadata)

    def test_refresh_runtime_configuration_reports_ready_when_runtime_starts(self) -> None:
        self.service.runtime_service = FakeRuntimeService(binary_available=True)
        self.service.storage.save_installed_model(
            InstalledLocalModel(
                model_id=DEFAULT_MODEL,
                file_path="C:/models/qwen.gguf",
                file_name="qwen.gguf",
                source="hf",
                downloaded_at="2026-03-16T00:00:00+00:00",
                size_bytes=123,
            )
        )

        result = self.service.refresh_runtime_configuration()

        self.assertEqual(result.local_status, "ready")
        self.assertTrue(result.runtime_ready)
        self.assertTrue(result.runtime_binary_available)
        self.assertEqual(self.service.runtime_service.ensure_calls[0][0], "C:/models/qwen.gguf")

    def test_refresh_runtime_configuration_reports_missing_bundled_runtime(self) -> None:
        self.service.runtime_service = FakeRuntimeService(binary_available=False)
        self.service.storage.save_installed_model(
            InstalledLocalModel(
                model_id=DEFAULT_MODEL,
                file_path="C:/models/qwen.gguf",
                file_name="qwen.gguf",
                source="hf",
                downloaded_at="2026-03-16T00:00:00+00:00",
                size_bytes=123,
            )
        )

        result = self.service.refresh_runtime_configuration()

        self.assertEqual(result.local_status, "missing_runtime")
        self.assertIn("Bundled local runtime is missing", result.local_detail)
        self.assertTrue(result.repair_required)

    def test_prepare_installer_handoff_uses_runtime_status_installer_url(self) -> None:
        self.service.storage.save_release_state(
            {
                "latest_version": "0.2.0",
                "release_url": "https://example.com/release",
                "installer_url": "https://example.com/LocalAssistantSetup.exe",
                "installer_available": True,
                "last_check_status": "update_available",
                "last_check_error": "",
                "last_checked_at": "2026-03-17T10:00:00+00:00",
                "update_available": True,
                "repair_required": False,
                "repair_reason": "",
            }
        )

        plan = self.service.prepare_installer_handoff(prefer_latest=True)

        self.assertEqual(plan.installer_path, Path("C:/temp/LocalAssistantSetup.exe"))

    def test_refresh_runtime_configuration_recovers_existing_model_from_models_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_models_dir:
            model_root = Path(temp_models_dir)
            model_dir = model_root / DEFAULT_MODEL
            model_dir.mkdir(parents=True)
            model_path = model_dir / "model.gguf"
            model_path.write_bytes(b"existing-model")

            class FakeCatalog:
                def list_models(self):
                    return [
                        type(
                            "Descriptor",
                            (),
                            {
                                "model_id": DEFAULT_MODEL,
                                "display_name": "Recovered model",
                                "description": "Recovered from disk",
                                "source": "hf",
                                "download_url": "https://example.com/model.gguf",
                                "file_name": "model.gguf",
                                "context_length": 8192,
                            },
                        )()
                    ]

                def get_model(self, model_id: str):
                    for item in self.list_models():
                        if item.model_id == model_id:
                            return item
                    return None

                def to_provider_models(self):
                    return []

            from local_assistant.services.model_download_service import ModelDownloadService

            self.service.catalog_service = FakeCatalog()
            self.service.download_service = ModelDownloadService(model_root)
            self.service.runtime_service = FakeRuntimeService(binary_available=True)

            result = self.service.refresh_runtime_configuration()

            self.assertEqual(result.local_status, "ready")
            recovered = self.service.get_installed_local_model(DEFAULT_MODEL)
            self.assertIsNotNone(recovered)
            assert recovered is not None
            self.assertEqual(Path(recovered.file_path), model_path)

    def test_install_recommended_local_model_raises_without_catalog_entry(self) -> None:
        class FakeCatalog:
            def get_recommended_model(self):
                return None

        self.service.catalog_service = FakeCatalog()

        with self.assertRaisesRegex(Exception, "No recommended local model"):
            self.service.install_recommended_local_model(Event(), lambda _progress: None)

    def test_prepare_user_generation_rejects_empty_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.service.prepare_user_generation(None, "   ")

    def test_message_helpers_raise_for_missing_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.append_to_message("missing", "chunk")
        with self.assertRaisesRegex(Exception, "not found"):
            self.service.finalize_message("missing")
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.update_message_metadata("missing", {"a": 1})
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.fail_message("missing", "boom")

    def test_message_helpers_update_existing_message(self) -> None:
        conversation = self.service.storage.create_conversation("Lifecycle")
        message = self.service.storage.add_message(conversation.conversation_id, "assistant", "", status="streaming")

        appended = self.service.append_to_message(message.message_id, "hello")
        self.assertEqual(appended.content, "hello")
        finalized = self.service.finalize_message(message.message_id)
        self.assertEqual(finalized.status, "completed")
        self.service.update_message_metadata(message.message_id, {"reasoning": "ok"})
        stored = self.service.storage.get_message(message.message_id)
        assert stored is not None
        self.assertEqual(stored.metadata["reasoning"], "ok")
        failed = self.service.fail_message(message.message_id, "cancelled", cancelled=True)
        self.assertEqual(failed.status, "cancelled")

    def test_regenerate_last_response_handles_missing_history_and_replaces_assistant(self) -> None:
        conversation = self.service.storage.create_conversation("No history")
        self.assertIsNone(self.service.regenerate_last_response(conversation.conversation_id))
        self.service.storage.add_message(conversation.conversation_id, "assistant", "reply", status="completed")
        self.assertIsNone(self.service.regenerate_last_response(conversation.conversation_id))

        prepared = self.service.prepare_user_generation(None, "Explain indexes.")
        self.service.finalize_message(prepared.assistant_message.message_id)
        regenerated = self.service.regenerate_last_response(prepared.conversation.conversation_id)
        assert regenerated is not None
        assistants = [item for item in self.service.load_messages(prepared.conversation.conversation_id) if item.role == "assistant"]
        self.assertEqual(len(assistants), 1)
        self.assertEqual(assistants[0].message_id, regenerated.assistant_message.message_id)

    def test_parse_action_request_missing_message_and_action_transitions(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.parse_action_request("missing")
        self.assertIsNone(self.service.get_action("missing"))

        conversation = self.service.storage.create_conversation("Action flow")
        self.service.storage.add_message(
            conversation.conversation_id,
            "user",
            "Read a file.",
            status="completed",
            metadata={"detected_language": "en"},
        )
        message = self.service.storage.add_message(
            conversation.conversation_id,
            "assistant",
            '<ACTION_REQUEST>{"kind":"file_read","title":"Read file","description":"Need content","target":"note.txt","risk":"medium","payload":{"path":"note.txt"}}</ACTION_REQUEST>',
            status="completed",
        )
        action = self.service.parse_action_request(message.message_id)
        assert action is not None and action.action_id is not None
        self.assertEqual(self.service.mark_action_approved(action.action_id).status, "approved")
        self.assertEqual(self.service.mark_action_denied(action.action_id).status, "denied")
        self.assertEqual(self.service.mark_action_executed(action.action_id, "ok").status, "executed")
        failed = self.service.mark_action_failed(action.action_id, "boom")
        self.assertEqual(failed.status, "failed")
        prepared = self.service.build_action_follow_up(failed)
        self.assertIn("ACTION_RESULT", prepared.request.messages[-1].content)

    def test_exports_and_misc_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "out.md"
            with self.assertRaisesRegex(ValueError, "not found"):
                self.service.export_conversation_markdown("missing", target)
            with self.assertRaisesRegex(ValueError, "not found"):
                self.service.export_conversation_json("missing", target)

        prepared = self.service.prepare_user_generation(None, "Hello there")
        health = self.service.get_provider_health("local_llama", prepared.request.model)
        self.assertEqual(health.status, "ready")
        self.assertEqual(self.service.set_last_conversation(prepared.conversation.conversation_id).last_conversation_id, prepared.conversation.conversation_id)
        self.assertTrue(self.service._derive_title("a" * 80).endswith("..."))  # noqa: SLF001
        self.assertEqual(self.service._resolve_provider_and_model(self.service.load_settings())[0], "local_llama")  # noqa: SLF001

    def test_chat_service_runtime_patch_remove_and_export_helpers(self) -> None:
        update_service = self.service.update_service
        self.service.storage.save_release_state(
            {
                "latest_version": "0.2.1",
                "patch_url": "https://example.com/LocalAssistantPatch.zip",
                "manifest_url": "https://example.com/LocalAssistant-manifest.json",
                "update_kind": "patch",
                "patch_available": True,
            }
        )
        plan = self.service.prepare_patch_handoff()
        self.assertEqual(plan.patch_path, Path("C:/temp/LocalAssistantPatch.zip"))
        self.service.launch_patch_update(Path("C:/temp/LocalAssistantPatch.zip"), current_pid=55)
        self.assertEqual(update_service.launched_patch, (Path("C:/temp/LocalAssistantPatch.zip"), 55))
        self.service.launch_installer(Path("C:/temp/LocalAssistantSetup.exe"))
        self.assertEqual(update_service.launched_installer, Path("C:/temp/LocalAssistantSetup.exe"))

        self.service.storage.save_installed_model(
            InstalledLocalModel(
                model_id="other-model",
                file_path="C:/models/other.gguf",
                file_name="other.gguf",
                source="hf",
                downloaded_at="2026-03-16T00:00:00+00:00",
                size_bytes=123,
            )
        )
        self.service.storage.save_installed_model(
            InstalledLocalModel(
                model_id=DEFAULT_MODEL,
                file_path="C:/models/default.gguf",
                file_name="default.gguf",
                source="hf",
                downloaded_at="2026-03-16T00:00:00+00:00",
                size_bytes=123,
            )
        )
        removed: list[object] = []
        stopped: list[str] = []
        self.service.download_service = type("Download", (), {"remove": lambda _self, item: removed.append(item)})()
        self.service.runtime_service = type("Runtime", (), {"stop": lambda _self: stopped.append("stopped")})()
        settings = self.service.load_settings()
        settings.model = DEFAULT_MODEL
        self.service.save_settings(settings)
        self.service.remove_local_model(DEFAULT_MODEL)
        self.assertEqual(stopped, ["stopped"])
        self.assertEqual(self.service.load_settings().model, "other-model")
        self.assertEqual(getattr(removed[0], "model_id", None), DEFAULT_MODEL)

        prepared = self.service.prepare_user_generation(None, "Export this.")
        self.service.finalize_message(prepared.assistant_message.message_id)
        with tempfile.TemporaryDirectory() as temp_dir:
            md_path = Path(temp_dir) / "chat.md"
            json_path = Path(temp_dir) / "chat.json"
            self.service.export_conversation_markdown(prepared.conversation.conversation_id, md_path)
            self.service.export_conversation_json(prepared.conversation.conversation_id, json_path)
            self.assertIn("# ", md_path.read_text(encoding="utf-8"))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["conversation_id"], prepared.conversation.conversation_id)
            self.assertGreaterEqual(len(payload["messages"]), 2)

    def test_chat_service_runtime_health_language_and_prompt_helpers(self) -> None:
        self.assertEqual(self.service._provider_config(self.service.load_settings(), "local_llama")["context_length"], "8192")  # noqa: SLF001
        self.assertEqual(self.service.get_chat_source(None, "api"), "local")
        conversation = self.service.storage.create_conversation("Title")
        self.assertIsNone(self.service.set_conversation_source(conversation.conversation_id, "api").source_override)

        self.service.storage.add_message(conversation.conversation_id, "user", "Hello", metadata={"detected_language": "en"})
        self.assertEqual(self.service._resolve_conversation_language(conversation.conversation_id, "ru"), "en")  # noqa: SLF001
        self.assertEqual(self.service._detect_message_language("12345", "ru", conversation.conversation_id), "en")  # noqa: SLF001
        self.assertEqual(self.service._detect_message_language("12345", "ru"), "ru")  # noqa: SLF001
        self.assertEqual(self.service._last_detected_user_language(conversation.conversation_id), "en")  # noqa: SLF001
        self.assertIn("Respond only in English", self.service._language_lock_prompt("en"))  # noqa: SLF001
        self.assertIn("ACTION_RESULT", self.service._format_action_summary(AssistantAction(None, "c", "m", "file_read", "Read", "desc", "note.txt", "medium", {"path": "note.txt"}, status="failed", error="boom")))  # noqa: SLF001
        self.assertIn("System prompt", self.service._compose_system_prompt("System prompt", "en"))  # noqa: SLF001
        self.assertTrue(self.service._invalid_action_fallback("conv"))  # noqa: SLF001

        settings = self.service.load_settings()
        settings.model = ""
        self.service.save_settings(settings)
        health = self.service.get_source_health()
        self.assertEqual(health.status, "ready")
        self.assertEqual(self.service.get_provider_health("local_llama", ""), ProviderHealth(status="missing_model", detail="missing model", models=[]))

    def test_chat_service_prepare_and_parse_error_paths(self) -> None:
        class MissingProviderRegistry(FakeRegistry):
            def get(self, provider_id: str):
                raise KeyError(provider_id)

        broken_service = ChatService(
            storage=Storage(Path(self.temp_dir.name) / "broken.sqlite3"),
            providers=MissingProviderRegistry(),
            update_service=FakeUpdateService(),
        )
        broken_service.initialize()
        self.assertEqual(broken_service._refresh_local_runtime(), ("error", "", "", False, False, ""))  # noqa: SLF001

        class MissingHealthProvider(FakeProvider):
            def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
                _ = provider_config
                _ = desired_model
                return ProviderHealth(status="missing_model", detail="need install", models=[])

        registry = FakeRegistry()
        registry.providers["local_llama"] = MissingHealthProvider()
        health_service = ChatService(
            storage=Storage(Path(self.temp_dir.name) / "health.sqlite3"),
            providers=registry,
            update_service=FakeUpdateService(),
        )
        health_service.initialize()
        conv = health_service.storage.create_conversation("Need install")
        with self.assertRaises(ProviderError):
            health_service._prepare_assistant_generation(conv.conversation_id, health_service.load_settings())  # noqa: SLF001

        message = health_service.storage.add_message(conv.conversation_id, "assistant", '<ACTION_REQUEST>{"kind":"web_request","title":"x","description":"y","target":"human-readable target","payload":{}}</ACTION_REQUEST>', status="completed")
        action = health_service.parse_action_request(message.message_id)
        self.assertIsNone(action)
        updated = health_service.storage.get_message(message.message_id)
        self.assertTrue(updated.content)  # type: ignore[union-attr]

    def test_chat_service_refresh_runtime_release_error_and_provider_config_defaults(self) -> None:
        self.service.update_service.release_check = ReleaseCheck(current_version="0.2.0", error="offline")
        result = self.service.refresh_runtime_configuration()
        self.assertEqual(result.status.last_check_status, "error")
        self.assertEqual(result.error, "offline")

        class NoDescriptorCatalog:
            def get_model(self, model_id: str):
                _ = model_id
                return None

            def list_models(self):
                return []

            def to_provider_models(self):
                return []

            def get_recommended_model(self):
                return None

        self.service.catalog_service = NoDescriptorCatalog()
        self.assertEqual(self.service._provider_config(self.service.load_settings(), "local_llama")["context_length"], "8192")  # noqa: SLF001

    def test_chat_service_refresh_local_runtime_error_branches(self) -> None:
        self.service.storage.save_installed_model(
            InstalledLocalModel(
                model_id=DEFAULT_MODEL,
                file_path="C:/models/qwen.gguf",
                file_name="qwen.gguf",
                source="hf",
                downloaded_at="2026-03-16T00:00:00+00:00",
                size_bytes=123,
            )
        )

        self.service.runtime_service = FakeRuntimeService(binary_available=True, ensure_error="timed out")
        status, detail, active_model_id, runtime_ready, repair_required, _reason = self.service._refresh_local_runtime()  # noqa: SLF001
        self.assertEqual(status, "error")
        self.assertFalse(runtime_ready)
        self.assertTrue(repair_required)
        self.assertEqual(active_model_id, DEFAULT_MODEL)
        self.assertIn("timed out", detail)

        self.service.runtime_service = type(
            "Runtime",
            (),
            {
                "verify_runtime_bundle": lambda _self: type("Verification", (), {"status": "invalid_bundle", "detail": "broken bundle"})(),
                "ensure_runtime": lambda _self, _path, _ctx: None,
            },
        )()
        status, detail, *_rest = self.service._refresh_local_runtime()  # noqa: SLF001
        self.assertEqual(status, "error")
        self.assertEqual(detail, "broken bundle")


if __name__ == "__main__":
    unittest.main()
