"""Persist the few app preferences in a local JSON file.

Settings live in ``%LOCALAPPDATA%\\CleanYourPhone\\settings.json`` and are never
sent anywhere. A missing, malformed or partial file simply falls back to the
defaults so a broken settings file cannot stop the app from starting.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from cleanyourphone_app.i18n.translator import SUPPORTED_LANGUAGES

APP_FOLDER = "CleanYourPhone"
SETTINGS_FILE = "settings.json"
_FALLBACK_FOLDER = ".cleanyourphone"


def default_path(local_app_data: str | Path | None = None) -> Path:
    """Return the per-user settings path, honoring ``LOCALAPPDATA``."""
    root: str | Path | None
    if local_app_data is not None:
        root = local_app_data
    else:
        root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / APP_FOLDER / SETTINGS_FILE
    return Path.home() / _FALLBACK_FOLDER / SETTINGS_FILE


def _normalize_language(value: object) -> str:
    if isinstance(value, str):
        checked = value.strip().lower()
        if checked in SUPPORTED_LANGUAGES:
            return checked
    return ""


def _normalize_adb_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    checked = value.strip()
    return checked or None


@dataclass
class Settings:
    """The small set of preferences the MVP persists.

    ``language`` is ``""`` until the user chooses one; an empty value means the
    app follows the Windows UI language (Spanish or English, otherwise English).
    """

    path: Path | None = field(default_factory=default_path)
    language: str = ""
    adb_path: str | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)
        self.language = _normalize_language(self.language)
        self.adb_path = _normalize_adb_path(self.adb_path)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Settings:
        """Read *path*, or the default path, returning defaults on any problem."""
        target = Path(path) if path is not None else default_path()
        if not target.is_file():
            return cls(path=target)

        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return cls(path=target)
        if not isinstance(payload, dict):
            return cls(path=target)

        return cls(
            path=target,
            language=_normalize_language(payload.get("language")),
            adb_path=_normalize_adb_path(payload.get("adb_path")),
        )

    @classmethod
    def in_memory(cls, language: str = "en", adb_path: str | None = None) -> Settings:
        """Build settings that never touch the disk, for tests and previews."""
        return cls(path=None, language=language, adb_path=adb_path)

    @staticmethod
    def default_path(local_app_data: str | Path | None = None) -> Path:
        return default_path(local_app_data)

    def save(self) -> None:
        """Write the settings atomically, creating parent directories."""
        if self.path is None:
            return

        self.language = _normalize_language(self.language)
        self.adb_path = _normalize_adb_path(self.adb_path)
        payload = {"language": self.language, "adb_path": self.adb_path}
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, self.path)
