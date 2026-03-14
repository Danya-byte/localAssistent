from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from threading import Event

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.models import (
    AppSettings,
    GenerationRequest,
    ModelDescriptor,
    ProviderDescriptor,
    ProviderHealth,
)
from local_assistant.services import ChatService
from local_assistant.storage import Storage


class FakeProvider:
    descriptor = ProviderDescriptor(
        provider_id="ollama",
        display_name="Fake Local",
        description_key="provider_ollama_desc",
    )

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        return ProviderHealth(
            status="ready",
            detail="ready",
            models=[ModelDescriptor(model_id=desired_model, display_name=desired_model)],
        )

    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        return [ModelDescriptor(model_id="demo-model", display_name="demo-model")]

    def stream_chat(self, request: GenerationRequest, cancel_event: Event):
        yield "chunk-1"
        yield "chunk-2"


class FakeRegistry:
    def __init__(self) -> None:
        self.provider = FakeProvider()

    def list_descriptors(self) -> list[ProviderDescriptor]:
        return [self.provider.descriptor]

    def get(self, provider_id: str) -> FakeProvider:
        if provider_id != "ollama":
            raise KeyError(provider_id)
        return self.provider


class ChatServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "app.sqlite3"
        storage = Storage(db_path)
        self.service = ChatService(storage=storage, providers=FakeRegistry())
        self.service.initialize()
        self.service.save_settings(
            AppSettings(
                provider_id="ollama",
                model="demo-model",
                system_prompt="Be precise.",
                provider_configs={"ollama": {"base_url": "http://127.0.0.1:11434"}},
                command_allowlist=["echo"],
            )
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_prepare_user_generation_uses_provider_and_model(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Explain WAL mode.")

        self.assertEqual(prepared.assistant_message.status, "streaming")
        self.assertEqual(prepared.request.provider_id, "ollama")
        self.assertEqual(prepared.request.model, "demo-model")
        self.assertEqual(prepared.request.messages[-1].content, "Explain WAL mode.")

    def test_parse_action_request_strips_machine_block_and_creates_action(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Open the docs")
        payload = """
Need approval first.
<ACTION_REQUEST>
{"kind":"web_fetch","title":"Fetch docs","description":"Need the page content","target":"https://example.com","risk":"low","payload":{"url":"https://example.com"}}
</ACTION_REQUEST>
        """.strip()
        self.service.append_to_message(prepared.assistant_message.message_id, payload)
        self.service.finalize_message(prepared.assistant_message.message_id)

        action = self.service.parse_action_request(prepared.assistant_message.message_id)

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.kind, "web_fetch")
        message = self.service.load_messages(prepared.conversation.conversation_id)[-1]
        self.assertNotIn("<ACTION_REQUEST>", message.content)
        self.assertIn("Need approval first.", message.content)

    def test_build_action_follow_up_adds_system_result_message(self) -> None:
        prepared = self.service.prepare_user_generation(None, "Read the file")
        action = self.service.storage.create_action(
            conversation_id=prepared.conversation.conversation_id,
            assistant_message_id=prepared.assistant_message.message_id,
            kind="file_read",
            title="Read file",
            description="Read config",
            target="C:/demo.txt",
            risk="medium",
            payload={"path": "C:/demo.txt"},
        )
        executed = self.service.mark_action_executed(action.action_id or "", "demo content")

        follow_up = self.service.build_action_follow_up(executed)

        self.assertEqual(follow_up.conversation.conversation_id, prepared.conversation.conversation_id)
        self.assertEqual(follow_up.request.messages[-1].role, "system")
        system_messages = [item for item in follow_up.request.messages if item.role == "system"]
        self.assertTrue(any("ACTION_RESULT" in item.content for item in system_messages))


if __name__ == "__main__":
    unittest.main()
