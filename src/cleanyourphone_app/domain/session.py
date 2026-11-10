"""The guided session, kept pure so every screen shares the same safety rules.

A session pins the exact serial and transport used to connect. The app never
offers a USB/Wi-Fi switch mid-session because the CLI keys backups and its undo
journal by serial, and a wireless port can change after a reconnect. Apply is
only allowed after a backup, a profile and a non-empty package selection have
all been recorded.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from .models import ProbeData
from .support import SupportedDecision


class Transport(StrEnum):
    """How the phone is attached; one transport per session."""

    USB = "usb"
    WIFI = "wifi"


class SessionState(StrEnum):
    """The steps of the guided flow, in order, plus the two exits."""

    WELCOME = "welcome"
    CONNECTING = "connecting"
    CHECKING = "checking"
    BLOCKED = "blocked"
    BACKUP = "backup"
    REVIEW = "review"
    APPLYING = "applying"
    DONE = "done"
    ERROR = "error"


class SessionError(RuntimeError):
    """Base class for session rule violations."""


class TransportLocked(SessionError):
    """Raised when a session tries to change its ADB transport."""


class InvalidTransition(SessionError):
    """Raised when a step is attempted in the wrong state."""


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_backup_path(value: str | Path) -> Path:
    if not isinstance(value, (str, Path)):
        raise TypeError("backup path must be a string or Path")
    if not str(value).strip():
        raise ValueError("backup path must not be empty")
    return Path(value)


def _require_probe(probe: ProbeData) -> ProbeData:
    if not isinstance(probe, ProbeData):
        raise TypeError("probe must be a ProbeData")
    return probe


class SessionController:
    """In-memory state for one guided cleanup session.

    The controller records only facts the user has actually reached: the exact
    serial and transport used, the probe, the chosen profile, the backup path,
    the selection and the number of completed apply batches. It deliberately
    has no Qt, subprocess or filesystem dependencies.
    """

    def __init__(self) -> None:
        self.state = SessionState.WELCOME
        self.serial: str | None = None
        self.transport: Transport | None = None
        self.probe: ProbeData | None = None
        self.profile_id: str | None = None
        self.backup_path: Path | None = None
        self.selected_packages: tuple[str, ...] = ()
        self.completed_batches = 0
        self.blocked_reason: str | None = None
        self.blocked_link: str | None = None
        self.error_message: str | None = None

    def _require_state(self, *allowed: SessionState, action: str) -> None:
        if self.state in allowed:
            return
        expected = ", ".join(state.value for state in allowed)
        raise InvalidTransition(
            f"cannot {action} while the session is {self.state.value!r}; "
            f"expected {expected}"
        )

    def start(self) -> None:
        """Leave the welcome screen and wait for a connection."""
        self._require_state(SessionState.WELCOME, action="start")
        self.state = SessionState.CONNECTING

    def _require_transport(self, transport: Transport) -> Transport:
        if not isinstance(transport, Transport):
            raise TypeError("transport must be a Transport")
        if self.serial is not None and transport is not self.transport:
            current = self.transport.value if self.transport is not None else "unknown"
            raise TransportLocked(
                f"this session is already using {current}; "
                "start a new session to change transport"
            )
        return transport

    def set_transport(self, transport: Transport) -> Transport:
        """Choose the transport, or confirm the one already pinned."""
        self.transport = self._require_transport(transport)
        return transport

    def attach(self, serial: str, transport: Transport) -> None:
        """Pin the device found by the connection page before it is probed.

        The probe is only available once the check page runs, so pairing and
        the one-device shortcut record the exact serial and transport here and
        leave the session in ``CONNECTING``. :meth:`connected` completes the
        record with the probe and moves the session to ``CHECKING``.
        """
        self._require_state(
            SessionState.WELCOME,
            SessionState.CONNECTING,
            action="attach a device",
        )
        checked_serial = _require_text(serial, "serial")
        checked_transport = self._require_transport(transport)

        if self.serial is not None and checked_serial != self.serial:
            self.probe = None
            self.profile_id = None
        self.serial = checked_serial
        self.transport = checked_transport
        self.blocked_reason = None
        self.blocked_link = None
        self.error_message = None
        self.state = SessionState.CONNECTING

    def connected(
        self,
        serial: str,
        transport: Transport,
        probe: ProbeData,
        profile_id: str | None = None,
    ) -> None:
        """Record the exact device the rest of the session will talk to."""
        self._require_state(
            SessionState.WELCOME,
            SessionState.CONNECTING,
            SessionState.CHECKING,
            action="connect",
        )
        checked_serial = _require_text(serial, "serial")
        checked_probe = _require_probe(probe)
        checked_profile = (
            _require_text(profile_id, "profile id") if profile_id is not None else None
        )
        checked_transport = self._require_transport(transport)

        self.transport = checked_transport
        self.serial = checked_serial
        self.probe = checked_probe
        self.profile_id = checked_profile
        self.blocked_reason = None
        self.blocked_link = None
        self.error_message = None
        self.state = SessionState.CHECKING

    def checked(
        self, probe: ProbeData | None = None, profile_id: str | None = None
    ) -> None:
        """Record a passed support check and move on to creating a backup."""
        self._require_state(
            SessionState.CHECKING,
            SessionState.BACKUP,
            action="record a passed check",
        )
        checked_probe = self.probe if probe is None else _require_probe(probe)
        checked_profile = (
            self.profile_id
            if profile_id is None
            else _require_text(profile_id, "profile id")
        )
        if not isinstance(checked_probe, ProbeData):
            raise InvalidTransition("cannot pass the check before probing the device")

        self.probe = checked_probe
        self.profile_id = checked_profile
        self.state = SessionState.BACKUP

    def begin_backup(self) -> None:
        """Enter the backup step without changing the recorded device."""
        self._require_state(
            SessionState.CHECKING,
            SessionState.BACKUP,
            action="start the backup",
        )
        if not isinstance(self.probe, ProbeData):
            raise InvalidTransition("cannot back up before probing the device")
        self.state = SessionState.BACKUP

    def blocked(self, decision: SupportedDecision) -> None:
        """Stop the session and keep the reason the device is not supported."""
        if not isinstance(decision, SupportedDecision):
            raise TypeError("decision must be a SupportedDecision")
        if decision.allowed:
            raise ValueError("only a denied support decision can block a session")
        self._require_state(
            SessionState.WELCOME,
            SessionState.CONNECTING,
            SessionState.CHECKING,
            action="block the session",
        )
        self.blocked_reason = decision.reason
        self.blocked_link = decision.link
        self.state = SessionState.BLOCKED

    def reset(self) -> None:
        """Clear a blocked session so the user can connect another phone.

        ``BLOCKED`` is the only terminal stop the user can leave from the UI.
        Resetting starts a genuinely new session: no serial, transport, probe,
        profile, backup, selection, progress or blocked reason survives.
        """
        self._require_state(SessionState.BLOCKED, action="start a new session")
        self.serial = None
        self.transport = None
        self.probe = None
        self.profile_id = None
        self.backup_path = None
        self.selected_packages = ()
        self.completed_batches = 0
        self.blocked_reason = None
        self.blocked_link = None
        self.error_message = None
        self.state = SessionState.WELCOME

    def backup_done(self, path: str | Path) -> None:
        """Record the verified backup folder created in this session."""
        self._require_state(
            SessionState.CHECKING,
            SessionState.BACKUP,
            action="record the backup",
        )
        if not isinstance(self.probe, ProbeData):
            raise InvalidTransition("cannot record a backup before probing the device")
        checked_path = _require_backup_path(path)

        self.backup_path = checked_path
        self.error_message = None
        self.state = SessionState.REVIEW

    def set_selection(self, packages: Iterable[str]) -> tuple[str, ...]:
        """Store the exact packages the user chose, without duplicates."""
        self._require_state(
            SessionState.BACKUP,
            SessionState.REVIEW,
            action="choose packages",
        )
        if isinstance(packages, (str, bytes)):
            raise TypeError("selection must be a collection of package ids")

        selected: list[str] = []
        seen: set[str] = set()
        for package in packages:
            if not isinstance(package, str) or not package.strip():
                raise ValueError("package ids must be non-empty strings")
            if package in seen:
                continue
            seen.add(package)
            selected.append(package)
        self.selected_packages = tuple(selected)
        return self.selected_packages

    def can_apply(self) -> bool:
        """Apply needs a review, a backup, a profile and at least one package."""
        return (
            self.state is SessionState.REVIEW
            and self.backup_path is not None
            and isinstance(self.probe, ProbeData)
            and bool(self.profile_id)
            and bool(self.selected_packages)
        )

    def can_undo(self) -> bool:
        """Undo needs the exact serial and a backup from this session."""
        return bool(self.serial) and self.backup_path is not None

    def start_apply(self) -> None:
        """Lock in the reviewed selection and begin the apply batches."""
        if not self.can_apply():
            raise InvalidTransition(
                "cannot apply before a review with a backup, a profile and a selection"
            )
        self.completed_batches = 0
        self.state = SessionState.APPLYING

    def batch_done(self) -> int:
        """Record one verified batch and return the new progress count."""
        self._require_state(SessionState.APPLYING, action="record a batch")
        self.completed_batches += 1
        return self.completed_batches

    def finish(self) -> None:
        """Mark the session complete after the last batch."""
        self._require_state(SessionState.APPLYING, action="finish")
        self.state = SessionState.DONE

    def fail(self, message: str) -> None:
        """Stop the session with a user-facing error message."""
        message = _require_text(message, "error message")
        self._require_state(
            SessionState.WELCOME,
            SessionState.CONNECTING,
            SessionState.CHECKING,
            SessionState.BLOCKED,
            SessionState.BACKUP,
            SessionState.REVIEW,
            SessionState.APPLYING,
            SessionState.ERROR,
            action="fail",
        )
        self.error_message = message
        self.state = SessionState.ERROR
