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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from cleanyourphone_app.domain.support import SKILL_URL
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


# The CLI returns stable preset keys. These labels are proper names, so they
# stay readable instead of showing the raw alias when a description is absent.
_ADS_LABELS: dict[str, str] = {
    "adguard": "AdGuard",
    "adguard-family": "AdGuard Family",
    "controld": "Control D",
    "mullvad": "Mullvad",
}
_FALLBACK_ADS_PROVIDERS: dict[str, dict[str, str]] = {
    "adguard": {
        "host": "dns.adguard-dns.com",
        "description": "AdGuard DNS: ads and trackers",
    }
}


def _ads_label(provider: str, preset: object) -> str:
    label = _ADS_LABELS.get(provider)
    if label is not None:
        return label
    description = ""
    if isinstance(preset, dict):
        description = str(preset.get("description") or "").strip()
    if description:
        return description.split(":", 1)[0].strip() or provider
    return provider.replace("-", " ").title()


class ReviewPage(Page):
    """The checked selection and the exact package details behind it."""

    ads_selected = Signal(object)

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
        self._documented = False
        self._providers_requested = False
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
        self._providers_call = BackgroundCall(self)
        self._providers_call.succeeded.connect(self._providers_succeeded)
        self._providers_call.failed.connect(self._providers_failed)
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

    def active_catalog(self) -> PackageCatalog | None:
        """Return the Spanish catalog only while Spanish is the UI language."""
        if self.context.translator.language != "es":
            return None
        return self._catalog

    def shows_english_note(self) -> bool:
        """Whether missing Spanish details should be marked in Spanish."""
        return self.context.translator.language == "es"

    @property
    def selected_count(self) -> int:
        return self.model.selected_count() if self.model is not None else 0

    def selected_packages(self) -> tuple[str, ...]:
        return self.model.selected_packages() if self.model is not None else ()

    @property
    def ads_provider(self) -> str | None:
        """The chosen private DNS preset, or ``None`` when ads are off."""
        if not self.ads_checkbox.isChecked():
            return None
        provider = self.ads_combo.currentData()
        if isinstance(provider, str) and provider:
            return provider
        # The card must never be checked without a provider: AdGuard is the
        # documented default and stays selectable if the presets are late.
        return "adguard"

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

        self.documented_card = QFrame(self)
        self.documented_card.setObjectName("DocumentedNotice")
        documented_layout = QVBoxLayout(self.documented_card)
        documented_layout.setContentsMargins(14, 12, 14, 12)
        documented_layout.setSpacing(8)

        self.documented_label = QLabel(self.documented_card)
        self.documented_label.setProperty("role", "warning")
        self.documented_label.setWordWrap(True)

        self.documented_ack = QCheckBox(self.documented_card)
        self.documented_ack.setObjectName("review_documented_ack")
        self.documented_ack.toggled.connect(
            lambda checked=False: self._update_selection_state()
        )

        self.documented_skill_label = QLabel(self.documented_card)
        self.documented_skill_label.setProperty("role", "muted")
        self.documented_skill_label.setWordWrap(True)
        self.documented_skill_label.setTextFormat(Qt.TextFormat.RichText)
        self.documented_skill_label.setOpenExternalLinks(True)
        self.documented_skill_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )

        documented_layout.addWidget(self.documented_label)
        documented_layout.addWidget(self.documented_ack)
        documented_layout.addWidget(self.documented_skill_label)
        self.documented_card.hide()

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

        self.ads_card = QFrame(content)
        self.ads_card.setObjectName("ReviewAdsCard")
        ads_layout = QVBoxLayout(self.ads_card)
        ads_layout.setContentsMargins(16, 14, 16, 14)
        ads_layout.setSpacing(8)
        self.ads_checkbox = QCheckBox(self.ads_card)
        self.ads_checkbox.setObjectName("review_ads_checkbox")
        self.ads_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ads_checkbox.setChecked(False)
        self.ads_checkbox.toggled.connect(self._set_ads_enabled)
        self.ads_body = QLabel(self.ads_card)
        self.ads_body.setProperty("role", "body")
        self.ads_body.setWordWrap(True)
        self.ads_provider_caption = QLabel(self.ads_card)
        self.ads_provider_caption.setProperty("role", "muted")
        self.ads_combo = QComboBox(self.ads_card)
        self.ads_combo.setObjectName("review_ads_combo")
        self.ads_combo.setEnabled(False)
        self.ads_caveat_label = QLabel(self.ads_card)
        self.ads_caveat_label.setObjectName("review_ads_caveat")
        self.ads_caveat_label.setProperty("role", "muted")
        self.ads_caveat_label.setWordWrap(True)

        ads_provider_row = QHBoxLayout()
        ads_provider_row.setContentsMargins(0, 0, 0, 0)
        ads_provider_row.setSpacing(10)
        ads_provider_row.addWidget(self.ads_provider_caption)
        ads_provider_row.addWidget(self.ads_combo, 1)
        ads_provider_row.addStretch(1)

        ads_layout.addWidget(self.ads_checkbox)
        ads_layout.addWidget(self.ads_body)
        ads_layout.addLayout(ads_provider_row)
        ads_layout.addWidget(self.ads_caveat_label)

        content_layout.addWidget(self.tested_section)
        content_layout.addWidget(self.ask_section)
        self.tested_section.hide()
        self.ask_section.hide()
        content_layout.addWidget(self.ads_card)
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
        layout.addWidget(self.documented_card)
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
        self._ensure_providers()
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
        self._providers_call.shutdown(5000)

    def reset(self) -> None:
        self._call.shutdown(5000)
        self._providers_call.shutdown(5000)
        self._busy = False
        self._has_run = False
        self._mode = "load"
        self._providers_requested = False
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
        self.ads_checkbox.setChecked(False)
        self.ads_combo.setEnabled(False)
        index = self.ads_combo.findData("adguard")
        if index >= 0:
            self.ads_combo.setCurrentIndex(index)
        self.backup_caption.hide()
        self.backup_label.clear()
        self.backup_label.hide()
        self._set_documented_mode(False)
        self._update_selection_state()

    def _continue_to_apply(self, checked: bool = False) -> None:
        if self._busy or self.model is None:
            return
        if self._documented and not self.documented_ack.isChecked():
            self._update_selection_state()
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

    # ----------------------------------------------------------------- ads

    def _ensure_providers(self) -> None:
        """Load the DNS presets once, without blocking the UI thread."""
        if self._providers_requested:
            return
        self._providers_requested = True
        loader = getattr(self._cli, "dns_providers", None)
        if not callable(loader):
            self._set_providers(None)
            return
        if not self._providers_call.start(loader):
            self._providers_requested = False
            self._set_providers(None)

    def _providers_succeeded(self, payload: object) -> None:
        self._set_providers(payload if isinstance(payload, dict) else None)

    def _providers_failed(self, error: object) -> None:
        logging.getLogger(LOGGER_NAME).warning(
            "dns providers failed: %s", type(error).__name__
        )
        self._set_providers(None)

    def _set_providers(self, payload: dict | None) -> None:
        providers = payload if isinstance(payload, dict) and payload else None
        if providers is None:
            providers = _FALLBACK_ADS_PROVIDERS
        current = self.ads_combo.currentData()
        self.ads_combo.blockSignals(True)
        self.ads_combo.clear()
        # AdGuard is the documented default, so it stays first even if the
        # sidecar returns its presets in a different order.
        for provider in sorted(providers, key=lambda name: (name != "adguard", name)):
            preset = providers[provider]
            self.ads_combo.addItem(_ads_label(provider, preset), provider)
            description = (
                preset.get("description") if isinstance(preset, dict) else None
            )
            if isinstance(description, str) and description.strip():
                self.ads_combo.setItemData(
                    self.ads_combo.count() - 1,
                    description,
                    Qt.ItemDataRole.ToolTipRole,
                )
        target = current if isinstance(current, str) and current else "adguard"
        index = self.ads_combo.findData(target)
        if index < 0:
            index = self.ads_combo.findData("adguard")
        if index < 0:
            index = 0
        self.ads_combo.setCurrentIndex(index)
        self.ads_combo.blockSignals(False)
        self.ads_combo.setEnabled(self.ads_checkbox.isChecked())

    def _set_ads_enabled(self, enabled: bool) -> None:
        self.ads_combo.setEnabled(enabled)

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
                self._set_documented_mode(False)
                self._rebuild_rows()
                self._update_selection_state()
            return

        if mode == "refresh":
            self._apply_refreshed_plan(result)
            return

        self.model = ReviewModel.from_plan(result)
        self._set_documented_mode(result.verification == "documented")
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
        self.ads_selected.emit(self.ads_provider)
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
            self.active_catalog(),
            checked=checked,
            selectable=selectable,
            show_english_note=self.shows_english_note(),
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

    def _set_documented_mode(self, documented: bool) -> None:
        self._documented = documented
        self.documented_card.setVisible(documented)
        if documented:
            self.documented_ack.blockSignals(True)
            self.documented_ack.setChecked(False)
            self.documented_ack.blockSignals(False)

    def _update_selection_state(self) -> None:
        count = self.selected_count
        self.continue_button.setText(self.tr("review.disable_n", count=count))
        acknowledged = not self._documented or self.documented_ack.isChecked()
        self.continue_button.setEnabled(
            self.model is not None and count > 0 and not self._busy and acknowledged
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
        self.documented_label.setText(self.tr("review.documented_warning"))
        self.documented_ack.setText(self.tr("review.documented_ack"))
        self.documented_skill_label.setText(
            f'<a href="{SKILL_URL}" style="color:#A78BFA;">'
            f"{self.tr('review.documented_skill')}</a>"
        )
        self.busy_label.setText(self.tr("review.loading"))
        self.tested_heading.setText(self.tr("review.tested"))
        self.ask_heading.setText(self.tr("review.ask"))
        self.ask_note.setText(self.tr("review.ask_note"))
        self.ads_checkbox.setText(self.tr("ads.block"))
        self.ads_body.setText(self.tr("ads.body"))
        self.ads_provider_caption.setText(self.tr("ads.provider"))
        self.ads_caveat_label.setText(self.tr("ads.caveat"))
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
        catalog = self.active_catalog()
        show_english_note = self.shows_english_note()
        for row in self.row_widgets.values():
            row.catalog = catalog
            row.show_english_note = show_english_note
            row.retranslate()
        self._update_selection_state()
        self._update_backup_path()

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.busy_label.setAccessibleName(self.busy_label.text())
        self.ask_note.setAccessibleName(self.ask_note.text())
        self.ads_checkbox.setAccessibleName(self.ads_checkbox.text())
        self.ads_body.setAccessibleName(self.ads_body.text())
        self.ads_provider_caption.setAccessibleName(
            self.ads_provider_caption.text()
        )
        self.ads_combo.setAccessibleName(self.ads_provider_caption.text())
        self.ads_caveat_label.setAccessibleName(self.ads_caveat_label.text())
        self.empty_label.setAccessibleName(self.empty_label.text())
        self.retry_button.setAccessibleName(self.retry_button.text())
        self.blocked_button.setAccessibleName(self.blocked_button.text())
        self.continue_button.setAccessibleName(self.continue_button.text())


def is_tested(plan_row: PlanRow) -> bool:
    return plan_row.action.strip().upper() == "DISABLE"


__all__ = ["ReviewPage"]
