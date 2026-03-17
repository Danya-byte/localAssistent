from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Event
from typing import Iterator

from ..models import (
    GenerationRequest,
    ModelDescriptor,
    ProviderDescriptor,
    ProviderHealth,
)


class ModelProvider(ABC):
    descriptor: ProviderDescriptor

    @abstractmethod
    def health_check(self, provider_config: dict[str, str], desired_model: str) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    def list_models(self, provider_config: dict[str, str]) -> list[ModelDescriptor]:
        raise NotImplementedError

    @abstractmethod
    def stream_chat(self, request: GenerationRequest, cancel_event: Event) -> Iterator[str]:
        raise NotImplementedError

    def pop_response_metadata(self, assistant_message_id: str) -> dict[str, object]:
        _ = assistant_message_id
        return {}
