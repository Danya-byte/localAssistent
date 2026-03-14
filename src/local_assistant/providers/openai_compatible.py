from __future__ import annotations

import json
from threading import Event
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import ProviderError
from ..models import GenerationRequest, ModelDescriptor, ProviderDescriptor, ProviderField, ProviderHealth
from .base import ModelProvider


class OpenAICompatibleProvider(ModelProvider):
    descriptor = ProviderDescriptor(
        provider_id="openai_compatible",
        display_name="OpenAI-compatible",
        description_key="provider_openai_desc",
        config_fields=[
            ProviderField(name="base_url", label_key="provider_base_url", placeholder_key="provider_base_url_placeholder"),
            ProviderField(name="api_key", label_key="provider_api_key", placeholder_key="provider_api_key_placeholder", secret=True),
        ],
    )

    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        base_url = provider_config.get("base_url", "").strip()
        if not base_url:
            return ProviderHealth(status="missing_configuration", detail="Base URL is required for the OpenAI-compatible provider.")

        try:
            models = self.list_models(provider_config)
        except ProviderError as exc:
            return ProviderHealth(status="error", detail=str(exc))

        if desired_model and desired_model not in {model.model_id for model in models}:
            return ProviderHealth(status="missing_model", detail="Selected model is unavailable on the endpoint.", models=models)

        return ProviderHealth(status="ready", detail="Provider endpoint is reachable.", models=models)

    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        payload = self._request_json("GET", "/models", provider_config)
        items = payload.get("data", [])
        models = [
            ModelDescriptor(model_id=item.get("id", ""), display_name=item.get("id", ""))
            for item in items
            if item.get("id")
        ]
        return sorted(models, key=lambda model: model.model_id)

    def stream_chat(self, request: GenerationRequest, cancel_event: Event) -> Iterator[str]:
        body = {
            "model": request.model,
            "stream": True,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        response = self._open_stream("POST", "/chat/completions", request.provider_config, body)
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
                event = self._parse_json(payload)
                choices = event.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content

    def _request_json(self, method: str, path: str, provider_config: dict[str, str]) -> dict[str, Any]:
        with self._open_stream(method, path, provider_config) as response:
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
        base_url = provider_config.get("base_url", "").rstrip("/")
        if not base_url:
            raise ProviderError("Base URL is not configured.")
        url = f"{base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url=url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        api_key = provider_config.get("api_key", "").strip()
        if api_key:
            request.add_header("Authorization", f"Bearer {api_key}")
        try:
            return urlopen(request, timeout=300)
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"OpenAI-compatible request failed with HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            raise ProviderError(f"Endpoint connection failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderError("Provider request timed out.") from exc

    @staticmethod
    def _parse_json(payload: str) -> dict[str, Any]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Invalid SSE payload: {payload!r}") from exc
