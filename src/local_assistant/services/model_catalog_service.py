from __future__ import annotations

import json
from pathlib import Path

from ..config import bundled_model_catalog_path
from ..models import LocalModelDescriptor, ModelDescriptor


class ModelCatalogService:
    def __init__(self, catalog_path: Path | None = None) -> None:
        self.catalog_path = catalog_path or bundled_model_catalog_path()

    def list_models(self) -> list[LocalModelDescriptor]:
        if not self.catalog_path.exists():
            return []
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        items = payload.get("models", [])
        models: list[LocalModelDescriptor] = []
        for item in items:
            models.append(
                LocalModelDescriptor(
                    model_id=str(item.get("model_id", "")).strip(),
                    display_name=str(item.get("display_name", "")).strip(),
                    description=str(item.get("description", "")).strip(),
                    source=str(item.get("source", "")).strip(),
                    download_url=str(item.get("download_url", "")).strip(),
                    file_name=str(item.get("file_name", "")).strip(),
                    size_hint=str(item.get("size_hint", "")).strip(),
                    quantization=str(item.get("quantization", "")).strip(),
                    recommended_ram_gb=int(item.get("recommended_ram_gb", 0) or 0),
                    context_length=int(item.get("context_length", 8192) or 8192),
                    recommended=bool(item.get("recommended", False)),
                )
            )
        return [model for model in models if model.model_id and model.download_url and model.file_name]

    def get_model(self, model_id: str) -> LocalModelDescriptor | None:
        for item in self.list_models():
            if item.model_id == model_id:
                return item
        return None

    def get_recommended_model(self) -> LocalModelDescriptor | None:
        for item in self.list_models():
            if item.recommended:
                return item
        return None

    def get_recommended_model_id(self) -> str:
        recommended = self.get_recommended_model()
        return recommended.model_id if recommended is not None else ""

    def to_provider_models(self) -> list[ModelDescriptor]:
        return [
            ModelDescriptor(
                model_id=item.model_id,
                display_name=item.display_name,
                description=item.description,
                source=item.source,
                source_url=item.download_url,
                recommended=item.recommended,
            )
            for item in self.list_models()
        ]
