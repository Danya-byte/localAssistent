from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.config import AppPaths


class AppPathsTests(unittest.TestCase):
    def test_resolve_uses_local_assistant_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get("LOCAL_ASSISTANT_HOME")
            os.environ["LOCAL_ASSISTANT_HOME"] = temp_dir
            try:
                paths = AppPaths.resolve()
            finally:
                if previous is None:
                    os.environ.pop("LOCAL_ASSISTANT_HOME", None)
                else:
                    os.environ["LOCAL_ASSISTANT_HOME"] = previous

        self.assertEqual(paths.root, Path(temp_dir).resolve())
        self.assertEqual(paths.db_path, Path(temp_dir).resolve() / "data" / "app.sqlite3")

if __name__ == "__main__":
    unittest.main()
