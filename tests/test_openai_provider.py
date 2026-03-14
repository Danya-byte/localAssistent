from __future__ import annotations

import unittest

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.exceptions import ProviderError
from local_assistant.providers.openai_compatible import OpenAICompatibleProvider


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_parse_json_accepts_valid_payload(self) -> None:
        payload = '{"choices":[{"delta":{"content":"hello"}}]}'

        parsed = OpenAICompatibleProvider._parse_json(payload)

        self.assertEqual(parsed["choices"][0]["delta"]["content"], "hello")

    def test_parse_json_rejects_invalid_payload(self) -> None:
        with self.assertRaises(ProviderError):
            OpenAICompatibleProvider._parse_json("not-json")


if __name__ == "__main__":
    unittest.main()
