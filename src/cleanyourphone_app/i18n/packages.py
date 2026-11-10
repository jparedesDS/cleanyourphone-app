"""Spanish package details with a safe English fallback.

The CLI ships the plan's ``why`` and ``breaks`` copy in English. This module
keeps a bundled Spanish catalog for the packages the four device profiles can
offer, so the review screen can explain every row without inventing a
translation at runtime. ``lookup`` never hides a package: when the catalog has
no text for that field it returns the English copy and ``False``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

PACKAGE_FIELDS: tuple[str, ...] = ("why", "breaks")
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "packages_es.json"


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"could not read package catalog {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"package catalog {path} is not valid JSON: {error}") from error


class PackageCatalog:
    """Package id to Spanish ``why``/``breaks`` details."""

    def __init__(self, entries: Mapping[str, Mapping[str, str]]) -> None:
        normalized: dict[str, dict[str, str]] = {}
        for package_id, entry in entries.items():
            normalized[package_id] = {field: entry[field] for field in PACKAGE_FIELDS}
        self._entries = MappingProxyType(
            {
                package_id: MappingProxyType(entry)
                for package_id, entry in normalized.items()
            }
        )

    @classmethod
    def from_dict(cls, payload: object) -> PackageCatalog:
        """Build a catalog from a JSON-shaped mapping, validating every entry."""
        if not isinstance(payload, Mapping):
            raise ValueError("package catalog must be a JSON object")
        entries: dict[str, dict[str, str]] = {}
        for package_id, value in payload.items():
            if not isinstance(package_id, str) or not package_id.strip():
                raise ValueError("package catalog ids must be non-empty strings")
            if not isinstance(value, Mapping):
                raise ValueError(f"{package_id} must be a JSON object")
            entry: dict[str, str] = {}
            for field in PACKAGE_FIELDS:
                text = value.get(field)
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(
                        f"{package_id}.{field} must be a non-empty string"
                    )
                entry[field] = text.strip()
            entries[package_id] = entry
        return cls(entries)

    @classmethod
    def from_file(cls, path: str | Path) -> PackageCatalog:
        """Load a catalog from *path*."""
        return cls.from_dict(_read_json(Path(path)))

    @classmethod
    def default(cls) -> PackageCatalog:
        """Load the bundled Spanish catalog."""
        return cls.from_file(DEFAULT_CATALOG_PATH)

    def package_ids(self) -> tuple[str, ...]:
        """Return every package id in stable sorted order."""
        return tuple(sorted(self._entries))

    def lookup(
        self, package_id: str, field: str, english: str
    ) -> tuple[str, bool]:
        """Return Spanish text when known, else the English copy and ``False``."""
        if field not in PACKAGE_FIELDS:
            raise ValueError(f"unknown package detail field: {field}")
        entry = self._entries.get(package_id)
        if entry is not None:
            text = entry.get(field, "")
            if text.strip():
                return text, True
        return english, False

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, package_id: object) -> bool:
        return isinstance(package_id, str) and package_id in self._entries


__all__ = [
    "DEFAULT_CATALOG_PATH",
    "PACKAGE_FIELDS",
    "PackageCatalog",
]
