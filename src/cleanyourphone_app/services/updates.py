"""Check the public GitHub release feed for a newer app version.

This module only reads the latest release metadata. It deliberately does not
download or run the installer: the update button opens the release page so the
person can review it and download the installer themselves.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO

RELEASES_API = (
    "https://api.github.com/repos/jparedesDS/cleanyourphone-app/releases/latest"
)
RELEASES_PAGE = (
    "https://github.com/jparedesDS/cleanyourphone-app/releases/latest"
)
_TIMEOUT = 10


class UpdateCheckError(RuntimeError):
    """The latest release could not be read from GitHub."""


@dataclass(frozen=True)
class UpdateInfo:
    """One newer release returned by GitHub."""

    version: str
    tag: str
    url: str = RELEASES_PAGE
    notes: str = ""
    published_at: str = ""


def parse_version(value: str) -> tuple[int, ...]:
    """Return the numeric parts of a version or tag, ignoring a leading ``v``."""
    match = re.search(r"(\d+(?:\.\d+)*)", str(value).strip())
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    """Return whether *latest* is strictly newer than *current*.

    Malformed values compare as not newer; the app should never offer an update
    it cannot understand.
    """
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    if not latest_parts or not current_parts:
        return False
    width = max(len(latest_parts), len(current_parts))
    latest_padded = latest_parts + (0,) * (width - len(latest_parts))
    current_padded = current_parts + (0,) * (width - len(current_parts))
    return latest_padded > current_padded


def check_for_update(
    current_version: str,
    *,
    opener: Callable[[object], BinaryIO] | None = None,
) -> UpdateInfo | None:
    """Return the latest release when it is newer than *current_version*.

    ``opener`` is injectable for tests. It receives a prepared
    :class:`urllib.request.Request` and must return a binary response.
    """
    open_url = opener or (
        lambda request: urllib.request.urlopen(request, timeout=_TIMEOUT)
    )
    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"CleanYourPhone/{current_version}",
        },
    )
    try:
        with open_url(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise UpdateCheckError("could not read the latest GitHub release") from exc

    if not isinstance(payload, dict):
        raise UpdateCheckError("the latest GitHub release is not an object")

    tag = str(payload.get("tag_name", "")).strip()
    version = tag.removeprefix("v")
    if not version or not is_newer(version, current_version):
        return None

    return UpdateInfo(
        version=version,
        tag=tag,
        url=RELEASES_PAGE,
        notes=str(payload.get("body", "")).strip(),
        published_at=str(payload.get("published_at", "")).strip(),
    )


__all__ = [
    "RELEASES_API",
    "RELEASES_PAGE",
    "UpdateCheckError",
    "UpdateInfo",
    "check_for_update",
    "is_newer",
    "parse_version",
]
