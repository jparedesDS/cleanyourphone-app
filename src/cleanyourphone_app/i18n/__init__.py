"""Bundled English and Spanish UI copy."""

from .packages import PackageCatalog
from .translator import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    Translator,
    normalize_language,
)

__all__ = [
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "PackageCatalog",
    "Translator",
    "normalize_language",
]
