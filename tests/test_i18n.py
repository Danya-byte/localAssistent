from __future__ import annotations

import unittest

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.i18n import LocalizationManager, TRANSLATIONS


class LocalizationTests(unittest.TestCase):
    def test_locale_key_sets_match(self) -> None:
        self.assertEqual(set(TRANSLATIONS["en"]), set(TRANSLATIONS["ru"]))

    def test_missing_key_falls_back_to_key_name(self) -> None:
        manager = LocalizationManager("en")

        self.assertEqual(manager.t("missing-key"), "missing-key")


if __name__ == "__main__":
    unittest.main()
