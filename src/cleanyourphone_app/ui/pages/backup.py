"""Create and verify the backup that unlocks Review.

The CLI writes one folder per run under ``~/.cleanyourphone/backup``. The page
never trusts the command's exit code alone: it looks up the newest folder whose
``meta.json`` matches the pinned serial and fingerprint. A missing match is a
hard stop, and there is deliberately no skip control.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.domain.session import SessionError
from cleanyourphone_app.services.backup import BackupStore
from cleanyourphone_app.services.logging import LOGGER_NAME
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.services.cli import CliClient
    from cleanyourphone_app.ui.app import AppContext


def default_backup_root() -> Path:
    """The folder the CLI client pins through ``CLEANYOURPHONE_BACKUP``."""
    return Path.home() / ".cleanyourphone" / "backup"


def _result_ok(result: object) -> bool:
    returncode = getattr(result, "returncode", None)
    if isinstance(returncode, int) and not isinstance(returncode, bool):
        return returncode == 0
    return bool(getattr(result, "ok", False))


class BackupPage(Page):
    """Run ``backup`` and only continue when the exact backup is on disk."""

    def __init__(
        self,
        context: AppContext,
        cli: CliClient | None = None,
        parent: QWidget | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        # A Path passed in the parent position is accepted as the backup root;
        # this keeps page construction convenient in focused tests.
        if root is None and isinstance(parent, Path):
            root = parent
            parent = None
        super().__init__(context, parent)
        self._cli = cli if cli is not None else context.cli
        self._root = Path(root) if root is not None else default_backup_root()
        self.root = self._root
        self._busy = False
        self._has_run = False
        self._completed = False
        self._error_key: str | None = None
        self.backup_path: Path | None = None
        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._backup_succeeded)
        self._call.failed.connect(self._backup_failed)
        self._call.finished.connect(self._backup_finished)
        self._build_ui()
        self.retranslate()

    @property
    def busy(self) -> bool:
        return self._busy

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 44)
        layout.setSpacing(14)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.no_skip_label = QLabel(self)
        self.no_skip_label.setProperty("role", "muted")
        self.no_skip_label.setWordWrap(True)

        self.busy_label = QLabel(self)
        self.busy_label.setProperty("role", "muted")
        self.busy_label.setWordWrap(True)
        self.busy_label.hide()

        self.done_label = QLabel(self)
        self.done_label.setProperty("role", "success")
        self.done_label.setWordWrap(True)
        self.done_label.hide()

        self.path_caption = QLabel(self)
        self.path_caption.setProperty("role", "muted")
        self.path_caption.hide()

        self.path_label = QLabel(self)
        self.path_label.setProperty("role", "body")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.path_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.retry_button = QPushButton(self)
        self.retry_button.setObjectName("backup_retry_button")
        self.retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_button.clicked.connect(lambda checked=False: self.run())
        self.retry_button.hide()

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self.retry_button)
        actions.addStretch(1)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.no_skip_label)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.done_label)
        layout.addWidget(self.path_caption)
        layout.addWidget(self.path_label)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)
        layout.addStretch(1)

    # ---------------------------------------------------------------- actions

    def run(self) -> None:
        """Start the backup worker, unless one is active or already done."""
        if self._completed or self._busy or self._call.active:
            return

        serial = self.context.session.serial
        probe = self.context.session.probe
        if (
            not isinstance(serial, str)
            or not serial.strip()
            or not isinstance(probe, ProbeData)
            or not probe.fingerprint.strip()
        ):
            self._has_run = True
            self._show_error("backup.failed")
            return

        self._has_run = True
        self._set_busy(True)
        fingerprint = probe.fingerprint
        root = self._root
        cli = self._cli

        def call() -> tuple[object, Path | None]:
            result = cli.backup()
            if not _result_ok(result):
                return result, None
            return result, BackupStore.latest(serial, fingerprint, root)

        if not self._call.start(call):
            self._set_busy(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._has_run and not self._completed:
            self.run()

    def shutdown(self) -> None:
        """Wait briefly for the backup worker when the window is closing."""
        self._call.shutdown(5000)

    def reset(self) -> None:
        """Return to a pristine page for a new session."""
        self._call.shutdown(5000)
        self._busy = False
        self._has_run = False
        self._completed = False
        self.backup_path = None
        self.next_page = None
        self._clear_error()
        self.busy_label.hide()
        self.done_label.hide()
        self.path_caption.hide()
        self.path_label.clear()
        self.path_label.hide()
        self.retry_button.hide()

    def _backup_succeeded(self, payload: object) -> None:
        result, folder = payload if isinstance(payload, tuple) else (None, None)
        if not _result_ok(result) or not isinstance(folder, Path):
            self._show_error("backup.failed")
            return

        try:
            self.context.session.backup_done(folder)
        except (SessionError, ValueError, TypeError):
            self._show_error("backup.failed")
            return

        self.backup_path = folder
        self._completed = True
        self._clear_error()
        self.done_label.setText(self.tr("backup.done"))
        self.done_label.show()
        self.path_caption.show()
        self.path_label.setText(str(folder))
        self.path_label.show()
        self._go("review")

    def _backup_failed(self, error: object) -> None:
        logging.getLogger(LOGGER_NAME).warning(
            "backup failed: %s", type(error).__name__
        )
        self._show_error("backup.failed")

    def _backup_finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._clear_error()
            self.done_label.hide()
            self.path_caption.hide()
            self.path_label.hide()
            self.busy_label.setText(self.tr("backup.running"))
            self.busy_label.show()
            self.retry_button.hide()
        else:
            self.busy_label.hide()
        self.retry_button.setEnabled(not busy)

    def _show_error(self, key: str) -> None:
        self._error_key = key
        self.error_label.setText(self.tr(key))
        self.error_label.show()
        self.retry_button.show()
        self.retry_button.setEnabled(not self._busy)

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()
        if not self._busy:
            self.retry_button.hide()

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("backup.title"))
        self.body_label.setText(self.tr("backup.body"))
        self.no_skip_label.setText(self.tr("backup.no_skip"))
        self.busy_label.setText(self.tr("backup.running"))
        self.done_label.setText(self.tr("backup.done"))
        self.path_caption.setText(self.tr("backup.path"))
        self.retry_button.setText(self.tr("backup.retry"))
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.no_skip_label.setAccessibleName(self.no_skip_label.text())
        self.busy_label.setAccessibleName(self.busy_label.text())
        self.path_caption.setAccessibleName(self.path_caption.text())
        self.path_label.setAccessibleName(self.path_caption.text())
        self.retry_button.setAccessibleName(self.retry_button.text())


__all__ = ["BackupPage", "default_backup_root"]
