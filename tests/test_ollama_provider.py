from __future__ import annotations

import unittest

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.exceptions import ProviderError
from local_assistant.providers.ollama import OllamaProvider


class OllamaProviderTests(unittest.TestCase):
    def test_parse_json_line(self) -> None:
        payload = b'{"message":{"role":"assistant","content":"hello"},"done":false}'

        parsed = OllamaProvider._parse_json_line(payload)

        self.assertEqual(parsed["message"]["content"], "hello")
        self.assertFalse(parsed["done"])

    def test_parse_json_line_rejects_invalid_json(self) -> None:
        with self.assertRaises(ProviderError):
            OllamaProvider._parse_json_line(b"not json")


if __name__ == "__main__":
    unittest.main()
