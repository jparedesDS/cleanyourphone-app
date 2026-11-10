"""Pair and connect an Android 11+ phone over Wi-Fi with ADB.

Android 11+ publishes two mDNS services while Wireless debugging is on: a
pairing service (``_adb-tls-pairing._tcp``) and a connect service
(``_adb-tls-connect._tcp``). The user reads the six-digit pairing code from the
phone's Wireless debugging screen; this module passes that code to ``adb pair``
and never logs it or repeats it in an error message.

ADB is never bundled. The connector only executes the binary inside an
:class:`~cleanyourphone_app.services.adb.AdbInfo` produced by
:class:`~cleanyourphone_app.services.adb.AdbLocator`, so an unverified or
outdated adb can never run.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cleanyourphone_app.services.adb import (
    MIN_ADB_VERSION,
    AdbInfo,
    parse_devices,
)

_PAIRING_SERVICE = "_adb-tls-pairing._tcp"
_CONNECT_SERVICE = "_adb-tls-connect._tcp"
_CODE_PATTERN = re.compile(r"[0-9]{6}\Z")
_CODE_PLACEHOLDER = "<pairing-code>"
_FAILURE_MARKERS = ("failed", "cannot", "unable", "error", "refused")

_MDNS_TIMEOUT = 15
_PAIR_TIMEOUT = 60
_CONNECT_TIMEOUT = 30
_DEVICES_TIMEOUT = 30
_STDERR_TAIL = 500
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class MdnsService:
    """One host and port advertised by the phone over mDNS."""

    host: str
    port: int

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass(frozen=True)
class MdnsServices:
    """The endpoints found by ``adb mdns services``.

    Either endpoint can be missing: the pairing service only exists while the
    Wireless debugging pairing dialog is open, and the connect service only
    exists after pairing has succeeded.
    """

    pairing: MdnsService | None = None
    connect: MdnsService | None = None


class WifiError(RuntimeError):
    """Wireless pairing or connecting failed in a way the user can retry."""


def _tail(text: str, limit: int = _STDERR_TAIL) -> str:
    text = text.strip()
    if not text:
        return "(empty)"
    if len(text) <= limit:
        return text
    return "..." + text[-limit:]


def _redact(text: str, secret: str | None) -> str:
    """Remove the pairing code from text that may reach the UI or a log."""
    if secret and secret in text:
        return text.replace(secret, _CODE_PLACEHOLDER)
    return text


def _detail(completed: subprocess.CompletedProcess[str]) -> str:
    parts: list[str] = []
    if (completed.stdout or "").strip():
        parts.append(f"stdout: {_tail(completed.stdout)}")
    if (completed.stderr or "").strip():
        parts.append(f"stderr: {_tail(completed.stderr)}")
    return "; ".join(parts) if parts else "no output"


def _parse_endpoint(token: str) -> MdnsService | None:
    host, separator, port_text = token.rpartition(":")
    if not separator or not host or not port_text:
        return None
    if not port_text.isdigit():
        return None
    port = int(port_text)
    if not 1 <= port <= 65535:
        return None
    return MdnsService(host=host, port=port)


def parse_mdns_services(output: str) -> MdnsServices:
    """Parse ``adb mdns services`` into the endpoints the app needs.

    Headers, daemon banners, error lines and malformed rows are ignored. When
    the phone advertises more than one endpoint of a kind, the last valid row
    wins because adb prints the freshest discovery last.
    """
    if not isinstance(output, str):
        raise ValueError("adb mdns services output must be text")

    pairing: MdnsService | None = None
    connect: MdnsService | None = None

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue

        kind: str | None = None
        for token in parts[:-1]:
            normalized = token.lower().rstrip(".")
            if normalized == _PAIRING_SERVICE:
                kind = "pairing"
                break
            if normalized == _CONNECT_SERVICE:
                kind = "connect"
                break
        if kind is None:
            continue

        endpoint = _parse_endpoint(parts[-1])
        if endpoint is None:
            continue
        if kind == "pairing":
            pairing = endpoint
        else:
            connect = endpoint

    return MdnsServices(pairing=pairing, connect=connect)


class WifiConnector:
    """Pair with and connect to an Android 11+ phone over the local network.

    Only an :class:`AdbInfo` returned by ``AdbLocator.find()`` is accepted so
    a raw or outdated path can never execute. The six-digit code is validated
    before any process starts and is redacted from every error message.
    """

    def __init__(self, adb: AdbInfo, runner: Runner | None = None) -> None:
        if not isinstance(adb, AdbInfo):
            raise TypeError(
                "WifiConnector requires an AdbInfo from AdbLocator.find(), "
                f"not {type(adb).__name__}"
            )
        if adb.version < MIN_ADB_VERSION:
            raise ValueError(
                f"adb {adb.version} is older than the minimum {MIN_ADB_VERSION}"
            )
        self._adb = adb
        self._runner: Runner = runner or subprocess.run

    @property
    def adb(self) -> AdbInfo:
        return self._adb

    def _run(
        self,
        args: Sequence[str],
        timeout: int,
        secret: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        argv = [str(self._adb.path), *args]
        shown = [_redact(part, secret) for part in argv]
        try:
            return self._runner(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            message = (
                f"`{' '.join(shown)}` timed out after {timeout} seconds. "
                "On the phone, keep the Wireless debugging screen open, then "
                "try again; you can also connect with a USB cable instead."
            )
            if secret is None:
                raise WifiError(message) from exc
            raise WifiError(message) from None
        except (OSError, subprocess.SubprocessError) as exc:
            message = _redact(
                f"could not run `{' '.join(shown)}`: {exc}. Make sure Android "
                "Platform-Tools are installed, then try again; you can also "
                "connect with a USB cable instead.",
                secret,
            )
            if secret is None:
                raise WifiError(message) from exc
            raise WifiError(message) from None

    def discover(self) -> MdnsServices:
        """Run ``adb mdns services`` and return the advertised endpoints."""
        completed = self._run(("mdns", "services"), _MDNS_TIMEOUT)
        if completed.returncode != 0:
            raise WifiError(
                "ADB could not discover wireless debugging services. On the "
                "phone, open Developer options > Wireless debugging and turn "
                "it on, keep the phone and PC on the same Wi-Fi network, then "
                "try again; you can also connect with a USB cable instead. "
                f"`adb mdns services` exited with {completed.returncode}; "
                f"{_detail(completed)}"
            )
        return parse_mdns_services(completed.stdout or "")

    def pair_and_connect(
        self,
        code: str,
        pairing: MdnsService,
        connect: MdnsService,
    ) -> str:
        """Pair with the phone, connect, and return the single device serial."""
        if not isinstance(code, str) or _CODE_PATTERN.fullmatch(code) is None:
            raise ValueError("the pairing code must be exactly six digits")
        if not isinstance(pairing, MdnsService) or not isinstance(connect, MdnsService):
            raise TypeError("pairing and connect must be MdnsService values")

        self._pair(pairing, code)
        self._connect(connect)
        return self._connected_serial(connect)

    def _pair(self, pairing: MdnsService, code: str) -> None:
        completed = self._run(
            ("pair", str(pairing), code),
            _PAIR_TIMEOUT,
            secret=code,
        )
        detail = _redact(_detail(completed), code)
        output = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
        failed = any(marker in output for marker in _FAILURE_MARKERS)
        if completed.returncode != 0 or failed:
            raise WifiError(
                "Pairing failed. On the phone, open Developer options > "
                "Wireless debugging, check that the pairing code shown there "
                "matches the one you entered, and make sure the phone and PC "
                "are on the same Wi-Fi network, then try again. You can also "
                "connect with a USB cable instead. `adb pair` exited with "
                f"{completed.returncode}; {detail}"
            )

    def _connect(self, connect: MdnsService) -> None:
        completed = self._run(("connect", str(connect)), _CONNECT_TIMEOUT)
        output = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
        failed = any(marker in output for marker in _FAILURE_MARKERS)
        if completed.returncode != 0 or failed:
            raise WifiError(
                "ADB could not connect to the phone over Wi-Fi. Make sure the "
                "phone and PC are on the same Wi-Fi network and that Wireless "
                "debugging is still on, then try again; you can also connect "
                "with a USB cable instead. `adb connect` exited with "
                f"{completed.returncode}; {_detail(completed)}"
            )

    def _connected_serial(self, connect: MdnsService) -> str:
        completed = self._run(("devices", "-l"), _DEVICES_TIMEOUT)
        if completed.returncode != 0:
            raise WifiError(
                "ADB connected to the phone but could not list devices. On the "
                "phone, check that Wireless debugging is still on, then try "
                "again; you can also connect with a USB cable instead. "
                f"`adb devices -l` exited with {completed.returncode}; "
                f"{_detail(completed)}"
            )

        usable = [
            device
            for device in parse_devices(completed.stdout or "")
            if device.state == "device"
        ]
        if not usable:
            raise WifiError(
                "ADB paired and tried to connect, but the phone did not appear "
                "as an online device. On the phone, keep the Wireless debugging "
                "screen open and approve any prompt, then try again; you can "
                "also connect with a USB cable instead."
            )

        exact = [device for device in usable if device.serial == str(connect)]
        if exact:
            return exact[0].serial

        wifi = [device for device in usable if device.transport == "wifi"]
        if len(wifi) == 1:
            return wifi[0].serial
        if len(usable) == 1:
            return usable[0].serial

        raise WifiError(
            "ADB paired and tried to connect, but expected exactly one "
            f"connected device and found {len(usable)}. Disconnect other "
            "phones or emulators, then try again; you can also connect with a "
            "USB cable instead."
        )
