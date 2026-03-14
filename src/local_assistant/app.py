from __future__ import annotations

import logging
import sys

from .config import AppPaths
from .logging_utils import configure_logging
from .actions.executor import ActionExecutor
from .providers import ProviderRegistry
from .services import ChatService
from .storage import Storage


def run() -> None:
    try:
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

    from .ui import MainWindow

    storage = Storage(paths.db_path)
    service = ChatService(storage=storage, providers=ProviderRegistry())
    window = MainWindow(service=service, executor=ActionExecutor(), paths=paths)
    window.show()
    sys.exit(app.exec())
