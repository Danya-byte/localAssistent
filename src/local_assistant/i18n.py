from __future__ import annotations

from dataclasses import dataclass

from .locales import EN_TRANSLATIONS, RU_TRANSLATIONS
from .models import Language


TRANSLATIONS: dict[Language, dict[str, str]] = {
    "en": EN_TRANSLATIONS,
    "ru": RU_TRANSLATIONS,
}


@dataclass(slots=True)
class LocalizationManager:
    language: Language

    def set_language(self, language: Language) -> None:
        self.language = language

    def t(self, key: str, **kwargs: str) -> str:
        template = TRANSLATIONS.get(self.language, TRANSLATIONS["en"]).get(key, key)
        return template.format(**kwargs)
