"""Review every package before any write.

The page shows the tested ``DISABLE`` list, the optional ``ASK`` list and a
collapsed not-changed list. Before navigating to Apply it re-runs ``plan`` and
intersects the selection, so a package that stopped being actionable is never
sent to the CLI. The page records the selection and leaves the session in
``REVIEW``; Apply owns the ``start_apply()`` transition.
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
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.models import PlanData, PlanRow
from cleanyourphone_app.domain.review import ReviewModel, plan_allows_review
from cleanyourphone_app.domain.session import SessionError
from cleanyourphone_app.i18n.packages import PackageCatalog
from cleanyourphone_app.services.logging import LOGGER_NAME
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.widgets.package_row import PackageRow
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.services.cli import CliClient
    from cleanyourphone_app.ui.app import AppContext


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class ReviewPage(Page):
    """The checked selection and the exact package details behind it."""

    def __init__(
        self,
        context: AppContext,
        cli: CliClient | None = None,
        catalog: PackageCatalog | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(context, parent)
        self._cli = cli if cli is not None else context.cli
        self._catalog = catalog
        self._busy = False
        self._has_run = False
        self._mode = "load"
        self._error_key: str | None = None
        self.model: ReviewModel | None = None
        self.row_widgets: dict[str, PackageRow] = {}
        self.tested_rows: list[PackageRow] = []
        self.ask_rows: list[PackageRow] = []
        self.blocked_rows: list[PackageRow] = []
        self.tested_list = self.tested_rows
        self.ask_list = self.ask_rows
        self.blocked_list = self.blocked_rows
        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._plan_succeeded)
        self._call.failed.connect(self._plan_failed)
        self._call.finished.connect(self._plan_finished)
        self._build_ui()
        self.retranslate()

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def review_model(self) -> ReviewModel | None:
        return self.model

    @property
    def catalog(self) -> PackageCatalog | None:
        return self._catalog

    @property
    def selected_count(self) -> int:
        return self.model.selected_count() if self.model is not None else 0

    def selected_packages(self) -> tuple[str, ...]:
        return self.model.selected_packages() if self.model is not None else ()

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

        self.busy_label = QLabel(self)
        self.busy_label.setProperty("role", "muted")
        self.busy_label.setWordWrap(True)
        self.busy_label.hide()

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("review_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget(self.scroll)
        content.setObjectName("review_content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(14)

        self.tested_section = QWidget(content)
        tested_layout = QVBoxLayout(self.tested_section)
        tested_layout.setContentsMargins(0, 0, 0, 0)
        tested_layout.setSpacing(8)
        self.tested_heading = QLabel(self.tested_section)
        self.tested_heading.setProperty("role", "brand")
        self.tested_heading.setWordWrap(True)
        self.tested_rows_layout = QVBoxLayout()
        self.tested_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.tested_rows_layout.setSpacing(8)
        tested_layout.addWidget(self.tested_heading)
        tested_layout.addLayout(self.tested_rows_layout)

        self.ask_section = QWidget(content)
        ask_layout = QVBoxLayout(self.ask_section)
        ask_layout.setContentsMargins(0, 0, 0, 0)
        ask_layout.setSpacing(8)
        self.ask_heading = QLabel(self.ask_section)
        self.ask_heading.setProperty("role", "brand")
        self.ask_heading.setWordWrap(True)
        self.ask_note = QLabel(self.ask_section)
        self.ask_note.setProperty("role", "muted")
        self.ask_note.setWordWrap(True)
        self.ask_rows_layout = QVBoxLayout()
        self.ask_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.ask_rows_layout.setSpacing(8)
        ask_layout.addWidget(self.ask_heading)
        ask_layout.addWidget(self.ask_note)
        ask_layout.addLayout(self.ask_rows_layout)

        self.blocked_header = QWidget(content)
        blocked_header_layout = QHBoxLayout(self.blocked_header)
        blocked_header_layout.setContentsMargins(0, 4, 0, 0)
        blocked_header_layout.setSpacing(10)
        self.blocked_button = QPushButton(self.blocked_header)
        self.blocked_button.setObjectName("review_blocked_button")
        self.blocked_button.setCheckable(True)
        self.blocked_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.blocked_button.toggled.connect(self._set_blocked_visible)
        self.blocked_count_label = QLabel(self.blocked_header)
        self.blocked_count_label.setProperty("role", "muted")
        blocked_header_layout.addWidget(self.blocked_button)
        blocked_header_layout.addWidget(self.blocked_count_label)
        blocked_header_layout.addStretch(1)

        self.blocked_container = QWidget(content)
        self.blocked_rows_layout = QVBoxLayout(self.blocked_container)
        self.blocked_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.blocked_rows_layout.setSpacing(8)
        self.blocked_container.hide()

        content_layout.addWidget(self.tested_section)
        content_layout.addWidget(self.ask_section)
        self.tested_section.hide()
        self.ask_section.hide()
        self.blocked_header.hide()
        content_layout.addWidget(self.blocked_header)
        content_layout.addWidget(self.blocked_container)
        content_layout.addStretch(1)
        self.scroll.setWidget(content)

        self.backup_caption = QLabel(self)
        self.backup_caption.setProperty("role", "muted")
        self.backup_caption.hide()
        self.backup_label = QLabel(self)
        self.backup_label.setProperty("role", "package-id")
        self.backup_label.setWordWrap(True)
        self.backup_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.backup_label.hide()

        self.empty_label = QLabel(self)
        self.empty_label.setProperty("role", "muted")
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.retry_button = QPushButton(self)
        self.retry_button.setObjectName("review_retry_button")
        self.retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_button.clicked.connect(lambda checked=False: self.run())
        self.retry_button.hide()

        self.continue_button = QPushButton(self)
        self.continue_button.setObjectName("review_continue_button")
        self.continue_button.setProperty("primary", True)
        self.continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_button.clicked.connect(self._continue_to_apply)
        self.primary_button = self.continue_button

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self.retry_button)
        actions.addStretch(1)
        actions.addWidget(self.continue_button)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.backup_caption)
        layout.addWidget(self.backup_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)

        self._update_selection_state()

    # ---------------------------------------------------------------- actions

    def run(self) -> None:
        """Load the plan from the CLI on the worker thread."""
        if self._busy or self._call.active:
            return
        profile_id = self.context.session.profile_id
        if not isinstance(profile_id, str) or not profile_id.strip():
            self._has_run = True
            self._show_error("review.plan_failed")
            return

        self._has_run = True
        self._mode = "load"
        self._set_busy(True)
        cli = self._cli
        if not self._call.start(lambda: cli.plan(profile_id)):
            self._set_busy(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._has_run:
            self.run()

    def shutdown(self) -> None:
        self._call.shutdown(5000)

    def reset(self) -> None:
        self._call.shutdown(5000)
        self._busy = False
        self._has_run = False
        self._mode = "load"
        self.model = None
        self.next_page = None
        self._clear_rows()
        self._clear_error()
        self.busy_label.hide()
        self.empty_label.hide()
        self.retry_button.hide()
        self.tested_section.hide()
        self.ask_section.hide()
        self.blocked_header.hide()
        self.blocked_container.hide()
        self.blocked_button.setChecked(False)
        self.backup_caption.hide()
        self.backup_label.clear()
        self.backup_label.hide()
        self._update_selection_state()

    def _continue_to_apply(self, checked: bool = False) -> None:
        if self._busy or self.model is None:
            return
        selected = self.model.selected_packages()
        if not selected:
            self._update_selection_state()
            return
        profile_id = self.context.session.profile_id
        if not isinstance(profile_id, str) or not profile_id.strip():
            self._show_error("review.plan_failed")
            return

        self._mode = "refresh"
        self._set_busy(True)
        cli = self._cli
        if not self._call.start(lambda: cli.plan(profile_id)):
            self._set_busy(False)

    def _set_blocked_visible(self, visible: bool) -> None:
        self.blocked_container.setVisible(visible)
        self.blocked_button.setText(
            self.tr("review.hide_blocked" if visible else "review.show_blocked")
        )

    # --------------------------------------------------------------- workers

    def _plan_succeeded(self, result: object) -> None:
        mode = self._mode
        self._mode = "load"
        if not isinstance(result, PlanData):
            self._show_error("review.plan_failed", retry=mode == "load")
            return
        if not plan_allows_review(result):
            self._show_error("review.plan_changed", retry=mode == "load")
            if mode == "load":
                self.model = None
                self._rebuild_rows()
                self._update_selection_state()
            return

        if mode == "refresh":
            self._apply_refreshed_plan(result)
            return

        self.model = ReviewModel.from_plan(result)
        self._rebuild_rows()
        self._clear_error()
        self._update_backup_path()
        self._update_selection_state()

    def _plan_failed(self, error: object) -> None:
        mode = self._mode
        self._mode = "load"
        logging.getLogger(LOGGER_NAME).warning(
            "plan failed: %s", type(error).__name__
        )
        self._show_error("review.plan_failed", retry=mode == "load")

    def _plan_finished(self) -> None:
        self._set_busy(False)

    def _apply_refreshed_plan(self, new_plan: PlanData) -> None:
        if self.model is None:
            self._show_error("review.plan_failed", retry=False)
            return
        selected = self.model.intersect_with_plan(new_plan)
        self._rebuild_rows()
        self._clear_error()
        if not selected:
            self._update_selection_state()
            return
        try:
            self.context.session.set_selection(selected)
        except (SessionError, ValueError, TypeError):
            # No disable has run yet, so the phone is still unchanged. Keep the
            # session in REVIEW and let the user retry the review.
            self._show_error("review.plan_changed", retry=False)
            self._update_selection_state()
            return
        # ApplyPage owns the REVIEW -> APPLYING transition when the user
        # clicks Apply; Review must not start the write flow by itself.
        self._go("apply")

    # ----------------------------------------------------------------- rows

    def _rebuild_rows(self) -> None:
        self._clear_rows()
        if self.model is None:
            self.tested_section.hide()
            self.ask_section.hide()
            self.blocked_header.hide()
            self.blocked_container.hide()
            return

        for plan_row in self.model.tested_rows():
            self.tested_rows.append(
                self._make_row(plan_row, selectable=True)
            )
        for plan_row in self.model.ask_rows():
            self.ask_rows.append(self._make_row(plan_row, selectable=True))
        for plan_row in self.model.blocked_rows():
            self.blocked_rows.append(self._make_row(plan_row, selectable=False))

        self.tested_section.setVisible(bool(self.tested_rows))
        self.ask_section.setVisible(bool(self.ask_rows))
        self.blocked_header.setVisible(bool(self.blocked_rows))
        self.blocked_count_label.setText(str(len(self.blocked_rows)))
        if not self.blocked_rows:
            self.blocked_container.hide()
        else:
            self.blocked_container.setVisible(self.blocked_button.isChecked())
        self._update_backup_path()

    def _make_row(self, plan_row: PlanRow, *, selectable: bool) -> PackageRow:
        checked = self.model.is_checked(plan_row.package) if self.model else False
        row = PackageRow(
            plan_row,
            self._catalog,
            checked=checked,
            selectable=selectable,
            tr=self.tr,
            parent=self,
        )
        row.toggled.connect(self._row_toggled)
        layout = (
            self.blocked_rows_layout
            if not selectable
            else (
                self.tested_rows_layout
                if is_tested(plan_row)
                else self.ask_rows_layout
            )
        )
        layout.addWidget(row)
        self.row_widgets[plan_row.package] = row
        return row

    def _clear_rows(self) -> None:
        self.row_widgets.clear()
        self.tested_rows.clear()
        self.ask_rows.clear()
        self.blocked_rows.clear()
        _clear_layout(self.tested_rows_layout)
        _clear_layout(self.ask_rows_layout)
        _clear_layout(self.blocked_rows_layout)

    def _row_toggled(self, package: str, checked: bool) -> None:
        if self.model is None:
            return
        try:
            self.model.set_checked(package, checked)
        except (ValueError, TypeError):
            self._show_error("review.plan_changed", retry=False)
            self._rebuild_rows()
            return
        self._update_selection_state()

    # ---------------------------------------------------------------- state

    def _update_selection_state(self) -> None:
        count = self.selected_count
        self.continue_button.setText(self.tr("review.disable_n", count=count))
        self.continue_button.setEnabled(
            self.model is not None and count > 0 and not self._busy
        )
        self.empty_label.setVisible(
            self.model is not None and count == 0 and not self._busy
        )

    def _update_backup_path(self) -> None:
        path = self.context.session.backup_path
        if isinstance(path, Path):
            self.backup_caption.setText(self.tr("backup.path"))
            self.backup_label.setText(str(path))
            self.backup_caption.show()
            self.backup_label.show()
        else:
            self.backup_caption.hide()
            self.backup_label.clear()
            self.backup_label.hide()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._clear_error()
            self.busy_label.setText(self.tr("review.loading"))
            self.busy_label.show()
        else:
            self.busy_label.hide()
        self.retry_button.setEnabled(not busy)
        self._update_selection_state()

    def _show_error(self, key: str, *, retry: bool = True) -> None:
        self._error_key = key
        self.error_label.setText(self.tr(key))
        self.error_label.show()
        self.retry_button.setVisible(retry)
        self.retry_button.setEnabled(not self._busy)
        if retry:
            self.empty_label.hide()

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()
        self.retry_button.hide()

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("review.title"))
        self.body_label.setText(self.tr("review.body"))
        self.busy_label.setText(self.tr("review.loading"))
        self.tested_heading.setText(self.tr("review.tested"))
        self.ask_heading.setText(self.tr("review.ask"))
        self.ask_note.setText(self.tr("review.ask_note"))
        self.empty_label.setText(self.tr("review.empty_selection"))
        self.retry_button.setText(self.tr("review.retry"))
        self.backup_caption.setText(self.tr("backup.path"))
        self.blocked_button.setText(
            self.tr(
                "review.hide_blocked"
                if self.blocked_button.isChecked()
                else "review.show_blocked"
            )
        )
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))
        for row in self.row_widgets.values():
            row.retranslate()
        self._update_selection_state()
        self._update_backup_path()

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.busy_label.setAccessibleName(self.busy_label.text())
        self.ask_note.setAccessibleName(self.ask_note.text())
        self.empty_label.setAccessibleName(self.empty_label.text())
        self.retry_button.setAccessibleName(self.retry_button.text())
        self.blocked_button.setAccessibleName(self.blocked_button.text())
        self.continue_button.setAccessibleName(self.continue_button.text())


def is_tested(plan_row: PlanRow) -> bool:
    return plan_row.action.strip().upper() == "DISABLE"


__all__ = ["ReviewPage"]
