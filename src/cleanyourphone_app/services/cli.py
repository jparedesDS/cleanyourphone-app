"""Typed client for the frozen CleanYourPhone CLI sidecar.

The CLI is the only path that writes to the phone. This module only starts the
sidecar and reads its machine-readable output; it never talks to ADB directly.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from cleanyourphone_app.domain.models import PlanData, ProbeData

_T = TypeVar("_T")
_STDERR_TAIL = 500
# The app is a windowed executable, so a console-subsystem sidecar would spawn
# a fresh console window for every call without this flag.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


@dataclass(frozen=True)
class CliResult:
    """The completed process result of one sidecar invocation."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CliError(RuntimeError):
    """The sidecar could not be started or did not finish."""


class CliProtocolError(CliError):
    """The sidecar returned an unexpected exit code or JSON shape."""


def _tail(text: str, limit: int = _STDERR_TAIL) -> str:
    text = text.strip()
    if not text:
        return "(empty)"
    if len(text) <= limit:
        return text
    return "..." + text[-limit:]


def _command_text(args: Sequence[str]) -> str:
    return " ".join(args) if args else "(no arguments)"


def _message(args: Sequence[str], reason: str, stderr: str) -> str:
    return f"`{_command_text(args)}` {reason}; stderr: {_tail(stderr)}"


def _verify_payload(payload: Any) -> dict[str, Any]:
    """Normalize the CLI verify JSON to the dict promised by ``verify``.

    The v0.2.2 sidecar prints a JSON array of ``{check, status, detail}``
    objects. The app interface is a dict, so the array is exposed under
    ``checks`` and every check is validated before it reaches the UI.
    """
    if isinstance(payload, Mapping):
        checks = payload.get("checks")
        if checks is None:
            raise ValueError("verify object must contain a 'checks' list")
    else:
        checks = payload
    if not isinstance(checks, list):
        raise ValueError("verify checks must be a list")
    if not checks:
        raise ValueError("verify returned no checks")

    normalized: list[dict[str, str]] = []
    for index, check in enumerate(checks):
        if not isinstance(check, Mapping):
            raise ValueError(f"verify check {index} must be a JSON object")
        row: dict[str, str] = {}
        for key in ("check", "status", "detail"):
            value = check.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"verify check {index} field {key!r} must be a non-empty string"
                )
            row[key] = value
        normalized.append(row)
    return {"checks": normalized}


def _disabled_packages(payload: Any) -> set[str]:
    if not isinstance(payload, list):
        raise ValueError("list payload must be a list")
    packages: set[str] = set()
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise ValueError(f"list row {index} must be a JSON object")
        package = row.get("package")
        if not isinstance(package, str) or not package.strip():
            raise ValueError(f"list row {index} package must be a non-empty string")
        packages.add(package)
    return packages


_DNS_CHECK_TEXT_FIELDS = (
    "ad_domain",
    "ad_ip",
    "ad_state",
    "control_domain",
    "control_ip",
    "control_state",
)
_BENCH_REQUIRED_KEYS = (
    "timestamp",
    "model",
    "android",
    "build",
    "ram_available_mb",
    "packages_enabled",
)


def _mapping(payload: Any, subject: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{subject} must be a JSON object")
    return payload


def _text(payload: Mapping[str, Any], key: str, subject: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{subject} field {key!r} must be a string")
    return value


def _non_empty_text(payload: Mapping[str, Any], key: str, subject: str) -> str:
    value = _text(payload, key, subject)
    if not value.strip():
        raise ValueError(f"{subject} field {key!r} must be a non-empty string")
    return value


def _path_argument(name: str, value: str | os.PathLike[str]) -> str:
    try:
        path = os.fspath(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a filesystem path") from exc
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"{name} must be a non-empty path")
    return path


def _dns_providers_payload(payload: Any) -> dict[str, dict[str, str]]:
    providers = _mapping(payload, "dns providers payload")
    if not providers:
        raise ValueError("dns providers returned no presets")

    normalized: dict[str, dict[str, str]] = {}
    for name, item in providers.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("dns providers preset names must be non-empty strings")
        subject = f"dns providers preset {name!r}"
        preset = _mapping(item, subject)
        normalized[name] = {
            "host": _non_empty_text(preset, "host", subject),
            "description": _non_empty_text(preset, "description", subject),
        }
    return normalized


def _dns_status_payload(payload: Any) -> dict[str, str]:
    status = _mapping(payload, "dns status payload")
    return {
        "mode": _non_empty_text(status, "mode", "dns status"),
        "specifier": _text(status, "specifier", "dns status"),
    }


def _dns_check_payload(payload: Any) -> dict[str, Any]:
    check = _mapping(payload, "dns check payload")
    normalized: dict[str, Any] = {}
    for key in _DNS_CHECK_TEXT_FIELDS:
        normalized[key] = _text(check, key, "dns check")
    for key in ("ad_domain", "control_domain"):
        if not normalized[key].strip():
            raise ValueError(f"dns check field {key!r} must be a non-empty string")

    blocked = check.get("ad_blocked")
    if blocked is not None and not isinstance(blocked, bool):
        raise ValueError("dns check field 'ad_blocked' must be true, false or null")
    online = check.get("online")
    if not isinstance(online, bool):
        raise ValueError("dns check field 'online' must be true or false")

    normalized["ad_blocked"] = blocked
    normalized["online"] = online
    return normalized


def _bench_snapshot_payload(payload: Any) -> dict[str, Any]:
    snapshot = _mapping(payload, "bench snapshot payload")
    path = _non_empty_text(snapshot, "path", "bench snapshot")
    data = _mapping(snapshot.get("data"), "bench snapshot data")

    missing = [key for key in _BENCH_REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"bench snapshot data is missing: {', '.join(missing)}")
    for key in ("timestamp", "model", "android", "build"):
        _text(data, key, "bench snapshot data")
    for key in ("ram_available_mb", "packages_enabled"):
        value = data.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise ValueError(
                f"bench snapshot data field {key!r} must be a number or null"
            )
    return {"path": path, "data": dict(data)}


def _bench_compare_payload(payload: Any) -> dict[str, Any]:
    comparison = _mapping(payload, "bench compare payload")
    path = _non_empty_text(comparison, "path", "bench compare")
    rows = comparison.get("rows")
    if not isinstance(rows, list):
        raise ValueError("bench compare field 'rows' must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        subject = f"bench compare row {index}"
        row = _mapping(item, subject)
        result: dict[str, Any] = {
            "metric": _non_empty_text(row, "metric", subject),
            "label": _non_empty_text(row, "label", subject),
        }
        for key in ("before", "after", "delta"):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{subject} field {key!r} must be a number")
            result[key] = value
        pct = row.get("pct")
        if pct is not None and (
            isinstance(pct, bool) or not isinstance(pct, (int, float))
        ):
            raise ValueError(f"{subject} field 'pct' must be a number or null")
        result["pct"] = pct
        normalized.append(result)
    return {"path": path, "rows": normalized}


def _bench_list_payload(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        raise ValueError("bench list payload must be a list")
    paths: list[str] = []
    for index, path in enumerate(payload):
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"bench list entry {index} must be a non-empty string")
        paths.append(path)
    return paths


class CliClient:
    """Starts the CLI with a fixed, app-owned environment.

    Callers supply ``ADB`` and ``CLEANYOURPHONE_PROFILES`` through ``env``. The
    backup and state directories are always pinned under the user's home so a
    frozen sidecar can never write inside its install directory.
    """

    def __init__(
        self,
        command: Sequence[str],
        env: Mapping[str, str] | None = None,
    ) -> None:
        if isinstance(command, str) or not command:
            raise ValueError("command must be a non-empty sequence of strings")
        self._command = tuple(str(part) for part in command)

        merged = dict(os.environ)
        if env is not None:
            merged.update({str(key): str(value) for key, value in env.items()})

        home = Path.home() / ".cleanyourphone"
        merged["CLEANYOURPHONE_BACKUP"] = str(home / "backup")
        merged["CLEANYOURPHONE_STATE"] = str(home)
        merged["PYTHONIOENCODING"] = "utf-8"
        self._env = merged

    def set_adb_path(self, path: str | os.PathLike[str] | None) -> None:
        """Point the next sidecar call at a verified ADB binary.

        The app verifies the binary before calling this; passing ``None`` clears
        the override and falls back to the environment the client was built
        with.
        """
        if path is None:
            self._env.pop("ADB", None)
            return
        value = os.fspath(path)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("ADB path must be a non-empty string")
        self._env["ADB"] = value

    def run(self, args: Sequence[str], timeout: int = 120) -> CliResult:
        """Run one sidecar command and capture its text output.

        A non-zero exit code is returned to the caller, not raised: write
        commands such as ``disable`` fail in ways the UI has to inspect.
        """
        argv = tuple(str(arg) for arg in args)
        try:
            completed = subprocess.run(
                [*self._command, *argv],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._env,
                timeout=timeout,
                check=False,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise CliError(
                f"`{_command_text(argv)}` timed out after {timeout} seconds"
            ) from exc
        except OSError as exc:
            raise CliError(f"could not run `{_command_text(argv)}`: {exc}") from exc

        return CliResult(
            args=argv,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    def _read_json(
        self,
        args: Sequence[str],
        parser: Callable[[Any], _T],
        timeout: int = 120,
        *,
        accepted_returncodes: tuple[int, ...] = (0,),
    ) -> _T:
        result = self.run(args, timeout=timeout)
        if result.returncode not in accepted_returncodes:
            raise CliProtocolError(
                _message(args, f"exited with {result.returncode}", result.stderr)
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CliProtocolError(
                _message(
                    args,
                    f"returned invalid JSON: {exc.msg} "
                    f"at line {exc.lineno} column {exc.colno}",
                    result.stderr,
                )
            ) from exc
        try:
            return parser(payload)
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise CliProtocolError(
                _message(args, f"returned an invalid payload: {exc}", result.stderr)
            ) from exc

    def probe(self) -> ProbeData:
        return self._read_json(("--json", "probe"), ProbeData.from_dict)

    def plan(self, profile_id: str) -> PlanData:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        return self._read_json(
            ("--json", "plan", "--profile", profile_id),
            PlanData.from_dict,
        )

    def verify(self) -> dict:
        # `verify` exits 1 when a check fails. The JSON payload is still valid
        # and is exactly what the failure path in the UI needs to display.
        return self._read_json(
            ("--json", "verify"),
            _verify_payload,
            accepted_returncodes=(0, 1),
        )

    def list_disabled(self) -> set[str]:
        return self._read_json(
            ("--json", "list", "--state", "disabled"),
            _disabled_packages,
        )

    def dns_providers(self) -> dict[str, dict[str, str]]:
        """Return the CLI's ad-blocking presets: ``{name: {host, description}}``."""
        return self._read_json(
            ("--json", "dns", "providers"),
            _dns_providers_payload,
        )

    def dns_status(self) -> dict[str, str]:
        """Return the current Private DNS ``{mode, specifier}``."""
        return self._read_json(
            ("--json", "dns", "status"),
            _dns_status_payload,
        )

    def dns_set(self, provider: str) -> CliResult:
        """Set a preset alias or a raw Private DNS hostname (journaled)."""
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider must be a non-empty string")
        return self.run(("dns", "set", provider))

    def dns_off(self) -> CliResult:
        """Return Private DNS to the Android default (journaled)."""
        return self.run(("dns", "off"))

    def dns_check(self) -> dict[str, Any]:
        # `dns check` exits 1 when ads are not confirmed blocked or the phone
        # cannot be tested. That payload is exactly what the UI has to show.
        return self._read_json(
            ("--json", "dns", "check"),
            _dns_check_payload,
            accepted_returncodes=(0, 1),
        )

    def bench_snapshot(self, label: str) -> dict[str, Any]:
        """Save a local measurement and return its ``{path, data}``."""
        if not isinstance(label, str) or not label.strip():
            raise ValueError("label must be a non-empty string")
        return self._read_json(
            ("--json", "bench", "snapshot", "--label", label),
            _bench_snapshot_payload,
        )

    def bench_compare(
        self,
        before: str | os.PathLike[str],
        after: str | os.PathLike[str],
    ) -> dict[str, Any]:
        """Compare two saved snapshots and return the report ``{path, rows}``."""
        before_path = _path_argument("before", before)
        after_path = _path_argument("after", after)
        return self._read_json(
            ("--json", "bench", "compare", before_path, after_path),
            _bench_compare_payload,
        )

    def bench_list(self) -> list[str]:
        """Return the saved snapshot paths, newest first."""
        return self._read_json(
            ("--json", "bench", "list"),
            _bench_list_payload,
        )

    def backup(self) -> CliResult:
        return self.run(("backup",))

    def disable(self, packages: Sequence[str]) -> CliResult:
        batch = tuple(packages)
        if len(batch) > 5:
            raise ValueError("disable accepts at most five packages per call")
        if any(not isinstance(package, str) or not package.strip() for package in batch):
            raise ValueError("package ids must be non-empty strings")
        return self.run(("disable", *batch))

    def restore_dry_run(self) -> CliResult:
        return self.run(("restore", "--dry-run"))

    def restore(self) -> CliResult:
        return self.run(("restore",))

    def restore_from_backup(self, backup: Path, yes: bool = True) -> CliResult:
        args = ["restore", "--from-backup", str(Path(backup))]
        if yes:
            args.append("--yes")
        return self.run(tuple(args))

    def version(self) -> str:
        result = self.run(("--version",))
        if result.returncode != 0:
            raise CliError(
                _message(
                    ("--version",),
                    f"exited with {result.returncode}",
                    result.stderr,
                )
            )
        version = result.stdout.strip()
        if not version:
            raise CliProtocolError(
                _message(("--version",), "returned no version", result.stderr)
            )
        return version
