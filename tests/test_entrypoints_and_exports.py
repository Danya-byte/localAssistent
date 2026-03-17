from __future__ import annotations

import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests._support import PROJECT_ROOT  # noqa: F401

import local_assistant
import local_assistant.__main__ as app_main
from local_assistant import app as app_module
from local_assistant.i18n import LocalizationManager
from local_assistant.services import ChatService, LocalRuntimeService, ModelCatalogService, ModelDownloadService, RuntimeRefreshResult, RuntimeStatus, UpdateService


class EntrypointAndExportTests(unittest.TestCase):
    def test_package_run_delegates_to_app(self) -> None:
        with patch("local_assistant.app.run") as run_mock:
            local_assistant.run()
        run_mock.assert_called_once()

    def test_main_module_delegates_to_app_run(self) -> None:
        with patch("local_assistant.__main__.run") as run_mock:
            app_main.main()
        run_mock.assert_called_once()

    def test_localization_manager_switches_language_and_falls_back_to_key(self) -> None:
        manager = LocalizationManager(language="en")
        self.assertEqual(manager.t("missing_key"), "missing_key")
        manager.set_language("ru")
        self.assertIsInstance(manager.t("app_title"), str)

    def test_services_exports_resolve_symbols(self) -> None:
        self.assertIsNotNone(ChatService)
        self.assertIsNotNone(LocalRuntimeService)
        self.assertIsNotNone(ModelCatalogService)
        self.assertIsNotNone(ModelDownloadService)
        self.assertIsNotNone(RuntimeRefreshResult)
        self.assertIsNotNone(RuntimeStatus)
        self.assertIsNotNone(UpdateService)
        with self.assertRaises(AttributeError):
            getattr(importlib.import_module("local_assistant.services"), "MissingSymbol")

    def test_app_run_bootstrap_mode_exits_with_bootstrap_code(self) -> None:
        with patch("local_assistant.app.run_recommended_model_bootstrap", return_value=7):
            with self.assertRaises(SystemExit) as exc:
                app_module.run(["--bootstrap-install-recommended-model"])
        self.assertEqual(exc.exception.code, 7)

    def test_run_recommended_model_bootstrap_builds_service_and_returns_code(self) -> None:
        fake_paths = Mock()
        fake_service = Mock()
        fake_result = Mock(exit_code=3)
        with (
            patch("local_assistant.app.AppPaths.resolve", return_value=fake_paths),
            patch("local_assistant.app.configure_logging"),
            patch("local_assistant.app.build_service_for_paths", return_value=(fake_service, Mock())),
            patch("local_assistant.app.bootstrap_recommended_model", return_value=fake_result),
        ):
            code = app_module.run_recommended_model_bootstrap()

        fake_paths.ensure.assert_called_once()
        fake_service.initialize.assert_called_once()
        self.assertEqual(code, 3)

    def test_app_run_raises_clear_error_without_pyside(self) -> None:
        import builtins

        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("PySide6"):
                raise ImportError("missing")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(SystemExit) as exc:
                app_module.run([])
        self.assertIn("PySide6 is not installed", str(exc.exception))

    def test_app_run_initializes_qt_window_and_respects_single_instance_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            icon_path = root / "app.ico"
            icon_path.write_text("icon", encoding="utf-8")
            fake_paths = Mock()
            fake_paths.root = root
            fake_lock = Mock()
            fake_lock.tryLock.return_value = True
            fake_app = Mock()
            fake_app.exec.return_value = 0
            fake_window = Mock()
            qtcore = types.ModuleType("PySide6.QtCore")
            qtcore.QLockFile = Mock(return_value=fake_lock)
            qtgui = types.ModuleType("PySide6.QtGui")
            qtgui.QIcon = Mock(side_effect=lambda path: f"ICON:{path}")
            qtwidgets = types.ModuleType("PySide6.QtWidgets")
            qtwidgets.QApplication = Mock(return_value=fake_app)
            ui_module = types.ModuleType("local_assistant.ui")
            ui_module.MainWindow = Mock(return_value=fake_window)

            with patch.dict(
                sys.modules,
                {
                    "PySide6": types.ModuleType("PySide6"),
                    "PySide6.QtCore": qtcore,
                    "PySide6.QtGui": qtgui,
                    "PySide6.QtWidgets": qtwidgets,
                    "local_assistant.ui": ui_module,
                },
            ):
                with (
                    patch("local_assistant.app.AppPaths.resolve", return_value=fake_paths),
                    patch("local_assistant.app.configure_logging"),
                    patch("local_assistant.app.resolve_asset", return_value=icon_path),
                    patch("local_assistant.app.build_service_for_paths", return_value=(Mock(), Mock())),
                    patch("local_assistant.app.sys.platform", "linux"),
                ):
                    with self.assertRaises(SystemExit) as exc:
                        app_module.run([])

            self.assertEqual(exc.exception.code, 0)
            fake_paths.ensure.assert_called_once()
            fake_lock.setStaleLockTime.assert_called_once_with(0)
            fake_app.setApplicationName.assert_called_once()
            fake_window.show.assert_called_once()

    def test_app_run_exits_when_another_instance_is_running(self) -> None:
        fake_paths = Mock()
        fake_paths.root = Path("C:/temp")
        fake_lock = Mock()
        fake_lock.tryLock.return_value = False
        qtcore = types.ModuleType("PySide6.QtCore")
        qtcore.QLockFile = Mock(return_value=fake_lock)
        qtgui = types.ModuleType("PySide6.QtGui")
        qtgui.QIcon = Mock()
        qtwidgets = types.ModuleType("PySide6.QtWidgets")
        qtwidgets.QApplication = Mock(return_value=Mock())

        with patch.dict(
            sys.modules,
            {
                "PySide6": types.ModuleType("PySide6"),
                "PySide6.QtCore": qtcore,
                "PySide6.QtGui": qtgui,
                "PySide6.QtWidgets": qtwidgets,
            },
        ):
            with (
                patch("local_assistant.app.AppPaths.resolve", return_value=fake_paths),
                patch("local_assistant.app.configure_logging"),
                patch("local_assistant.app.resolve_asset", return_value=Path("missing.ico")),
                patch("local_assistant.app.sys.platform", "linux"),
            ):
                with self.assertRaises(SystemExit) as exc:
                    app_module.run([])
        self.assertEqual(exc.exception.code, 0)
