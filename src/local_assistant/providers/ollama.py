from __future__ import annotations

import json
import logging
from threading import Event
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import DEFAULT_OLLAMA_BASE_URL
from ..exceptions import ProviderError
from ..models import GenerationRequest, ModelDescriptor, ProviderDescriptor, ProviderField, ProviderHealth
from .base import ModelProvider


LOGGER = logging.getLogger(__name__)


class OllamaProvider(ModelProvider):
    descriptor = ProviderDescriptor(
        provider_id="ollama",
        display_name="Ollama",
        description_key="provider_ollama_desc",
        config_fields=[
            ProviderField(name="base_url", label_key="provider_base_url", placeholder_key="provider_base_url_placeholder"),
        ],
    )

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        try:
            models = self.list_models(provider_config)
        except ProviderError as exc:
            detail = str(exc)
            if "connection" in detail.lower() or "refused" in detail.lower():
                return ProviderHealth(status="missing_runtime", detail=detail)
            return ProviderHealth(status="error", detail=detail)

        available_ids = {model.model_id for model in models}
        if desired_model and desired_model not in available_ids:
            return ProviderHealth(status="missing_model", detail="Selected model is not installed in Ollama.", models=models)

        return ProviderHealth(status="ready", detail="Ollama is ready.", models=models)

    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        payload = self._request_json("GET", "/api/tags", provider_config)
        models = payload.get("models", [])
        descriptors = []
        for item in models:
            model_id = item.get("model") or item.get("name")
            if not model_id:
                continue
            descriptors.append(ModelDescriptor(model_id=model_id, display_name=model_id))
        return sorted(descriptors, key=lambda model: model.model_id)

    def stream_chat(self, request: GenerationRequest, cancel_event: Event) -> Iterator[str]:
        body = {
            "model": request.model,
            "stream": True,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens,
            },
        }
        response = self._open_stream("POST", "/api/chat", request.provider_config, body)
        with response:
            for raw_line in response:
                if cancel_event.is_set():
                    LOGGER.info("Generation cancelled for conversation %s", request.conversation_id)
                    return
                if not raw_line.strip():
                    continue
                event = self._parse_json_line(raw_line)
                message = event.get("message", {})
                chunk = message.get("content", "")
                if chunk:
                    yield chunk
                if event.get("error"):
                    raise ProviderError(str(event["error"]))
                if event.get("done"):
                    return

    def _request_json(
        self,
        method: str,
        path: str,
        provider_config: dict[str, str],
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._open_stream(method, path, provider_config, body) as response:
            raw = response.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)

    def _open_stream(
        self,
        method: str,
        path: str,
        provider_config: dict[str, str],
        body: dict[str, Any] | None = None,
    ):
        base_url = provider_config.get("base_url", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        url = f"{base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url=url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        try:
            return urlopen(request, timeout=300)
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Ollama request failed with HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            raise ProviderError(f"Ollama connection failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderError("Ollama request timed out.") from exc

    @staticmethod
    def _parse_json_line(raw_line: bytes) -> dict[str, Any]:
        try:
            return json.loads(raw_line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Invalid streaming payload: {raw_line!r}") from exc
