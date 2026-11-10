"""Small JSON-backed translator for the two first-class app languages.

The catalogs are plain UTF-8 JSON objects shipped with the package so a frozen
PyInstaller build needs no extra data path. ``tr`` looks in the active language,
then in English, then returns the key itself; a missing placeholder never
crashes a screen.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "es")
DEFAULT_LANGUAGE = "en"

_CATALOG_DIR = Path(__file__).resolve().parent
_CATALOG_CACHE: dict[str, dict[str, str]] = {}


def normalize_language(language: str | None) -> str:
    """Return ``en`` or ``es`` for a locale such as ``es-ES`` or ``es_MX``."""
    if not isinstance(language, str) or not language.strip():
        return DEFAULT_LANGUAGE
    primary = language.strip().replace("_", "-").split("-", 1)[0].lower()
    if primary in SUPPORTED_LANGUAGES:
        return primary
    return DEFAULT_LANGUAGE


def _read_catalog(language: str) -> dict[str, str]:
    cached = _CATALOG_CACHE.get(language)
    if cached is not None:
        return cached

    path = _CATALOG_DIR / f"{language}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    catalog = {str(key): str(value) for key, value in payload.items()}
    _CATALOG_CACHE[language] = catalog
    return catalog


class Translator:
    """Look up UI copy by key in the active language with English fallback."""

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        *,
        catalogs: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        if catalogs is None:
            self._catalogs = {
                code: dict(_read_catalog(code)) for code in SUPPORTED_LANGUAGES
            }
        else:
            self._catalogs = {
                normalize_language(code): {str(k): str(v) for k, v in catalog.items()}
                for code, catalog in catalogs.items()
            }
        self._language = normalize_language(language)

    @property
    def language(self) -> str:
        return self._language

    @property
    def available_languages(self) -> tuple[str, ...]:
        return SUPPORTED_LANGUAGES

    @classmethod
    def for_system_language(cls, locale: str | None = None) -> Translator:
        """Build a translator from a Windows locale name.

        Only Spanish and English are first-class; every other locale gets
        English. The Windows UI language is passed in by ``ui.app.run`` so this
        class stays free of Qt imports.
        """
        return cls(normalize_language(locale))

    def set_language(self, language: str) -> str:
        """Switch the active language and return the normalized code."""
        self._language = normalize_language(language)
        return self._language

    def has(self, key: str) -> bool:
        return key in self._catalogs.get(
            self._language, {}
        ) or key in self._catalogs.get(DEFAULT_LANGUAGE, {})

    def tr(self, key: str, **kwargs: object) -> str:
        """Return translated text for *key*, falling back to English then *key*."""
        text = self._catalogs.get(self._language, {}).get(key)
        if text is None:
            text = self._catalogs.get(DEFAULT_LANGUAGE, {}).get(key)
        if text is None:
            return key
        if not kwargs:
            return text
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # A copy edit that drops a placeholder must not break a screen.
            return text
