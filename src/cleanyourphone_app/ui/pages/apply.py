"""Apply the reviewed selection in visible, verified batches.

The page never starts a write by itself. It calls ``session.start_apply()``
exactly once when the user clicks Apply, runs the :class:`ApplyController` on a
``BackgroundCall`` worker, and keeps every widget update on the UI thread by
receiving progress through a queued signal. Window close stays blocked while a
batch is in flight, and a failure shows the packages that are actually still
disabled instead of claiming the phone is unchanged. The controller also takes
local before/after measurements; they are part of the summary and never gate or
undo a package write.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.apply import (
    ApplyController,
    ApplyProgress,
    ApplyResult,
    ApplySummary,
)
from cleanyourphone_app.domain.batches import split_batches
from cleanyourphone_app.domain.session import SessionError
from cleanyourphone_app.services.logging import LOGGER_NAME
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.services.cli import CliClient
    from cleanyourphone_app.ui.app import AppContext


class ApplyPage(Page):
    """Progress, a batch list and a stop-after-this-batch flag."""

    progress_ready = Signal(object)
    completed = Signal(object)

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
        self._started = False
        self._stop_requested = False
        self._selected: tuple[str, ...] = ()
        self._applied: tuple[str, ...] = ()
        self._result: ApplyResult | None = None
        self._ads_provider: str | None = None
        self._batch_index = 1
        self._total_batches = 0
        self._batch_size = 5
        self._documented = False
        self._status_key: str | None = None
        self._status_kwargs: dict[str, object] = {}
        self._error_key: str | None = None
        self.last_summary: ApplySummary | None = None

        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._apply_succeeded)
        self._call.failed.connect(self._apply_failed)
        self._call.finished.connect(self._apply_finished)
        self.progress_ready.connect(self._on_progress)
        self._build_ui()
        self.retranslate()

    # ------------------------------------------------------------------ state

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def close_blocked(self) -> bool:
        return self._busy or self._call.active

    @property
    def result(self) -> ApplyResult | None:
        return self._result

    @property
    def applied_packages(self) -> tuple[str, ...]:
        return self._applied

    @property
    def ads_provider(self) -> str | None:
        return self._ads_provider

    def set_ads_provider(self, provider: str | None) -> None:
        """Record the optional DNS preset chosen on Review."""
        if provider is None:
            self._ads_provider = None
            return
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("ads provider must be a non-empty string or None")
        self._ads_provider = provider.strip()

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

        self.do_not_close_label = QLabel(self)
        self.do_not_close_label.setProperty("role", "muted")
        self.do_not_close_label.setWordWrap(True)

        self.batch_label = QLabel(self)
        self.batch_label.setObjectName("apply_batch_label")
        self.batch_label.setProperty("role", "brand")
        self.batch_label.setWordWrap(True)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("apply_progress")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.status_label = QLabel(self)
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)

        self.packages_caption = QLabel(self)
        self.packages_caption.setProperty("role", "muted")

        self.package_list = QListWidget(self)
        self.package_list.setObjectName("apply_package_list")
        self.package_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        self.package_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.remaining_label = QLabel(self)
        self.remaining_label.setObjectName("apply_remaining_label")
        self.remaining_label.setProperty("role", "error")
        self.remaining_label.setWordWrap(True)
        self.remaining_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.remaining_label.hide()

        self.stopping_label = QLabel(self)
        self.stopping_label.setProperty("role", "muted")
        self.stopping_label.setWordWrap(True)
        self.stopping_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.empty_label = QLabel(self)
        self.empty_label.setProperty("role", "muted")
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()

        self.apply_button = QPushButton(self)
        self.apply_button.setObjectName("apply_button")
        self.apply_button.setProperty("primary", True)
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(lambda checked=False: self.apply())

        self.stop_button = QPushButton(self)
        self.stop_button.setObjectName("apply_stop_button")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(self._request_stop)
        self.stop_button.hide()

        self.undo_button = QPushButton(self)
        self.undo_button.setObjectName("apply_undo_button")
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self._undo_partial)
        self.undo_button.hide()

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self.undo_button)
        actions.addStretch(1)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.apply_button)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.do_not_close_label)
        layout.addWidget(self.batch_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.packages_caption)
        layout.addWidget(self.package_list, 1)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.remaining_label)
        layout.addWidget(self.stopping_label)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)

    # ---------------------------------------------------------------- actions

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started and not self._busy:
            self._sync_from_session()

    def apply(self) -> None:
        """Start applying, exactly once, for the reviewed selection."""
        if self._busy or self._started or self._call.active:
            return
        session = self.context.session
        if not session.can_apply():
            self._show_error("apply.not_ready")
            self._sync_from_session()
            return

        selected = session.selected_packages
        profile_id = session.profile_id
        if not isinstance(profile_id, str) or not profile_id.strip():
            self._show_error("apply.not_ready")
            return

        try:
            session.start_apply()
        except SessionError:
            self._show_error("apply.not_ready")
            self._sync_from_session()
            return

        self._started = True
        self._stop_requested = False
        self._selected = tuple(selected)
        self._applied = ()
        self._result = None
        self.last_summary = None
        self._documented = session.verification == "documented"
        self._batch_size = 1 if self._documented else 5
        self.body_label.setText(
            self.tr("apply.body_documented" if self._documented else "apply.body")
        )
        self._total_batches = len(
            split_batches(self._selected, self._batch_size)
        )
        self._batch_index = 1
        self._fill_packages()
        self._render_batch()
        self._set_busy(True)

        controller = self._controller
        if controller is None:
            controller = ApplyController(
                self._cli,
                backup=session.backup_path,
                batch_size=self._batch_size,
            )
            self._controller = controller

        ads_provider = self._ads_provider

        def call() -> ApplyResult:
            return controller.run(
                self._selected,
                profile_id,
                on_progress=self.progress_ready.emit,
                should_stop=lambda: self._stop_requested,
                ads_provider=ads_provider,
            )

        if not self._call.start(call):
            self._set_busy(False)
            self._show_error("apply.not_ready")

    def _request_stop(self) -> None:
        if not self._busy or self._stop_requested:
            return
        self._stop_requested = True
        self.stop_button.setEnabled(False)
        self.stopping_label.setText(self.tr("apply.stopping"))
        self.stopping_label.show()

    def _undo_partial(self) -> None:
        if self._result is None or self._busy:
            return
        self._finish_done(stopped=False)

    def _finish_done(self, *, stopped: bool) -> None:
        if self._result is None:
            return
        summary = ApplySummary(
            result=self._result,
            applied=tuple(self._applied),
            selected=tuple(self._selected),
            stopped=stopped,
        )
        self.last_summary = summary
        self.completed.emit(summary)
        self._go("done")

    # --------------------------------------------------------------- workers

    def _apply_succeeded(self, result: object) -> None:
        if not isinstance(result, ApplyResult):
            self._apply_failed(RuntimeError("invalid apply result"))
            return

        self._result = result
        if result.completed:
            self._finish_session()
            self._finish_done(stopped=False)
            return

        if result.failed_batch is not None:
            self._show_failure(result, plan_changed=False)
            return

        if self._stop_requested:
            self._finish_session()
            self._finish_done(stopped=True)
            return

        self._show_failure(result, plan_changed=True)

    def _apply_failed(self, error: object) -> None:
        logging.getLogger(LOGGER_NAME).warning(
            "apply worker failed: %s", type(error).__name__
        )
        synthetic = ApplyResult(
            completed=False,
            failed_batch=(),
            remaining_disabled=(),
            rollback_verified=False,
            verify={},
        )
        self._result = synthetic
        self._show_failure(synthetic, plan_changed=False)

    def _apply_finished(self) -> None:
        self._set_busy(False)

    def _record_batch(self) -> None:
        try:
            self.context.session.batch_done()
        except SessionError:
            logging.getLogger(LOGGER_NAME).warning(
                "could not record a completed apply batch"
            )

    def _finish_session(self) -> None:
        try:
            self.context.session.finish()
        except SessionError:
            logging.getLogger(LOGGER_NAME).warning(
                "could not mark the apply session as finished"
            )

    # ----------------------------------------------------------------- events

    def _on_progress(self, progress: object) -> None:
        if not isinstance(progress, ApplyProgress):
            return
        self._applied = tuple(progress.completed)
        self._batch_index = progress.batch_index
        self._total_batches = progress.total_batches
        self._render_batch()

        if progress.phase == "started":
            self._set_status(
                "apply.running_batch",
                current=progress.batch_index,
                total=progress.total_batches,
            )
            self.progress_bar.setValue(max(0, progress.batch_index - 1))
        elif progress.phase == "done":
            self._set_status(
                "apply.batch_done",
                current=progress.batch_index,
                total=progress.total_batches,
            )
            self.progress_bar.setValue(progress.batch_index)
            self._record_batch()
        elif progress.phase == "skipped":
            self._set_status("apply.plan_changed")
        elif progress.phase == "stopped":
            self._set_status("apply.stopping")

    # ------------------------------------------------------------------ state

    def _sync_from_session(self) -> None:
        selected = tuple(self.context.session.selected_packages)
        self._selected = selected
        self._documented = self.context.session.verification == "documented"
        self._batch_size = 1 if self._documented else 5
        self.body_label.setText(
            self.tr("apply.body_documented" if self._documented else "apply.body")
        )
        self._total_batches = len(split_batches(selected, self._batch_size))
        self._batch_index = 1
        self._fill_packages()
        self._render_batch()
        if self.context.session.can_apply():
            self._clear_error()
        self._update_actions()

    def _fill_packages(self) -> None:
        self.package_list.clear()
        for package in self._selected:
            item = QListWidgetItem(package, self.package_list)
            item.setToolTip(package)
        self.package_list.setVisible(bool(self._selected))
        self.packages_caption.setVisible(bool(self._selected))

    def _render_batch(self) -> None:
        if self._total_batches < 1:
            self.batch_label.hide()
            self.progress_bar.hide()
            return
        total = self._total_batches
        index = min(max(1, self._batch_index), total)
        self.batch_label.setText(
            self.tr("apply.batch_of", current=index, total=total)
        )
        self.batch_label.show()
        self.progress_bar.setMaximum(total)
        self.progress_bar.show()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._clear_error()
            self.remaining_label.hide()
            self.undo_button.hide()
            self.stop_button.setEnabled(not self._stop_requested)
            self.stop_button.setText(self.tr("apply.stop_after_batch"))
            self.stop_button.show()
            self.status_label.show()
        else:
            self.stop_button.hide()
            if self._result is not None and not self._result.completed:
                self.undo_button.show()
        self.apply_button.setText(
            self.tr("apply.applying" if busy else "apply.start")
        )
        self._update_actions()

    def _update_actions(self) -> None:
        can_start = (
            not self._busy
            and not self._started
            and self.context.session.can_apply()
        )
        self.apply_button.setEnabled(can_start)
        self.stop_button.setEnabled(self._busy and not self._stop_requested)
        self.empty_label.setVisible(
            not self._busy and not self._selected and not self._started
        )

    def _show_failure(self, result: ApplyResult, *, plan_changed: bool) -> None:
        key = "apply.plan_changed" if plan_changed else "apply.failed"
        self._error_key = key
        self.error_label.setText(self.tr(key))
        self.error_label.show()

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
        self.undo_button.show()
        self.stopping_label.hide()
        self._update_actions()

    def _set_status(self, key: str, **kwargs: object) -> None:
        self._status_key = key
        self._status_kwargs = dict(kwargs)
        self.status_label.setText(self.tr(key, **kwargs))
        self.status_label.show()

    def _show_error(self, key: str) -> None:
        self._error_key = key
        self.error_label.setText(self.tr(key))
        self.error_label.show()

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()

    # ----------------------------------------------------------------- reset

    def shutdown(self) -> None:
        self._call.shutdown(5000)

    def reset(self) -> None:
        self._call.shutdown(5000)
        self._busy = False
        self._started = False
        self._stop_requested = False
        self._selected = ()
        self._applied = ()
        self._result = None
        self._ads_provider = None
        self._controller = None
        self.last_summary = None
        self._batch_index = 1
        self._total_batches = 0
        self._status_key = None
        self._status_kwargs = {}
        self.next_page = None
        self._clear_error()
        self.remaining_label.hide()
        self.stopping_label.hide()
        self.undo_button.hide()
        self.stop_button.hide()
        self.status_label.clear()
        self.package_list.clear()
        self.package_list.hide()
        self.packages_caption.hide()
        self.apply_button.setText(self.tr("apply.start"))
        self._render_batch()
        self._update_actions()

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("apply.title"))
        self.body_label.setText(
            self.tr("apply.body_documented" if self._documented else "apply.body")
        )
        self.do_not_close_label.setText(self.tr("apply.do_not_close"))
        self.packages_caption.setText(self.tr("apply.packages"))
        self.empty_label.setText(self.tr("apply.empty_selection"))
        self.apply_button.setText(
            self.tr("apply.applying" if self._busy else "apply.start")
        )
        self.stop_button.setText(self.tr("apply.stop_after_batch"))
        self.undo_button.setText(self.tr("apply.undo_all"))
        self.stopping_label.setText(self.tr("apply.stopping"))
        self._render_batch()
        if self._status_key is not None:
            self.status_label.setText(
                self.tr(self._status_key, **self._status_kwargs)
            )
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.do_not_close_label.setAccessibleName(self.do_not_close_label.text())
        self.batch_label.setAccessibleName(self.batch_label.text())
        self.progress_bar.setAccessibleName(self.batch_label.text())
        self.packages_caption.setAccessibleName(self.packages_caption.text())
        self.apply_button.setAccessibleName(self.apply_button.text())
        self.stop_button.setAccessibleName(self.stop_button.text())
        self.undo_button.setAccessibleName(self.undo_button.text())


__all__ = ["ApplyPage"]
