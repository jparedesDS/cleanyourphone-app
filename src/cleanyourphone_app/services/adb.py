"""Find a supported ADB executable and list connected Android devices.

ADB is never bundled with the app. This module only locates a binary that has
already been installed, and it returns a path only after ``adb version`` reports
at least :data:`MIN_ADB_VERSION`. Callers must use :attr:`AdbInfo.path` for
device operations so an old or broken adb is never executed by the app.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

MIN_ADB_VERSION = (31, 0, 0)

_VERSION_TIMEOUT = 15
_DEVICES_TIMEOUT = 30
_STDERR_TAIL = 500
_CHUNK = 1024 * 1024
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# Newer adb builds print a legacy banner ("version 1.0.41") followed by the
# Platform-Tools version ("Version 37.0.1-..."). The last match is the real one.
_VERSION_PATTERN = re.compile(r"version\s+(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)
_SKIP_PREFIXES = ("adb:", "error:", "warning:", "cannot", "failed")

# A pure runner only has the tuple; the built-in runner also returns the text.
_VersionProbe = (
    tuple[int, int, int] | tuple[tuple[int, int, int], str]
)


@dataclass(frozen=True)
class AdbInfo:
    """A verified ADB executable and the version it reported."""

    path: Path
    version: tuple[int, int, int]
    version_text: str


@dataclass(frozen=True)
class DeviceEntry:
    """One row from ``adb devices -l``."""

    serial: str
    state: str
    model: str
    transport: str


class AdbError(RuntimeError):
    """ADB could not be run or returned an unusable result."""


def _tail(text: str, limit: int = _STDERR_TAIL) -> str:
    text = text.strip()
    if not text:
        return "(empty)"
    if len(text) <= limit:
        return text
    return "..." + text[-limit:]


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AdbError(f"could not run `{' '.join(args)}`: {exc}") from exc


def parse_adb_version(text: str) -> tuple[int, int, int]:
    """Read the Platform-Tools version from ``adb version`` output.

    The last version-like token wins because newer builds also print the
    legacy ``Android Debug Bridge version 1.0.41`` banner first.
    """
    if not isinstance(text, str):
        raise ValueError("adb version output must be text")
    matches = _VERSION_PATTERN.findall(text)
    if not matches:
        raise ValueError("adb version output did not contain a version")
    major, minor, patch = matches[-1]
    return int(major), int(minor), int(patch)


def _default_version_runner(
    adb_path: Path,
) -> tuple[tuple[int, int, int], str]:
    completed = _run([str(adb_path), "version"], _VERSION_TIMEOUT)
    text = f"{completed.stdout or ''}{completed.stderr or ''}"
    if completed.returncode != 0:
        raise AdbError(
            f"`{adb_path} version` exited with {completed.returncode}; "
            f"stderr: {_tail(completed.stderr or '')}"
        )
    return parse_adb_version(text), text


def default_cache_dir(local_app_data: str | Path | None = None) -> Path:
    """Return the app-owned directory that holds a downloaded Platform-Tools."""
    root: str | Path | None
    if local_app_data is not None:
        root = local_app_data
    else:
        root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "CleanYourPhone"
    return Path.home() / ".cleanyourphone"


class AdbLocator:
    """Look for ADB in a fixed, predictable order.

    Candidates are checked in this order: the ``ADB`` environment variable,
    ``PATH``, the Android SDK under ``%LOCALAPPDATA%`` and finally the copy the
    app downloaded into its own cache. A candidate is accepted only when it is
    a file and its version is at least :data:`MIN_ADB_VERSION`.
    """

    def __init__(
        self,
        version_runner: Callable[[Path], _VersionProbe | None] | None = None,
        cache_dir: str | Path | None = None,
        local_app_data: str | Path | None = None,
    ) -> None:
        self._version_runner = version_runner or _default_version_runner
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._local_app_data = (
            Path(local_app_data) if local_app_data is not None else None
        )

    @property
    def cache_dir(self) -> Path:
        if self._cache_dir is not None:
            return self._cache_dir
        return default_cache_dir(self._local_app_data)

    def _local_app_data_dir(self) -> Path | None:
        if self._local_app_data is not None:
            return self._local_app_data
        raw = os.environ.get("LOCALAPPDATA")
        return Path(raw) if raw else None

    def candidates(self) -> Iterator[Path]:
        seen: set[str] = set()

        def remember(path: Path) -> Path | None:
            key = os.path.normcase(os.path.abspath(os.fspath(path)))
            if key in seen:
                return None
            seen.add(key)
            return path

        env_adb = os.environ.get("ADB", "").strip().strip('"')
        if env_adb:
            candidate = remember(Path(env_adb))
            if candidate is not None:
                yield candidate

        path_adb = shutil.which("adb")
        if path_adb:
            candidate = remember(Path(path_adb))
            if candidate is not None:
                yield candidate

        local = self._local_app_data_dir()
        if local is not None:
            candidate = remember(local / "Android" / "Sdk" / "platform-tools" / "adb.exe")
            if candidate is not None:
                yield candidate

        candidate = remember(self.cache_dir / "platform-tools" / "adb.exe")
        if candidate is not None:
            yield candidate

    def accept(self, path: str | os.PathLike[str]) -> AdbInfo | None:
        """Return an :class:`AdbInfo` when *path* is a supported ADB binary."""
        candidate = Path(path)
        try:
            if not candidate.is_file():
                return None
        except OSError:
            return None

        try:
            probe = self._version_runner(candidate)
        except (AdbError, OSError, ValueError, subprocess.SubprocessError):
            return None

        if probe is None:
            return None
        if (
            isinstance(probe, tuple)
            and len(probe) == 2
            and isinstance(probe[0], tuple)
        ):
            version, version_text = probe
        elif isinstance(probe, tuple) and len(probe) == 3:
            version, version_text = probe, ""
        else:
            return None

        try:
            normalized = (int(version[0]), int(version[1]), int(version[2]))
        except (IndexError, TypeError, ValueError):
            return None
        if normalized < MIN_ADB_VERSION:
            return None
        if not version_text:
            version_text = "Version " + ".".join(str(part) for part in normalized)
        return AdbInfo(path=candidate, version=normalized, version_text=version_text)

    def find(self) -> AdbInfo | None:
        """Return the first acceptable ADB, or ``None`` when none is usable."""
        for candidate in self.candidates():
            info = self.accept(candidate)
            if info is not None:
                return info
        return None


def parse_devices(output: str) -> list[DeviceEntry]:
    """Parse ``adb devices -l`` output into typed rows."""
    devices: list[DeviceEntry] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        if line.lower().startswith("list of devices attached"):
            continue
        if line.startswith(_SKIP_PREFIXES):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = ""
        for token in parts[2:]:
            if token.startswith("model:"):
                model = token[len("model:") :]
                break
        transport = "wifi" if serial.startswith("adb-") or ":" in serial else "usb"
        devices.append(
            DeviceEntry(
                serial=serial,
                state=state,
                model=model,
                transport=transport,
            )
        )
    return devices


def _default_devices_runner(adb_path: Path) -> str:
    completed = _run([str(adb_path), "devices", "-l"], _DEVICES_TIMEOUT)
    if completed.returncode != 0:
        raise AdbError(
            f"`{adb_path} devices -l` exited with {completed.returncode}; "
            f"stderr: {_tail(completed.stderr or '')}"
        )
    return completed.stdout or ""


def list_devices(
    adb: AdbInfo,
    runner: Callable[[Path], str] | None = None,
) -> list[DeviceEntry]:
    """Run ``adb devices -l`` on a version-checked ADB.

    Only an :class:`AdbInfo` returned by :meth:`AdbLocator.find` is accepted so
    a raw, unverified path can never be executed. A forged outdated version is
    rejected as well.
    """
    if not isinstance(adb, AdbInfo):
        raise TypeError(
            "list_devices requires an AdbInfo from AdbLocator.find(), "
            f"not {type(adb).__name__}"
        )
    if adb.version < MIN_ADB_VERSION:
        raise ValueError(
            f"adb {adb.version} is older than the minimum {MIN_ADB_VERSION}"
        )
    path = adb.path
    active_runner = runner or _default_devices_runner
    try:
        output = active_runner(path)
    except AdbError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise AdbError(f"could not run `{path} devices -l`: {exc}") from exc
    if not isinstance(output, str):
        raise AdbError(f"`{path} devices -l` returned no text output")
    return parse_devices(output)
