"""Locate the backup folder the CLI just wrote for this exact phone.

The CLI owns the backup folder layout (one directory per run, each with a
``meta.json``). The app only needs one fact after ``backup``: the newest matching
folder for the pinned serial and fingerprint. A mismatched or unreadable folder
is ignored, so a stale backup can never be used to unlock Review.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _mtime(folder: Path) -> float:
    try:
        return folder.stat().st_mtime
    except OSError:
        return 0.0


def _timestamp_key(meta: Mapping[str, Any], folder: Path) -> tuple[str, float]:
    """Return a sortable timestamp, falling back to the folder mtime.

    The real CLI writes ``YYYYmmdd_HHMMSS`` strings, which sort correctly as
    text. Numbers are normalized to a fixed-width string so they never compare
    against a text timestamp with a different type.
    """
    raw = meta.get("timestamp")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), _mtime(folder)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return f"{float(raw):020.6f}", _mtime(folder)
    return f"{_mtime(folder):020.6f}", _mtime(folder)


def _read_meta(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _matches(meta: Mapping[str, Any], serial: str, fingerprint: str) -> bool:
    probe = meta.get("probe")
    if not isinstance(probe, Mapping):
        return False
    return (
        meta.get("serial") == serial
        and probe.get("fingerprint") == fingerprint
    )


class BackupStore:
    """Read-only view of the CLI's backup directory."""

    @staticmethod
    def latest(serial: str, fingerprint: str, root: Path) -> Path | None:
        """Return the newest backup folder for *serial* and *fingerprint*.

        ``root`` is the CLI's backup directory, normally
        ``Path.home() / ".cleanyourphone" / "backup"``. Malformed metadata is
        skipped; the caller treats ``None`` as a failed backup and stops.
        """
        if not isinstance(serial, str) or not serial.strip():
            raise ValueError("serial must be a non-empty string")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(root, Path):
            raise TypeError("root must be a pathlib.Path")

        if not root.is_dir():
            return None

        candidates: list[tuple[tuple[str, float], Path]] = []
        for meta_path in root.glob("*/meta.json"):
            meta = _read_meta(meta_path)
            if meta is None or not _matches(meta, serial, fingerprint):
                continue
            folder = meta_path.parent
            candidates.append((_timestamp_key(meta, folder), folder))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]


__all__ = ["BackupStore"]
