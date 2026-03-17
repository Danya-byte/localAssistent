from __future__ import annotations

import json
from threading import Event
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import ProviderError
from ..models import GenerationRequest, ModelDescriptor, ProviderDescriptor, ProviderHealth
from ..services.local_runtime_service import LocalRuntimeService
from ..storage import Storage
from .base import ModelProvider


class LocalLlamaProvider(ModelProvider):
    descriptor = ProviderDescriptor(
        provider_id="local_llama",
        display_name="Local Qwen",
        description_key="provider_local_desc",
    )

    def __init__(self, runtime_service: LocalRuntimeService, storage: Storage, catalog_service) -> None:
        self.runtime_service = runtime_service
        self.storage = storage
        self.catalog_service = catalog_service

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        _ = provider_config
        verification = self.runtime_service.verify_runtime_bundle()
        if verification.status != "ready":
            return ProviderHealth(status="missing_runtime", detail=verification.detail or "Local runtime binary is missing.")
        installed = self.storage.get_installed_model(desired_model)
        if installed is None:
            return ProviderHealth(status="missing_model", detail="Selected local model is not installed.", models=self.list_models({}))
        return ProviderHealth(status="ready", detail="Local runtime is ready.", models=self.list_models({}))

    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        _ = provider_config
        installed_ids = {item.model_id for item in self.storage.list_installed_models()}
        models: list[ModelDescriptor] = []
        for item in self.catalog_service.to_provider_models():
            description = item.description
            if item.model_id in installed_ids:
                description = f"{description} Installed locally."
            models.append(
                ModelDescriptor(
                    model_id=item.model_id,
                    display_name=item.display_name,
                    description=description,
                    source=item.source,
                    source_url=item.source_url,
                    recommended=item.recommended,
                )
            )
        return models

    def stream_chat(self, request: GenerationRequest, cancel_event: Event) -> Iterator[str]:
        installed = self.storage.get_installed_model(request.model)
        if installed is None:
            raise ProviderError("Selected local model is not installed.")
        self.runtime_service.ensure_runtime(installed.file_path, int(request.provider_config.get("context_length", "8192") or 8192))
        body = {
            "model": request.model,
            "stream": True,
            "messages": [self._serialize_message(message) for message in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        url = f"{self.runtime_service.base_url}/chat/completions"
        request_obj = Request(url=url, data=json.dumps(body).encode("utf-8"), method="POST")
        request_obj.add_header("Content-Type", "application/json")
        try:
            response = urlopen(request_obj, timeout=600)
        except HTTPError as exc:
            raise ProviderError(f"Local runtime request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise ProviderError(f"Local runtime connection failed: {exc.reason}") from exc

        with response:
            for raw_line in response:
                if cancel_event.is_set():
                    return
                decoded = raw_line.decode("utf-8").strip()
                if not decoded or not decoded.startswith("data:"):
                    continue
                payload = decoded.removeprefix("data:").strip()
                if payload == "[DONE]":
                    return
                event = json.loads(payload)
                choices = event.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                chunk = delta.get("content", "")
                if chunk:
                    yield chunk

    @staticmethod
    def _serialize_message(message) -> dict[str, Any]:
        return {"role": message.role, "content": message.content}
