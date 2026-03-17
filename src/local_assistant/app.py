from __future__ import annotations

import logging
import sys

from .config import AppPaths, resolve_asset
from .logging_utils import configure_logging
from .bootstrap import bootstrap_recommended_model, build_service_for_paths


def run(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--bootstrap-install-recommended-model" in args:
        raise SystemExit(run_recommended_model_bootstrap())

    try:
        from PySide6.QtCore import QLockFile
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise SystemExit("PySide6 is not installed. Run `pip install -e .` first.") from exc

    paths = AppPaths.resolve()
    paths.ensure()
    configure_logging(paths.logs_dir)
    logging.getLogger(__name__).info("Starting application")

    app = QApplication(sys.argv)
    app.setApplicationName("Local Assistant")
    app.setOrganizationName("LocalAssistant")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LocalAssistant.Desktop")
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Failed to set AppUserModelID")
    lock_file = QLockFile(str(paths.root / "app.lock"))
    lock_file.setStaleLockTime(0)
    if not lock_file.tryLock(0):
        logging.getLogger(__name__).info("Another application instance is already running")
        raise SystemExit(0)
    app._instance_lock = lock_file  # type: ignore[attr-defined]
    icon_path = resolve_asset("assets", "branding", "app.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from .ui import MainWindow

    service, executor = build_service_for_paths(paths)
    window = MainWindow(service=service, executor=executor, paths=paths)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec())


def run_recommended_model_bootstrap() -> int:
    paths = AppPaths.resolve()
    paths.ensure()
    configure_logging(paths.logs_dir)
    logging.getLogger(__name__).info("Starting recommended model bootstrap")
    service, _executor = build_service_for_paths(paths)
    service.initialize()
    return bootstrap_recommended_model(service).exit_code
