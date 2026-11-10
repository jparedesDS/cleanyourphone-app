"""The result screen and the single undo path.

Done always tells the truth about what happened: the applied count, the backup
path and, after a failure, the packages that are still disabled. Undo asks for
confirmation only after showing the ``restore --dry-run`` summary. If the
journal restore fails, the page offers the backup fallback explicitly, with a
warning that it reconstructs state from the backup instead of the journal, and
never retries by itself.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.apply import (
    ApplyController,
    ApplyResult,
    ApplySummary,
    UndoResult,
)
from cleanyourphone_app.services.logging import LOGGER_NAME
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.services.cli import CliClient
    from cleanyourphone_app.ui.app import AppContext


def _result_ok(result: object) -> bool:
    return bool(getattr(result, "ok", False))


class DonePage(Page):
    """Summary, confirmation and the explicit backup fallback."""

    def __init__(
        self,
        context: AppContext,
        cli: CliClient | None = None,
        controller: object | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(context, parent)
        self._cli = cli if cli is not None else context.cli
        self._controller = controller
        self._busy = False
        self._mode = ""
        self._error_key: str | None = None
        self._undo_done = False
        self._undo_status_key = "done.undone"
        self.summary: ApplySummary | None = None

        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._worker_succeeded)
        self._call.failed.connect(self._worker_failed)
        self._call.finished.connect(self._worker_finished)
        self._build_ui()
        self.retranslate()

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def close_blocked(self) -> bool:
        return self._busy or self._call.active

    @property
    def backup(self) -> Path | None:
        path = self.context.session.backup_path
        return path if isinstance(path, Path) else None

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 44)
        layout.setSpacing(12)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.count_label = QLabel(self)
        self.count_label.setObjectName("done_count_label")
        self.count_label.setProperty("role", "brand")
        self.count_label.setWordWrap(True)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("done_status_label")
        self.status_label.setProperty("role", "success")
        self.status_label.setWordWrap(True)
        self.status_label.hide()

        self.summary_warning_label = QLabel(self)
        self.summary_warning_label.setObjectName("done_summary_warning")
        self.summary_warning_label.setProperty("role", "error")
        self.summary_warning_label.setWordWrap(True)
        self.summary_warning_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setObjectName("done_error_label")
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.remaining_caption = QLabel(self)
        self.remaining_caption.setProperty("role", "muted")
        self.remaining_caption.setWordWrap(True)
        self.remaining_caption.hide()

        self.remaining_label = QLabel(self)
        self.remaining_label.setObjectName("done_remaining_label")
        self.remaining_label.setProperty("role", "error")
        self.remaining_label.setWordWrap(True)
        self.remaining_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.remaining_label.hide()

        self.verified_label = QLabel(self)
        self.verified_label.setProperty("role", "muted")
        self.verified_label.setWordWrap(True)

        self.backup_caption = QLabel(self)
        self.backup_caption.setProperty("role", "muted")

        self.backup_label = QLabel(self)
        self.backup_label.setObjectName("done_backup_label")
        self.backup_label.setProperty("role", "package-id")
        self.backup_label.setWordWrap(True)
        self.backup_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.undo_button = QPushButton(self)
        self.undo_button.setObjectName("done_undo_button")
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self._start_preview)

        self.confirm_panel = QFrame(self)
        self.confirm_panel.setObjectName("UndoConfirm")
        confirm_layout = QVBoxLayout(self.confirm_panel)
        confirm_layout.setContentsMargins(16, 14, 16, 14)
        confirm_layout.setSpacing(8)

        self.confirm_title_label = QLabel(self.confirm_panel)
        self.confirm_title_label.setProperty("role", "brand")
        self.confirm_title_label.setWordWrap(True)

        self.confirm_body_label = QLabel(self.confirm_panel)
        self.confirm_body_label.setObjectName("done_confirm_body")
        self.confirm_body_label.setProperty("role", "body")
        self.confirm_body_label.setWordWrap(True)

        self.dry_run_caption = QLabel(self.confirm_panel)
        self.dry_run_caption.setProperty("role", "muted")

        self.dry_run_output = QLabel(self.confirm_panel)
        self.dry_run_output.setObjectName("done_dry_run_output")
        self.dry_run_output.setProperty("role", "package-id")
        self.dry_run_output.setWordWrap(True)
        self.dry_run_output.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.confirm_button = QPushButton(self.confirm_panel)
        self.confirm_button.setObjectName("done_confirm_button")
        self.confirm_button.setProperty("primary", True)
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.clicked.connect(self._confirm_undo)

        self.cancel_button = QPushButton(self.confirm_panel)
        self.cancel_button.setObjectName("done_cancel_button")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self._cancel_undo)

        confirm_actions = QHBoxLayout()
        confirm_actions.setContentsMargins(0, 0, 0, 0)
        confirm_actions.addStretch(1)
        confirm_actions.addWidget(self.cancel_button)
        confirm_actions.addWidget(self.confirm_button)

        confirm_layout.addWidget(self.confirm_title_label)
        confirm_layout.addWidget(self.confirm_body_label)
        confirm_layout.addWidget(self.dry_run_caption)
        confirm_layout.addWidget(self.dry_run_output)
        confirm_layout.addLayout(confirm_actions)
        self.confirm_panel.hide()

        self.fallback_panel = QFrame(self)
        self.fallback_panel.setObjectName("UndoFallback")
        fallback_layout = QVBoxLayout(self.fallback_panel)
        fallback_layout.setContentsMargins(16, 14, 16, 14)
        fallback_layout.setSpacing(8)

        self.fallback_warning_label = QLabel(self.fallback_panel)
        self.fallback_warning_label.setObjectName("done_fallback_warning")
        self.fallback_warning_label.setProperty("role", "error")
        self.fallback_warning_label.setWordWrap(True)

        self.fallback_button = QPushButton(self.fallback_panel)
        self.fallback_button.setObjectName("done_fallback_button")
        self.fallback_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fallback_button.clicked.connect(self._start_fallback)

        fallback_layout.addWidget(self.fallback_warning_label)
        fallback_layout.addWidget(self.fallback_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.fallback_panel.hide()

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch(1)
        actions.addWidget(self.undo_button)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.count_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.summary_warning_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.remaining_caption)
        layout.addWidget(self.remaining_label)
        layout.addWidget(self.verified_label)
        layout.addWidget(self.backup_caption)
        layout.addWidget(self.backup_label)
        layout.addWidget(self.confirm_panel)
        layout.addWidget(self.fallback_panel)
        layout.addLayout(actions)
        layout.addStretch(1)

    # ---------------------------------------------------------------- summary

    def show_summary(self, summary: ApplySummary) -> None:
        if not isinstance(summary, ApplySummary):
            raise TypeError("summary must be an ApplySummary")
        self.summary = summary
        self.next_page = None
        self._undo_done = False
        self._undo_status_key = "done.undone"
        self._clear_error()
        self.confirm_panel.hide()
        self.fallback_panel.hide()
        self.dry_run_output.clear()
        self._render_summary()
        self._update_actions()

    def _render_summary(self) -> None:
        summary = self.summary
        if summary is None:
            return

        result = summary.result
        self.count_label.setText(
            self.tr("done.count", count=len(summary.applied))
        )
        self.count_label.show()
        self.verified_label.setText(self.tr("done.verified"))
        self.verified_label.setVisible(
            isinstance(result.verify, dict)
            and bool(result.verify.get("checks"))
        )
        self._render_backup()

        if self._undo_done:
            # The present-tense summary no longer describes the phone: undo
            # restored it. Keep only the outcome, never a stale count or a
            # "still disabled" list.
            self.count_label.hide()
            self.verified_label.hide()
            self.summary_warning_label.hide()
            self.status_label.setText(self.tr(self._undo_status_key))
            self.status_label.show()
            self.error_label.hide()
            self.remaining_caption.hide()
            self.remaining_label.hide()
            return

        failed = result.failed_batch is not None
        if result.completed:
            self.status_label.setText(self.tr("apply.complete"))
            self.status_label.show()
            self.summary_warning_label.hide()
            self.error_label.hide()
            self.remaining_caption.hide()
            self.remaining_label.hide()
        elif failed:
            self.status_label.hide()
            self.summary_warning_label.setText(self.tr("done.failed"))
            self.summary_warning_label.show()
            self.error_label.hide()
            self._render_remaining(result)
        else:
            self.status_label.hide()
            self.summary_warning_label.setText(self.tr("apply.plan_changed"))
            self.summary_warning_label.show()
            self.error_label.hide()
            self._render_remaining(result)

        if summary.stopped:
            self.status_label.setText(
                self.tr("done.stopped", count=len(summary.applied))
            )
            self.status_label.show()
            self.summary_warning_label.hide()
            self.error_label.hide()
            self.remaining_caption.hide()
            self.remaining_label.hide()

    def _render_remaining(self, result: ApplyResult) -> None:
        self.remaining_caption.setText(self.tr("done.remaining_caption"))
        self.remaining_caption.show()
        if result.remaining_disabled:
            self.remaining_label.setText(
                self.tr(
                    "apply.remaining_disabled",
                    packages=", ".join(result.remaining_disabled),
                )
            )
        elif result.rollback_verified:
            self.remaining_label.setText(self.tr("apply.rollback_verified"))
        else:
            self.remaining_label.setText(self.tr("apply.state_unknown"))
        self.remaining_label.show()

    def _render_backup(self) -> None:
        path = self.backup
        if path is None:
            self.backup_caption.hide()
            self.backup_label.clear()
            self.backup_label.hide()
            return
        self.backup_caption.setText(self.tr("done.backup_path"))
        self.backup_caption.show()
        self.backup_label.setText(str(path))
        self.backup_label.show()

    # ------------------------------------------------------------------- undo

    def _current_controller(self):
        if self._controller is None:
            self._controller = ApplyController(self._cli, backup=self.backup)
        return self._controller

    def _start_preview(self) -> None:
        if self._busy:
            return
        if self.backup is None:
            self._show_error("done.undo_unavailable")
            return
        self._mode = "preview"
        self._set_busy(True)
        controller = self._current_controller()
        if not self._call.start(controller.preview_undo):
            self._set_busy(False)

    def _confirm_undo(self) -> None:
        if self._busy:
            return
        self.confirm_panel.hide()
        self._mode = "undo"
        self._set_busy(True)
        controller = self._current_controller()
        if not self._call.start(controller.undo):
            self._set_busy(False)

    def _cancel_undo(self) -> None:
        self.confirm_panel.hide()
        self.dry_run_output.clear()
        self._clear_error()

    def _start_fallback(self) -> None:
        if self._busy:
            return
        self._mode = "fallback"
        self.confirm_panel.hide()
        self._set_busy(True)
        controller = self._current_controller()
        if not self._call.start(controller.restore_from_backup):
            self._set_busy(False)

    def _worker_succeeded(self, payload: object) -> None:
        mode = self._mode
        if mode == "preview":
            self._preview_succeeded(payload)
        elif mode == "undo":
            self._undo_succeeded(payload)
        elif mode == "fallback":
            self._fallback_succeeded(payload)

    def _preview_succeeded(self, payload: object) -> None:
        if not _result_ok(payload):
            self._show_error("done.dry_run_failed")
            self._show_fallback()
            return
        text = str(getattr(payload, "stdout", "") or "").strip()
        if not text:
            text = str(getattr(payload, "stderr", "") or "").strip()
        self.dry_run_output.setText(text or self.tr("done.undo_dry_run_empty"))
        self.dry_run_output.show()
        self.confirm_panel.show()
        self._clear_error()

    def _undo_succeeded(self, payload: object) -> None:
        if not isinstance(payload, UndoResult):
            self._show_error("done.undo_failed")
            self._show_fallback()
            return
        if payload.restored:
            self._undo_done = True
            self._undo_status_key = "done.undone"
            self._render_summary()
            self.confirm_panel.hide()
            self.fallback_panel.hide()
            self.undo_button.hide()
            return
        self._show_error("done.undo_failed")
        if payload.fallback_backup is not None or self.backup is not None:
            self._show_fallback()

    def _fallback_succeeded(self, payload: object) -> None:
        if isinstance(payload, UndoResult) and payload.restored:
            self._undo_done = True
            self._undo_status_key = "done.restored"
            self._render_summary()
            self.fallback_panel.hide()
            self.undo_button.hide()
            return
        self._show_error("done.restore_failed")
        self.fallback_panel.show()

    def _worker_failed(self, error: object) -> None:
        logging.getLogger(LOGGER_NAME).warning(
            "undo worker failed: %s", type(error).__name__
        )
        if self._mode == "fallback":
            self._show_error("done.restore_failed")
            self.fallback_panel.show()
        elif self._mode == "preview":
            self._show_error("done.dry_run_failed")
            self._show_fallback()
        else:
            self._show_error("done.undo_failed")
            self._show_fallback()

    def _worker_finished(self) -> None:
        self._set_busy(False)

    # ------------------------------------------------------------------ state

    def _show_fallback(self) -> None:
        self.fallback_warning_label.setText(self.tr("done.fallback_warning"))
        self.fallback_button.setText(self.tr("done.restore_from_backup"))
        self.fallback_panel.show()

    def _show_error(self, key: str) -> None:
        self._error_key = key
        self.error_label.setText(self.tr(key))
        self.error_label.show()

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.confirm_button.setEnabled(not busy)
        self.cancel_button.setEnabled(not busy)
        self.fallback_button.setEnabled(not busy)
        if busy:
            self._clear_error()
            self.status_label.hide()
            self.undo_button.setEnabled(False)
        self._update_actions()

    def _update_actions(self) -> None:
        available = (
            self.summary is not None
            and self.backup is not None
            and not self._undo_done
        )
        self.undo_button.setVisible(available)
        self.undo_button.setEnabled(available and not self._busy)

    # ----------------------------------------------------------------- reset

    def shutdown(self) -> None:
        self._call.shutdown(5000)

    def reset(self) -> None:
        self._call.shutdown(5000)
        self._busy = False
        self._mode = ""
        self._undo_done = False
        self._undo_status_key = "done.undone"
        self._controller = None
        self.summary = None
        self.next_page = None
        self._clear_error()
        self.confirm_panel.hide()
        self.fallback_panel.hide()
        self.dry_run_output.clear()
        self.remaining_caption.hide()
        self.remaining_label.hide()
        self.status_label.hide()
        self.summary_warning_label.hide()
        self.verified_label.hide()
        self.backup_caption.hide()
        self.backup_label.clear()
        self.backup_label.hide()
        self.count_label.clear()
        self.undo_button.hide()

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("done.title"))
        self.body_label.setText(self.tr("done.body"))
        self.undo_button.setText(self.tr("done.undo_all"))
        self.confirm_title_label.setText(self.tr("done.undo_title"))
        self.confirm_body_label.setText(self.tr("done.undo_body"))
        self.dry_run_caption.setText(self.tr("done.undo_dry_run"))
        self.confirm_button.setText(self.tr("done.undo_confirm"))
        self.cancel_button.setText(self.tr("common.cancel"))
        self.fallback_warning_label.setText(self.tr("done.fallback_warning"))
        self.fallback_button.setText(self.tr("done.restore_from_backup"))
        self.remaining_caption.setText(self.tr("done.remaining_caption"))
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))
        if self.summary is not None:
            self._render_summary()

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.count_label.setAccessibleName(self.count_label.text())
        self.undo_button.setAccessibleName(self.undo_button.text())
        self.confirm_button.setAccessibleName(self.confirm_button.text())
        self.cancel_button.setAccessibleName(self.cancel_button.text())
        self.fallback_button.setAccessibleName(self.fallback_button.text())


__all__ = ["DonePage"]
