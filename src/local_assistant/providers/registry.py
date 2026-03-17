from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import ProviderError
from ..models import ProviderDescriptor
from .base import ModelProvider
from .llama_cpp_local import LocalLlamaProvider

if TYPE_CHECKING:
    from ..services.local_runtime_service import LocalRuntimeService
    from ..services.model_catalog_service import ModelCatalogService
    from ..storage import Storage


class ProviderRegistry:
    def __init__(self, runtime_service: LocalRuntimeService, storage: Storage, catalog_service: ModelCatalogService) -> None:
        self._providers: dict[str, ModelProvider] = {
            "local_llama": LocalLlamaProvider(runtime_service=runtime_service, storage=storage, catalog_service=catalog_service),
        }

    def list_descriptors(self) -> list[ProviderDescriptor]:
        return [provider.descriptor for provider in self._providers.values()]

    def get(self, provider_id: str) -> ModelProvider:
        if provider_id not in self._providers:
            raise ProviderError(f"Unknown provider: {provider_id}")
        return self._providers[provider_id]
