from __future__ import annotations

import contextlib
import os
from pathlib import Path
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import APP_VERSION
from ..models import InstalledLocalModel, LocalModelDescriptor, ModelDownloadProgress
from ..storage import utcnow


class ModelDownloadService:
    CHUNK_SIZE = 1024 * 256

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir

    def download(
        self,
        descriptor: LocalModelDescriptor,
        cancel_event: Event,
        progress_callback,
    ) -> InstalledLocalModel:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        target_dir = self.models_dir / descriptor.model_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / descriptor.file_name
        partial_path = target_path.with_suffix(target_path.suffix + ".part")

        existing_bytes = partial_path.stat().st_size if partial_path.exists() else 0
        request = Request(descriptor.download_url, headers={"User-Agent": f"LocalAssistant/{APP_VERSION}"})
        if existing_bytes > 0:
            request.add_header("Range", f"bytes={existing_bytes}-")
        try:
            response = urlopen(request, timeout=60)  # noqa: S310
        except HTTPError as exc:
            if exc.code == 401:
                raise RuntimeError("The selected model file is unavailable from the current source.") from exc
            if exc.code == 404:
                raise RuntimeError("The selected model file was not found at the download source.") from exc
            raise RuntimeError(f"Model download failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise RuntimeError(f"Model download connection failed: {exc.reason}") from exc

        with contextlib.closing(response) as response:
            total_bytes = self._resolve_total_bytes(response, existing_bytes)
            mode = "ab" if existing_bytes > 0 else "wb"
            downloaded = existing_bytes
            progress_callback(
                ModelDownloadProgress(
                    model_id=descriptor.model_id,
                    display_name=descriptor.display_name,
                    stage="downloading",
                    downloaded_bytes=downloaded,
                    total_bytes=total_bytes,
                    message="Downloading model files...",
                )
            )
            with partial_path.open(mode) as handle:
                while True:
                    if cancel_event.is_set():
                        raise RuntimeError("Download cancelled.")
                    chunk = response.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    progress_callback(
                        ModelDownloadProgress(
                            model_id=descriptor.model_id,
                            display_name=descriptor.display_name,
                            stage="downloading",
                            downloaded_bytes=downloaded,
                            total_bytes=total_bytes,
                            message="Downloading model files...",
                        )
                    )

        progress_callback(
            ModelDownloadProgress(
                model_id=descriptor.model_id,
                display_name=descriptor.display_name,
                stage="verifying",
                downloaded_bytes=downloaded,
                total_bytes=downloaded,
                message="Verifying local model...",
            )
        )
        if target_path.exists():
            target_path.unlink()
        partial_path.replace(target_path)
        size_bytes = target_path.stat().st_size if target_path.exists() else 0
        progress_callback(
            ModelDownloadProgress(
                model_id=descriptor.model_id,
                display_name=descriptor.display_name,
                stage="completed",
                downloaded_bytes=size_bytes,
                total_bytes=size_bytes,
                message="Model is ready.",
            )
        )
        return InstalledLocalModel(
            model_id=descriptor.model_id,
            file_path=str(target_path),
            file_name=descriptor.file_name,
            source=descriptor.source,
            downloaded_at=utcnow(),
            size_bytes=size_bytes,
        )

    @staticmethod
    def _resolve_total_bytes(response, existing_bytes: int) -> int:
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            try:
                return int(content_range.rsplit("/", maxsplit=1)[-1])
            except ValueError:
                pass
        content_length = response.headers.get("Content-Length", "")
        try:
            return existing_bytes + int(content_length)
        except ValueError:
            return 0

    def remove(self, installed_model: InstalledLocalModel | None) -> None:
        if installed_model is None:
            return
        model_path = Path(installed_model.file_path)
        if model_path.exists():
            model_path.unlink()
        with contextlib.suppress(OSError):
            parent = model_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()

    def discover_existing(self, descriptor: LocalModelDescriptor) -> InstalledLocalModel | None:
        target_path = self.models_dir / descriptor.model_id / descriptor.file_name
        if not target_path.exists() or not target_path.is_file():
            return None
        size_bytes = target_path.stat().st_size
        return InstalledLocalModel(
            model_id=descriptor.model_id,
            file_path=str(target_path),
            file_name=descriptor.file_name,
            source=descriptor.source,
            downloaded_at=utcnow(),
            size_bytes=size_bytes,
        )
