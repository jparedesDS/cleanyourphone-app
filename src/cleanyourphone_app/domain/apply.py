"""Apply a reviewed selection in verified batches, and keep undo honest.

The CLI owns every write. This controller only sequences the calls: it re-runs
the plan before each batch so a package that stopped being actionable is never
sent to ``disable``, verifies the phone after every successful batch, and on a
failure reports the packages that are still disabled instead of claiming the
phone is unchanged. Undo always previews with ``restore --dry-run`` first and
never retries a failed restore on its own.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .batches import split_batches
from .review import SELECTABLE_ACTIONS

LOGGER_NAME = "cleanyourphone_app"


@dataclass(frozen=True)
class ApplyResult:
    """The outcome of one apply run, including the phone's real state."""

    completed: bool
    failed_batch: tuple[str, ...] | None = None
    remaining_disabled: tuple[str, ...] = ()
    rollback_verified: bool = False
    verify: dict = field(default_factory=dict)
    fallback_backup: Path | None = None


@dataclass(frozen=True)
class ApplyProgress:
    """One progress event, emitted from the apply worker thread."""

    batch_index: int
    total_batches: int
    batch: tuple[str, ...]
    completed: tuple[str, ...]
    phase: str


@dataclass(frozen=True)
class ApplySummary:
    """What the Done page needs: the result and the packages really touched."""

    result: ApplyResult
    applied: tuple[str, ...]
    selected: tuple[str, ...]
    stopped: bool = False


@dataclass(frozen=True)
class UndoResult:
    """The outcome of an undo or an explicit restore-from-backup fallback."""

    restored: bool
    dry_run: str = ""
    fallback_backup: Path | None = None
    dry_run_failed: bool = False
    used_backup: bool = False


def _selection(selected: Iterable[str]) -> tuple[str, ...]:
    if isinstance(selected, (str, bytes)):
        raise TypeError("selection must be a collection of package ids")
    packages: list[str] = []
    seen: set[str] = set()
    for package in selected:
        if not isinstance(package, str) or not package.strip():
            raise ValueError("package ids must be non-empty strings")
        if package in seen:
            continue
        seen.add(package)
        packages.append(package)
    if not packages:
        raise ValueError("selection must contain at least one package")
    return tuple(packages)


def _action(row: object) -> str:
    return str(getattr(row, "action", "")).strip().upper()


def _package(row: object) -> str:
    return str(getattr(row, "package", ""))


def _checks_pass(verify: dict) -> bool:
    checks = verify.get("checks") if isinstance(verify, dict) else None
    if not isinstance(checks, list) or not checks:
        return False
    return all(
        isinstance(check, dict)
        and str(check.get("status", "")).strip().upper() == "PASS"
        for check in checks
    )


def _result_ok(result: object) -> bool:
    return bool(getattr(result, "ok", False))


class ApplyController:
    """Sequence CLI apply batches and the two-step undo path."""

    def __init__(
        self,
        cli,
        backup: Path | None = None,
        *,
        batch_size: int = 5,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch size must be at least 1")
        self._cli = cli
        self._backup = Path(backup) if backup is not None else None
        self._batch_size = batch_size

    @property
    def backup(self) -> Path | None:
        return self._backup

    # ------------------------------------------------------------------ apply

    def run(
        self,
        selected: Sequence[str],
        profile_id: str,
        on_progress: Callable[[ApplyProgress], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> ApplyResult:
        """Disable *selected* in batches, re-planning and verifying each one."""
        packages = _selection(selected)
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")

        batches = split_batches(packages, self._batch_size)
        total = len(batches)
        applied: list[str] = []
        last_verify: dict = {}
        skipped_any = False

        for index, original in enumerate(batches, start=1):
            if should_stop is not None and should_stop():
                self._emit(
                    on_progress,
                    ApplyProgress(
                        index, total, tuple(original), tuple(applied), "stopped"
                    ),
                )
                return self._partial_result(
                    packages, last_verify, failed_batch=None
                )

            try:
                new_plan = self._cli.plan(profile_id)
            except Exception as error:  # noqa: BLE001 - the batch must stop
                logging.getLogger(LOGGER_NAME).warning(
                    "apply plan refresh failed: %s", type(error).__name__
                )
                return self._failure_result(packages, original, attempted=False)

            actionable = {
                _package(row)
                for row in getattr(new_plan, "rows", ())
                if _action(row) in SELECTABLE_ACTIONS
            }
            batch = tuple(package for package in original if package in actionable)
            if not batch:
                skipped_any = True
                self._emit(
                    on_progress,
                    ApplyProgress(
                        index, total, tuple(original), tuple(applied), "skipped"
                    ),
                )
                continue

            self._emit(
                on_progress,
                ApplyProgress(index, total, batch, tuple(applied), "started"),
            )

            try:
                disable_result = self._cli.disable(batch)
            except Exception as error:  # noqa: BLE001 - inspect the phone first
                logging.getLogger(LOGGER_NAME).warning(
                    "apply disable failed: %s", type(error).__name__
                )
                return self._failure_result(packages, batch, attempted=True)

            if not _result_ok(disable_result):
                return self._failure_result(packages, batch, attempted=True)

            try:
                verify = self._verify()
            except Exception as error:  # noqa: BLE001 - unverified is not success
                logging.getLogger(LOGGER_NAME).warning(
                    "apply verify failed: %s", type(error).__name__
                )
                return self._failure_result(packages, batch, attempted=True)

            if not _checks_pass(verify):
                return ApplyResult(
                    completed=False,
                    failed_batch=batch,
                    remaining_disabled=self._remaining(packages),
                    rollback_verified=False,
                    verify=verify,
                )

            applied.extend(batch)
            last_verify = verify
            self._emit(
                on_progress,
                ApplyProgress(index, total, batch, tuple(applied), "done"),
            )

        if skipped_any:
            return self._partial_result(
                packages, last_verify, failed_batch=None
            )

        if not last_verify:
            last_verify = self._safe_verify()

        return ApplyResult(
            completed=True,
            failed_batch=None,
            remaining_disabled=(),
            rollback_verified=False,
            verify=last_verify,
        )

    # ------------------------------------------------------------------- undo

    def preview_undo(self):
        """Run the non-destructive ``restore --dry-run`` step."""
        return self._cli.restore_dry_run()

    def undo(self) -> UndoResult:
        """Preview, then restore; a failed restore is reported, never retried."""
        dry_run = self._cli.restore_dry_run()
        if not _result_ok(dry_run):
            return UndoResult(
                restored=False,
                dry_run=str(getattr(dry_run, "stdout", "") or ""),
                fallback_backup=self._backup,
                dry_run_failed=True,
            )

        restored = self._cli.restore()
        if not _result_ok(restored):
            return UndoResult(
                restored=False,
                dry_run=str(getattr(dry_run, "stdout", "") or ""),
                fallback_backup=self._backup,
            )

        return UndoResult(
            restored=True,
            dry_run=str(getattr(dry_run, "stdout", "") or ""),
        )

    def restore_from_backup(self) -> UndoResult:
        """Explicit fallback: rebuild the phone from the session backup."""
        if self._backup is None:
            raise ValueError("no backup path is available for this session")
        result = self._cli.restore_from_backup(self._backup, yes=True)
        if not _result_ok(result):
            return UndoResult(
                restored=False,
                fallback_backup=self._backup,
                used_backup=True,
            )
        return UndoResult(restored=True, used_backup=True)

    # ---------------------------------------------------------------- helpers

    def _verify(self) -> dict:
        payload = self._cli.verify()
        if not isinstance(payload, dict):
            raise TypeError("verify must return a dict")
        checks = payload.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError("verify returned no checks")
        return payload

    def _safe_verify(self) -> dict:
        try:
            return self._verify()
        except Exception:  # noqa: BLE001 - failure copy must stay honest
            return {}

    def _read_disabled(self) -> set[str] | None:
        try:
            return set(self._cli.list_disabled())
        except Exception:  # noqa: BLE001 - unknown is not "nothing disabled"
            return None

    def _remaining(self, selected: tuple[str, ...]) -> tuple[str, ...]:
        disabled = self._read_disabled()
        if disabled is None:
            return ()
        return tuple(sorted(set(selected) & disabled))

    def _failure_result(
        self,
        selected: tuple[str, ...],
        batch: Sequence[str],
        *,
        attempted: bool,
    ) -> ApplyResult:
        disabled = self._read_disabled()
        remaining = (
            tuple(sorted(set(selected) & disabled)) if disabled is not None else ()
        )
        verify = self._safe_verify()
        rollback_verified = (
            attempted
            and disabled is not None
            and not remaining
            and _checks_pass(verify)
        )
        return ApplyResult(
            completed=False,
            failed_batch=tuple(batch),
            remaining_disabled=remaining,
            rollback_verified=rollback_verified,
            verify=verify,
        )

    def _partial_result(
        self,
        selected: tuple[str, ...],
        last_verify: dict,
        *,
        failed_batch: tuple[str, ...] | None,
    ) -> ApplyResult:
        verify = last_verify or self._safe_verify()
        return ApplyResult(
            completed=False,
            failed_batch=failed_batch,
            remaining_disabled=self._remaining(selected),
            rollback_verified=False,
            verify=verify,
        )

    @staticmethod
    def _emit(
        callback: Callable[[ApplyProgress], None] | None,
        progress: ApplyProgress,
    ) -> None:
        if callback is None:
            return
        try:
            callback(progress)
        except Exception:  # noqa: BLE001 - progress must never abort a write
            logging.getLogger(LOGGER_NAME).warning(
                "apply progress callback failed: %s", "callback error"
            )


__all__ = [
    "ApplyController",
    "ApplyProgress",
    "ApplyResult",
    "ApplySummary",
    "UndoResult",
]
