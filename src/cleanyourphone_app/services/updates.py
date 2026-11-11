"""Check GitHub for a newer app release and, when asked, install it.

The check only reads the latest release metadata. Downloading and installing
happen only after the person presses the update button and confirms: the
installer is downloaded to an app-owned folder, its SHA-256 is verified, the
app closes, a small helper runs the installer silently and the app restarts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

RELEASES_API = (
    "https://api.github.com/repos/jparedesDS/cleanyourphone-app/releases/latest"
)
RELEASES_PAGE = (
    "https://github.com/jparedesDS/cleanyourphone-app/releases/latest"
)
_RELEASE_DOWNLOAD_PREFIX = (
    "https://github.com/jparedesDS/cleanyourphone-app/releases/download/"
)
_TIMEOUT = 10
_CHUNK = 1024 * 1024


class UpdateCheckError(RuntimeError):
    """The latest release could not be read from GitHub."""


class UpdateInstallError(RuntimeError):
    """The update installer could not be downloaded or verified."""


class UpdateCancelled(UpdateInstallError):
    """The person cancelled the update download."""


@dataclass(frozen=True)
class UpdateInfo:
    """One newer release returned by GitHub."""

    version: str
    tag: str
    url: str = RELEASES_PAGE
    notes: str = ""
    published_at: str = ""
    installer_url: str | None = None
    sha256: str | None = None
    size: int | None = None

    @property
    def can_install(self) -> bool:
        """True only when a verified installer can be offered."""
        return bool(self.installer_url and self.sha256)


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


def _installer_asset(payload: dict, version: str) -> dict | None:
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    candidates: list[dict] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", "")).strip()
        if not name.lower().endswith(".exe"):
            continue
        if not url.startswith(_RELEASE_DOWNLOAD_PREFIX):
            continue
        candidates.append(asset)
    for asset in candidates:
        if version in str(asset.get("name", "")):
            return asset
    return candidates[0] if candidates else None


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

    notes = str(payload.get("body", "")).strip()
    installer_url = None
    sha256 = None
    size = None
    asset = _installer_asset(payload, version)
    if asset is not None:
        candidate = str(asset.get("browser_download_url", "")).strip()
        match = re.search(r"SHA-256:\s*([0-9a-fA-F]{64})", notes)
        if candidate and match:
            installer_url = candidate
            sha256 = match.group(1).lower()
            raw_size = asset.get("size")
            if isinstance(raw_size, int) and raw_size > 0:
                size = raw_size

    return UpdateInfo(
        version=version,
        tag=tag,
        url=RELEASES_PAGE,
        notes=notes,
        published_at=str(payload.get("published_at", "")).strip(),
        installer_url=installer_url,
        sha256=sha256,
        size=size,
    )


def default_update_dir(local_app_data: str | os.PathLike[str] | None = None) -> Path:
    """Return the app-owned folder used for downloaded installers."""
    root = (
        Path(local_app_data)
        if local_app_data is not None
        else Path(os.environ.get("LOCALAPPDATA", Path.home()))
    )
    return root / "CleanYourPhone" / "updates"


def _safe_version(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]", "", str(value))
    return cleaned or "update"


def download_update(
    info: UpdateInfo,
    destination: str | os.PathLike[str],
    *,
    opener: Callable[[str], BinaryIO] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Path:
    """Download and verify the installer, returning its local path."""
    if not info.can_install:
        raise UpdateInstallError("this release does not provide a verified installer")

    folder = Path(destination)
    target = folder / f"CleanYourPhone-Setup-{_safe_version(info.version)}.exe"
    staging = target.with_suffix(target.suffix + ".part")
    folder.mkdir(parents=True, exist_ok=True)
    open_url = opener or (
        lambda url: urllib.request.urlopen(url, timeout=_TIMEOUT)
    )

    digest = hashlib.sha256()
    total = 0
    try:
        with open_url(info.installer_url) as response, staging.open("wb") as handle:
            while True:
                if cancel is not None and cancel():
                    raise UpdateCancelled("update download cancelled")
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                total += len(chunk)
        if info.size is not None and total != info.size:
            raise UpdateInstallError(
                f"installer size mismatch: expected {info.size}, got {total}"
            )
        if digest.hexdigest().lower() != info.sha256.lower():
            raise UpdateInstallError(
                "installer SHA-256 mismatch: expected "
                f"{info.sha256}, got {digest.hexdigest()}"
            )
        os.replace(staging, target)
        return target
    except UpdateCancelled:
        staging.unlink(missing_ok=True)
        raise
    except UpdateInstallError:
        staging.unlink(missing_ok=True)
        raise
    except Exception as exc:
        staging.unlink(missing_ok=True)
        raise UpdateInstallError(f"could not download the update: {exc}") from exc


def launch_update_helper(
    installer: str | os.PathLike[str],
    app_exe: str | os.PathLike[str],
    *,
    pid: int | None = None,
    directory: str | os.PathLike[str] | None = None,
    starter: Callable[..., object] | None = None,
) -> Path:
    """Write and start a detached helper that installs after the app exits."""
    installer_path = Path(installer).resolve()
    app_path = Path(app_exe).resolve()
    if not installer_path.is_file():
        raise UpdateInstallError(f"installer not found: {installer_path}")

    helper_dir = Path(directory) if directory is not None else installer_path.parent
    helper_dir.mkdir(parents=True, exist_ok=True)
    process_id = os.getpid() if pid is None else int(pid)
    helper = helper_dir / f"install-{_safe_version(installer_path.stem)}.cmd"
    script = (
        "@echo off\n"
        "setlocal\n"
        ":wait\n"
        f'tasklist /FI "PID eq {process_id}" 2>nul | findstr /C:"{process_id}" >nul\n'
        "if not errorlevel 1 (\n"
        "  timeout /t 1 /nobreak >nul\n"
        "  goto wait\n"
        ")\n"
        f'start "" /wait "{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES '
        "/NORESTART /CLOSEAPPLICATIONS\n"
        f'start "" "{app_path}"\n'
        'del "%~f0"\n'
    )
    helper.write_text(script, encoding="utf-8", newline="\r\n")

    launch = starter or subprocess.Popen
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "DETACHED_PROCESS", 0
    )
    launch(["cmd.exe", "/c", str(helper)], creationflags=flags, close_fds=True)
    return helper


__all__ = [
    "RELEASES_API",
    "RELEASES_PAGE",
    "UpdateCancelled",
    "UpdateCheckError",
    "UpdateInfo",
    "UpdateInstallError",
    "check_for_update",
    "default_update_dir",
    "download_update",
    "is_newer",
    "launch_update_helper",
    "parse_version",
]
