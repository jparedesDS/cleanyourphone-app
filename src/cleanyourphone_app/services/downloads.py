"""Download Google's official Platform-Tools after an explicit user action.

Platform-Tools are not bundled or redistributed with the app. This module
fetches the pinned archive from Google's download server only when the user
asks for it, verifies the pinned SHA-256 before touching the destination, and
leaves no usable adb behind when any step fails.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import BinaryIO

PLATFORM_TOOLS_VERSION = "37.0.1"
PLATFORM_TOOLS_URL = (
    "https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip"
)
PLATFORM_TOOLS_SHA256 = (
    "45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99"
)

_CHUNK = 1024 * 1024
_DOWNLOAD_TIMEOUT = 60
_PREFIX = "platform-tools"


class DownloadError(RuntimeError):
    """Platform-Tools could not be downloaded, verified or extracted."""


def _remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
        return
    try:
        path.unlink()
    except OSError:
        pass


def _validate_member(name: str) -> None:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute():
        raise DownloadError(f"refusing unsafe archive member: {name!r}")
    for part in path.parts:
        if part in ("", ".", "..") or ":" in part:
            raise DownloadError(f"refusing unsafe archive member: {name!r}")


class PlatformToolsDownloader:
    """Download, verify and install the pinned Windows Platform-Tools archive.

    ``destination`` must be an app-owned directory. The executable is installed
    as ``<destination>/platform-tools/adb.exe``; a failed attempt removes that
    tree so a partial or unverified adb can never be picked up later.
    """

    def __init__(
        self,
        *,
        url: str = PLATFORM_TOOLS_URL,
        sha256: str = PLATFORM_TOOLS_SHA256,
        opener: Callable[[str], BinaryIO] | None = None,
    ) -> None:
        self._url = url
        self._sha256 = sha256.strip().lower()
        self._opener = opener or (
            lambda address: urllib.request.urlopen(
                address, timeout=_DOWNLOAD_TIMEOUT
            )
        )

    def download(self, destination: str | os.PathLike[str]) -> Path:
        """Install Platform-Tools under *destination* and return ``adb.exe``."""
        destination = Path(destination)
        target = destination / _PREFIX
        try:
            destination.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(prefix=".platform-tools-", dir=destination)
            )
        except OSError as exc:
            raise DownloadError(
                f"could not prepare the Platform-Tools folder {destination}: {exc}"
            ) from exc

        try:
            archive_path = staging / "platform-tools.zip"
            digest = self._fetch(archive_path)
            if digest != self._sha256:
                raise DownloadError(
                    "Platform-Tools SHA-256 mismatch: "
                    f"expected {self._sha256}, got {digest}"
                )

            extracted = staging / "extracted"
            self._extract(archive_path, extracted)
            staged_tools = extracted / _PREFIX
            adb_path = staged_tools / "adb.exe"
            if not adb_path.is_file():
                raise DownloadError(
                    "the Platform-Tools archive did not contain "
                    "platform-tools/adb.exe"
                )

            _remove(target)
            os.replace(staged_tools, target)
            return target / "adb.exe"
        except DownloadError:
            _remove(target)
            raise
        except Exception as exc:
            _remove(target)
            raise DownloadError(f"could not install Platform-Tools: {exc}") from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _fetch(self, archive_path: Path) -> str:
        """Stream the archive to disk and return its SHA-256 digest."""
        digest = hashlib.sha256()
        try:
            response = self._opener(self._url)
        except OSError as exc:
            raise DownloadError(f"could not download {self._url}: {exc}") from exc

        try:
            with contextlib.closing(response):
                with archive_path.open("wb") as handle:
                    while True:
                        chunk = response.read(_CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
        except OSError as exc:
            raise DownloadError(f"could not download {self._url}: {exc}") from exc
        return digest.hexdigest()

    def _extract(self, archive_path: Path, destination: Path) -> None:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for info in archive.infolist():
                    name = info.filename.replace("\\", "/")
                    _validate_member(name)
                    parts = PurePosixPath(name).parts
                    if not parts or parts[0] != _PREFIX or info.is_dir():
                        continue
                    if len(parts) == 1:
                        continue
                    if stat.S_ISLNK(info.external_attr >> 16):
                        raise DownloadError(
                            f"refusing symlink in Platform-Tools archive: {name!r}"
                        )

                    output = destination.joinpath(*parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, output.open("wb") as sink:
                        shutil.copyfileobj(source, sink, _CHUNK)
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError(
                f"could not extract Platform-Tools: {exc}"
            ) from exc
