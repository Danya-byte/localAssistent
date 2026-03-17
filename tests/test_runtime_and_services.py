from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.config import AppPaths
from local_assistant.logging_utils import configure_logging
from local_assistant.models import ChatMessage, GenerationRequest, InstalledLocalModel, LocalModelDescriptor
from local_assistant.providers.llama_cpp_local import LocalLlamaProvider
from local_assistant.providers.registry import ProviderRegistry
from local_assistant.services.local_runtime_service import LocalRuntimeService, RuntimeVerification
from local_assistant.services.model_catalog_service import ModelCatalogService
from local_assistant.services.model_download_service import ModelDownloadService
from local_assistant.storage import Storage


class RuntimeAndServiceTests(unittest.TestCase):
    @staticmethod
    def _paths(root: Path) -> AppPaths:
        return AppPaths(
            root=root,
            data_dir=root / "data",
            logs_dir=root / "logs",
            exports_dir=root / "exports",
            models_dir=root / "models",
            runtime_dir=root / "runtime-cache",
            cache_dir=root / "cache",
            db_path=root / "data" / "app.sqlite3",
            secrets_path=root / "data" / "secrets.json",
        )

    @staticmethod
    def _descriptor(**overrides) -> LocalModelDescriptor:
        data = {
            "model_id": "demo",
            "display_name": "Demo",
            "description": "Demo model",
            "source": "hf",
            "download_url": "https://example.com/demo.gguf",
            "file_name": "demo.gguf",
            "size_hint": "1 MB",
            "quantization": "Q4",
            "recommended_ram_gb": 8,
            "context_length": 4096,
            "recommended": False,
        }
        data.update(overrides)
        return LocalModelDescriptor(**data)

    def test_configure_logging_adds_handlers_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root_logger = logging.getLogger()
            previous_handlers = list(root_logger.handlers)
            previous_level = root_logger.level
            for handler in list(root_logger.handlers):
                root_logger.removeHandler(handler)
            try:
                configure_logging(Path(temp_dir))
                self.assertEqual(len(root_logger.handlers), 2)
                configure_logging(Path(temp_dir))
                self.assertEqual(len(root_logger.handlers), 2)
            finally:
                for handler in list(root_logger.handlers):
                    root_logger.removeHandler(handler)
                    handler.close()
                for handler in previous_handlers:
                    root_logger.addHandler(handler)
                root_logger.setLevel(previous_level)

    def test_model_catalog_service_filters_invalid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path = Path(temp_dir) / "catalog.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "valid",
                                "display_name": "Valid",
                                "description": "ok",
                                "source": "hf",
                                "download_url": "https://example.com/model.gguf",
                                "file_name": "model.gguf",
                            },
                            {
                                "model_id": "broken",
                                "display_name": "Broken",
                                "download_url": "",
                                "file_name": "broken.gguf",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            service = ModelCatalogService(catalog_path=catalog_path)

            models = service.list_models()

            self.assertEqual([item.model_id for item in models], ["valid"])
            self.assertEqual(service.get_model("valid").display_name, "Valid")  # type: ignore[union-attr]
            self.assertIsNone(service.get_model("missing"))
            self.assertEqual(service.to_provider_models()[0].model_id, "valid")

    def test_bundled_catalog_recommended_model_is_compact_smart_default(self) -> None:
        service = ModelCatalogService()

        models = service.list_models()

        self.assertGreaterEqual(len(models), 3)
        recommended = next(item for item in models if item.recommended)
        self.assertEqual(recommended.model_id, "qwen2.5-1.5b-instruct-q4-k-m")
        self.assertEqual(service.get_recommended_model_id(), "qwen2.5-1.5b-instruct-q4-k-m")
        self.assertEqual(recommended.display_name, "Recommended Smart")
        self.assertEqual(recommended.size_hint, "940 MB")

    def test_model_download_service_remove_cleans_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            service = ModelDownloadService(models_dir)
            target_dir = models_dir / "demo"
            target_dir.mkdir(parents=True)
            target_path = target_dir / "demo.gguf"
            target_path.write_text("data", encoding="utf-8")

            service.remove(
                InstalledLocalModel(
                    model_id="demo",
                    file_path=str(target_path),
                    file_name="demo.gguf",
                    source="hf",
                    downloaded_at="2026-03-17T00:00:00+00:00",
                    size_bytes=4,
                )
            )

            self.assertFalse(target_path.exists())
            self.assertFalse(target_dir.exists())
            service.remove(None)

    def test_model_download_service_total_bytes_resolution(self) -> None:
        response = type("Response", (), {"headers": {"Content-Range": "bytes 10-19/100", "Content-Length": "10"}})()
        self.assertEqual(ModelDownloadService._resolve_total_bytes(response, 10), 100)
        response = type("Response", (), {"headers": {"Content-Length": "10"}})()
        self.assertEqual(ModelDownloadService._resolve_total_bytes(response, 5), 15)
        response = type("Response", (), {"headers": {"Content-Length": "oops"}})()
        self.assertEqual(ModelDownloadService._resolve_total_bytes(response, 5), 0)

    def test_model_download_service_downloads_resumes_and_discovers_existing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            service = ModelDownloadService(models_dir)
            descriptor = self._descriptor()
            target_dir = models_dir / descriptor.model_id
            target_dir.mkdir(parents=True)
            partial_path = target_dir / f"{descriptor.file_name}.part"
            partial_path.write_bytes(b"abc")
            progress: list[tuple[str, int, int]] = []

            class FakeResponse:
                headers = {"Content-Length": "3"}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self, _size=None):
                    if hasattr(self, "_done"):
                        return b""
                    self._done = True
                    return b"def"

                def close(self):
                    return None

            with patch("local_assistant.services.model_download_service.urlopen", return_value=FakeResponse()) as urlopen_mock:
                installed = service.download(
                    descriptor,
                    Event(),
                    lambda item: progress.append((item.stage, item.downloaded_bytes, item.total_bytes)),
                )

            request = urlopen_mock.call_args.args[0]
            self.assertEqual(request.headers["Range"], "bytes=3-")
            self.assertEqual(installed.size_bytes, 6)
            self.assertEqual((target_dir / descriptor.file_name).read_bytes(), b"abcdef")
            self.assertEqual(progress[0][0], "downloading")
            self.assertEqual(progress[-1][0], "completed")

            discovered = service.discover_existing(descriptor)
            self.assertIsNotNone(discovered)
            self.assertEqual(discovered.size_bytes, 6)  # type: ignore[union-attr]
            self.assertIsNone(service.discover_existing(self._descriptor(model_id="missing")))

    def test_model_download_service_reports_http_url_and_cancel_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ModelDownloadService(Path(temp_dir))
            descriptor = self._descriptor()

            with patch(
                "local_assistant.services.model_download_service.urlopen",
                side_effect=HTTPError(descriptor.download_url, 401, "denied", hdrs=None, fp=None),
            ):
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    service.download(descriptor, Event(), lambda _item: None)

            with patch(
                "local_assistant.services.model_download_service.urlopen",
                side_effect=HTTPError(descriptor.download_url, 404, "missing", hdrs=None, fp=None),
            ):
                with self.assertRaisesRegex(RuntimeError, "not found"):
                    service.download(descriptor, Event(), lambda _item: None)

            with patch(
                "local_assistant.services.model_download_service.urlopen",
                side_effect=HTTPError(descriptor.download_url, 500, "boom", hdrs=None, fp=None),
            ):
                with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
                    service.download(descriptor, Event(), lambda _item: None)

            with patch(
                "local_assistant.services.model_download_service.urlopen",
                side_effect=URLError("offline"),
            ):
                with self.assertRaisesRegex(RuntimeError, "connection failed"):
                    service.download(descriptor, Event(), lambda _item: None)

            class StreamingResponse:
                headers = {"Content-Length": "10"}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self, _size=None):
                    return b"x"

                def close(self):
                    return None

            cancel_event = Event()
            cancel_event.set()
            with patch("local_assistant.services.model_download_service.urlopen", return_value=StreamingResponse()):
                with self.assertRaisesRegex(RuntimeError, "cancelled"):
                    service.download(descriptor, cancel_event, lambda _item: None)

    def test_local_runtime_service_verifies_flat_runtime_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            paths.ensure()
            service = LocalRuntimeService(paths)
            runtime_dir = root / "runtime-cache"
            runtime_dir.mkdir(exist_ok=True)
            for name in ("llama-server.exe", "llama.dll", "ggml.dll", "ggml-base.dll", "ggml-cpu.dll"):
                (runtime_dir / name).write_text("x", encoding="utf-8")

            with (
                patch("local_assistant.services.local_runtime_service.application_root", return_value=root),
                patch("local_assistant.services.local_runtime_service.resolve_asset", side_effect=lambda *parts: root.joinpath(*parts)),
                patch("local_assistant.services.local_runtime_service.subprocess.run") as run_mock,
            ):
                run_mock.return_value = Mock(returncode=0)
                verification = service.verify_runtime_bundle()

            self.assertEqual(verification.status, "ready")
            self.assertEqual(verification.binary_path, runtime_dir / "llama-server.exe")

    def test_local_runtime_service_reports_invalid_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            paths.ensure()
            service = LocalRuntimeService(paths)
            runtime_dir = root / "runtime-cache"
            runtime_dir.mkdir(exist_ok=True)
            (runtime_dir / "llama-server.exe").write_text("x", encoding="utf-8")

            with (
                patch("local_assistant.services.local_runtime_service.application_root", return_value=root),
                patch("local_assistant.services.local_runtime_service.resolve_asset", side_effect=lambda *parts: root.joinpath(*parts)),
            ):
                verification = service.verify_runtime_bundle()

            self.assertEqual(verification.status, "invalid_bundle")

    def test_local_runtime_service_runtime_helpers_cover_ready_timeout_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            paths.ensure()
            service = LocalRuntimeService(paths)
            binary = root / "runtime-cache" / "llama-server.exe"
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_text("x", encoding="utf-8")

            with patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="missing_binary", detail="missing")):
                with self.assertRaisesRegex(Exception, "missing"):
                    service.ensure_runtime("C:/models/demo.gguf")

            process = Mock()
            process.poll.return_value = None
            service._process = process
            service._active_model_path = "C:/models/demo.gguf"
            with patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="ready", binary_path=binary)):
                with patch.object(service, "_is_ready", return_value=True):
                    service.ensure_runtime("C:/models/demo.gguf")
            process.terminate.assert_not_called()

            service._process = None
            popen_process = Mock()
            popen_process.poll.side_effect = [None, None, None]
            with (
                patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="ready", binary_path=binary)),
                patch.object(service, "_is_ready", side_effect=[False, True]),
                patch("local_assistant.services.local_runtime_service.subprocess.Popen", return_value=popen_process) as popen_mock,
                patch("local_assistant.services.local_runtime_service.time.sleep"),
            ):
                service.ensure_runtime("C:/models/other.gguf", context_length=1024)
            command = popen_mock.call_args.args[0]
            self.assertIn("--ctx-size", command)
            self.assertIn("2048", command)

            service._process = None
            failed_process = Mock()
            failed_process.poll.return_value = 2
            with (
                patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="ready", binary_path=binary)),
                patch.object(service, "_is_ready", return_value=False),
                patch("local_assistant.services.local_runtime_service.subprocess.Popen", return_value=failed_process),
                patch.object(service, "_runtime_start_failure_detail", return_value="bad model"),
                patch("local_assistant.services.local_runtime_service.time.sleep"),
            ):
                with self.assertRaisesRegex(Exception, "bad model"):
                    service.ensure_runtime("C:/models/fail.gguf")

            service._process = None
            hung_process = Mock()
            hung_process.poll.return_value = None
            with (
                patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="ready", binary_path=binary)),
                patch.object(service, "_is_ready", return_value=False),
                patch("local_assistant.services.local_runtime_service.subprocess.Popen", return_value=hung_process),
                patch("local_assistant.services.local_runtime_service.time.sleep"),
                patch("local_assistant.services.local_runtime_service.time.time", side_effect=[0.0, 26.0]),
            ):
                with self.assertRaisesRegex(Exception, "did not become ready"):
                    service.ensure_runtime("C:/models/timeout.gguf")

    def test_local_runtime_service_stop_port_ready_candidates_and_log_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            paths.ensure()
            service = LocalRuntimeService(paths)

            process = Mock()
            process.poll.return_value = None
            service._process = process
            service._active_model_path = "x"
            service.stop()
            process.terminate.assert_called_once()
            self.assertIsNone(service._process)
            self.assertIsNone(service._active_model_path)

            process = Mock()
            process.poll.return_value = None
            process.wait.side_effect = subprocess.TimeoutExpired(cmd="demo", timeout=5)
            service._process = process
            service.stop()
            process.kill.assert_called_once()

            fake_socket = Mock()
            fake_socket.connect_ex.return_value = 0
            with patch("local_assistant.services.local_runtime_service.socket.socket", return_value=fake_socket):
                self.assertTrue(service.is_port_in_use())

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps({"data": []}).encode("utf-8")

            with patch("local_assistant.services.local_runtime_service.urlopen", return_value=FakeResponse()):
                self.assertTrue(service._is_ready())  # noqa: SLF001
            with patch("local_assistant.services.local_runtime_service.urlopen", side_effect=URLError("offline")):
                self.assertFalse(service._is_ready())  # noqa: SLF001

            with (
                patch("local_assistant.services.local_runtime_service.application_root", return_value=root),
                patch("local_assistant.services.local_runtime_service.resolve_asset", side_effect=lambda *parts: root.joinpath(*parts)),
                patch("local_assistant.services.local_runtime_service.sys.frozen", False, create=True),
            ):
                candidates = service._candidate_runtime_paths()  # noqa: SLF001
            self.assertEqual(len(candidates), len(set(candidates)))
            with patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="missing_binary", detail="missing")):
                self.assertIsNone(service.runtime_binary_path())
            with patch.object(service, "verify_runtime_bundle", return_value=RuntimeVerification(status="ready", binary_path=Path("bin.exe"))):
                self.assertTrue(service.is_binary_available())
                self.assertEqual(service.runtime_binary_path(), Path("bin.exe"))

            log_path = root / "logs" / "llama-server.log"
            self.assertIn("exited", LocalRuntimeService._runtime_start_failure_detail(log_path))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("error loading model vocabulary: unknown pre-tokenizer type: 'deepseek-r1-qwen'\n", encoding="utf-8")
            self.assertIn("could not load", LocalRuntimeService._runtime_start_failure_detail(log_path))
            log_path.write_text("failed to load model\n", encoding="utf-8")
            self.assertIn("failed to load model", LocalRuntimeService._runtime_start_failure_detail(log_path))

    def test_local_llama_provider_stream_chat_yields_chunks_and_handles_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.sqlite3"
            storage = Storage(db_path)
            storage.initialize()
            storage.save_installed_model(
                InstalledLocalModel(
                    model_id="demo",
                    file_path="C:/models/demo.gguf",
                    file_name="demo.gguf",
                    source="hf",
                    downloaded_at="2026-03-17T00:00:00+00:00",
                    size_bytes=123,
                )
            )
            runtime_service = Mock()
            runtime_service.base_url = "http://127.0.0.1:8654/v1"
            runtime_service.verify_runtime_bundle.return_value = RuntimeVerification(status="ready", binary_path=Path("runtime/llama-server.exe"))
            catalog_service = Mock()
            catalog_service.to_provider_models.return_value = []
            provider = LocalLlamaProvider(runtime_service=runtime_service, storage=storage, catalog_service=catalog_service)

            request = GenerationRequest(
                conversation_id="c1",
                assistant_message_id="m1",
                provider_id="local_llama",
                provider_config={"context_length": "4096"},
                model="demo",
                messages=[ChatMessage(role="user", content="hi")],
                reasoning_enabled=False,
                temperature=0.7,
                top_p=0.9,
                max_tokens=64,
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def __iter__(self):
                    yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\n'
                    yield b'data: [DONE]\n'

            with patch("local_assistant.providers.llama_cpp_local.urlopen", return_value=FakeResponse()):
                chunks = list(provider.stream_chat(request, Event()))

            self.assertEqual(chunks, ["hello"])
            runtime_service.ensure_runtime.assert_called_once()

            with patch("local_assistant.providers.llama_cpp_local.urlopen", side_effect=URLError("offline")):
                with self.assertRaisesRegex(Exception, "connection failed"):
                    list(provider.stream_chat(request, Event()))

    def test_provider_registry_lists_and_rejects_unknown_provider(self) -> None:
        runtime_service = Mock()
        storage = Mock()
        catalog_service = Mock()
        registry = ProviderRegistry(runtime_service=runtime_service, storage=storage, catalog_service=catalog_service)

        self.assertEqual(registry.list_descriptors()[0].provider_id, "local_llama")
        self.assertEqual(registry.get("local_llama").descriptor.provider_id, "local_llama")
        with self.assertRaisesRegex(Exception, "Unknown provider"):
            registry.get("missing")

    def test_provider_health_and_list_models_cover_missing_and_installed_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.sqlite3"
            storage = Storage(db_path)
            storage.initialize()
            runtime_service = Mock()
            runtime_service.verify_runtime_bundle.return_value = RuntimeVerification(status="missing_binary", detail="missing")
            catalog_service = Mock()
            catalog_service.to_provider_models.return_value = []
            provider = LocalLlamaProvider(runtime_service=runtime_service, storage=storage, catalog_service=catalog_service)

            health = provider.health_check({}, "demo")
            self.assertEqual(health.status, "missing_runtime")

            runtime_service.verify_runtime_bundle.return_value = RuntimeVerification(status="ready", binary_path=Path("runtime/llama-server.exe"))
            health = provider.health_check({}, "demo")
            self.assertEqual(health.status, "missing_model")

            catalog_service.to_provider_models.return_value = [
                type("Descriptor", (), {"model_id": "demo", "display_name": "Demo", "description": "base", "source": "hf", "source_url": "https://example.com", "recommended": True})()
            ]
            storage.save_installed_model(
                InstalledLocalModel(
                    model_id="demo",
                    file_path="C:/models/demo.gguf",
                    file_name="demo.gguf",
                    source="hf",
                    downloaded_at="2026-03-17T00:00:00+00:00",
                    size_bytes=1,
                )
            )
            models = provider.list_models({})
            self.assertIn("Installed locally.", models[0].description)
