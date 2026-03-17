from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant import bootstrap as bootstrap_module
from local_assistant.bootstrap import BootstrapResult, bootstrap_recommended_model


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_recommended_model_returns_success(self) -> None:
        class FakeService:
            def install_recommended_local_model(self, cancel_event, progress_callback):
                progress_callback(type("Progress", (), {"stage": "completed", "downloaded_bytes": 1, "total_bytes": 1, "message": "done"})())
                _ = cancel_event
                return type("Installed", (), {"model_id": "recommended-model"})()

        result = bootstrap_recommended_model(FakeService())

        self.assertEqual(result.status, "success")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.message, "recommended-model")

    def test_bootstrap_recommended_model_returns_failure(self) -> None:
        class FakeService:
            def install_recommended_local_model(self, cancel_event, progress_callback):
                _ = cancel_event
                _ = progress_callback
                raise RuntimeError("download failed")

        result = bootstrap_recommended_model(FakeService())

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("download failed", result.message)

    def test_bootstrap_recommended_model_returns_skipped(self) -> None:
        class FakeService:
            def install_recommended_local_model(self, cancel_event, progress_callback):
                _ = cancel_event
                _ = progress_callback
                raise RuntimeError("No recommended local model is available in the bundled catalog.")

        result = bootstrap_recommended_model(FakeService())

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.exit_code, 10)

    def test_build_service_for_paths_constructs_runtime_stack(self) -> None:
        fake_paths = Mock()
        fake_paths.db_path = "db.sqlite3"
        fake_paths.models_dir = "models"
        fake_paths.cache_dir = "cache"
        storage = Mock()
        catalog_service = Mock()
        runtime_service = Mock()
        download_service = Mock()
        providers = Mock()
        update_service = Mock()
        chat_service = Mock()
        action_executor = Mock()

        with (
            patch("local_assistant.storage.Storage", return_value=storage),
            patch("local_assistant.services.ModelCatalogService", return_value=catalog_service),
            patch("local_assistant.services.LocalRuntimeService", return_value=runtime_service),
            patch("local_assistant.services.ModelDownloadService", return_value=download_service),
            patch("local_assistant.providers.ProviderRegistry", return_value=providers),
            patch("local_assistant.services.UpdateService", return_value=update_service),
            patch("local_assistant.services.ChatService", return_value=chat_service),
            patch("local_assistant.actions.executor.ActionExecutor", return_value=action_executor),
        ):
            service, executor = bootstrap_module.build_service_for_paths(fake_paths)

        self.assertIs(service, chat_service)
        self.assertIs(executor, action_executor)

    def test_bootstrap_result_unknown_status_uses_failure_exit_code(self) -> None:
        self.assertEqual(BootstrapResult(status="mystery").exit_code, 1)


if __name__ == "__main__":
    unittest.main()
