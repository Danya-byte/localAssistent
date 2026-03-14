from __future__ import annotations

from ..exceptions import ProviderError
from ..models import ProviderDescriptor
from .base import ModelProvider
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {
            "ollama": OllamaProvider(),
            "openai_compatible": OpenAICompatibleProvider(),
        }

    def list_descriptors(self) -> list[ProviderDescriptor]:
        return [provider.descriptor for provider in self._providers.values()]

    def get(self, provider_id: str) -> ModelProvider:
        if provider_id not in self._providers:
            raise ProviderError(f"Unknown provider: {provider_id}")
        return self._providers[provider_id]
