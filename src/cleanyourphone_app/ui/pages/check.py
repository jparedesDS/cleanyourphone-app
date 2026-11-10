"""Probe the attached phone and decide whether the guided flow may continue.

The probe is the only source of the support decision. It runs on the existing
background worker so the window keeps painting during ADB calls, and every
session mutation happens back on the UI thread. A denied decision is recorded
with :meth:`SessionController.blocked` before the stop screen is shown; an
allowed phone records the exact serial, transport, probe and selected profile
with ``connected`` and then ``checked`` so Backup can never start from a
half-recorded session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.domain.session import SessionError, Transport
from cleanyourphone_app.domain.support import SupportedDecision, decide_support
from cleanyourphone_app.services.logging import LOGGER_NAME
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.pages.blocked import SAFETY_DOCS_URL
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.services.cli import CliClient
    from cleanyourphone_app.ui.app import AppContext


class CheckPage(Page):
    """Run ``probe`` and route the phone to Backup or the Blocked screen."""

    def __init__(
        self,
        context: AppContext,
        cli: CliClient | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(context, parent)
        self._cli = cli if cli is not None else context.cli
        self._busy = False
        self._error_key: str | None = None
        self._probe: ProbeData | None = None
        self._verification = "device"
        self._completed = False
        self._has_run = False
        self.blocked_reason: str | None = None
        self.blocked_link: str | None = None
        self.blocked_decision: SupportedDecision | None = None
        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._probe_succeeded)
        self._call.failed.connect(self._probe_failed)
        self._call.finished.connect(self._probe_finished)
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

        self.documented_label = QLabel(self)
        self.documented_label.setObjectName("check_documented_warning")
        self.documented_label.setProperty("role", "warning")
        self.documented_label.setWordWrap(True)
        self.documented_label.hide()

        details = QWidget(self)
        self.details = details
        form = QFormLayout(details)
        form.setContentsMargins(0, 6, 0, 6)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(8)

        self.model_caption = QLabel(details)
        self.model_caption.setProperty("role", "muted")
        self.model_label = QLabel(details)
        self.model_label.setWordWrap(True)
        self.android_caption = QLabel(details)
        self.android_caption.setProperty("role", "muted")
        self.android_label = QLabel(details)
        self.android_label.setWordWrap(True)
        self.build_caption = QLabel(details)
        self.build_caption.setProperty("role", "muted")
        self.build_label = QLabel(details)
        self.build_label.setWordWrap(True)
        self.battery_caption = QLabel(details)
        self.battery_caption.setProperty("role", "muted")
        self.battery_label = QLabel(details)
        self.connection_caption = QLabel(details)
        self.connection_caption.setProperty("role", "muted")
        self.connection_label = QLabel(details)

        form.addRow(self.model_caption, self.model_label)
        form.addRow(self.android_caption, self.android_label)
        form.addRow(self.build_caption, self.build_label)
        form.addRow(self.battery_caption, self.battery_label)
        form.addRow(self.connection_caption, self.connection_label)

        self.profile_label = QLabel(self)
        self.profile_label.setProperty("role", "body")
        self.profile_label.hide()

        self.profile_combo = QComboBox(self)
        self.profile_combo.setObjectName("check_profile_combo")
        self.profile_combo.hide()
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)

        self.continue_button = QPushButton(self)
        self.continue_button.setObjectName("check_continue_button")
        self.continue_button.setProperty("primary", True)
        self.continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_button.clicked.connect(self._continue_with_profile)
        self.continue_button.hide()

        selection = QHBoxLayout()
        selection.setContentsMargins(0, 0, 0, 0)
        selection.setSpacing(10)
        selection.addWidget(self.profile_label)
        selection.addWidget(self.profile_combo)
        selection.addWidget(self.continue_button)
        selection.addStretch(1)

        self.busy_label = QLabel(self)
        self.busy_label.setProperty("role", "muted")
        self.busy_label.setWordWrap(True)
        self.busy_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.retry_button = QPushButton(self)
        self.retry_button.setObjectName("check_retry_button")
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
        layout.addWidget(self.documented_label)
        layout.addWidget(details)
        layout.addLayout(selection)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)
        layout.addStretch(1)

        self._update_continue_enabled()

    # ---------------------------------------------------------------- actions

    def run(self) -> None:
        """Start one probe on the worker thread, unless one is already running."""
        if self._completed or self._busy or self._call.active:
            return

        self._has_run = True
        self._probe = None
        self._set_busy(True)
        if not self._call.start(self._cli.probe):
            self._set_busy(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._has_run:
            self.run()

    def shutdown(self) -> None:
        """Wait briefly for the probe worker when the window is closing."""
        self._call.shutdown(5000)

    def reset(self) -> None:
        """Return to a pristine page so a new phone can be probed again."""
        self._call.shutdown(5000)
        self._busy = False
        self._completed = False
        self._has_run = False
        self._probe = None
        self._verification = "device"
        self.blocked_reason = None
        self.blocked_link = None
        self.blocked_decision = None
        self.next_page = None
        self._clear_error()
        self.retry_button.hide()
        self.busy_label.hide()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.blockSignals(False)
        self.profile_label.hide()
        self.continue_button.hide()
        self.continue_button.setEnabled(False)
        self.documented_label.hide()
        self.continue_button.setText(self.tr("check.continue"))
        for label in (
            self.model_label,
            self.android_label,
            self.build_label,
            self.battery_label,
            self.connection_label,
        ):
            label.setText(self.tr("common.not_available"))

    def _probe_succeeded(self, result: object) -> None:
        if not isinstance(result, ProbeData):
            self._show_error("check.failed")
            return

        self._probe = result
        self.context.last_probe = result
        self._show_probe_details(result)
        decision = decide_support(result)
        if not decision.allowed:
            self._block(decision)
            return

        profile_ids = decision.profile_ids
        if decision.verification == "documented":
            if not profile_ids:
                self._show_error("check.failed")
                return
            self._show_profile_choice(profile_ids, documented=True)
            return
        if len(profile_ids) == 1:
            self._advance(result, profile_ids[0])
            return
        if not profile_ids:
            self._show_error("check.failed")
            return
        self._show_profile_choice(profile_ids)

    def _probe_failed(self, error: object) -> None:
        logging.getLogger(LOGGER_NAME).warning(
            "device probe failed: %s", type(error).__name__
        )
        self._show_error("check.failed")

    def _probe_finished(self) -> None:
        self._set_busy(False)

    def _advance(
        self, probe: ProbeData, profile_id: str, verification: str | None = None
    ) -> None:
        session = self.context.session
        serial = session.serial
        transport = session.transport
        if not isinstance(serial, str) or not serial.strip() or transport is None:
            self._show_error("check.failed")
            return

        mode = verification or self._verification
        try:
            # Keep the transport and serial pinned by Connect, then complete the
            # exact device record before the backup step can be reached.
            session.connected(serial, transport, probe, profile_id, mode)
            session.checked(probe, profile_id)
        except (SessionError, ValueError, TypeError):
            self._show_error("check.failed")
            return

        self._completed = True
        self._clear_error()
        self._go("backup")

    def _block(self, decision: SupportedDecision) -> None:
        self.blocked_reason = decision.reason
        self.blocked_decision = decision
        self.blocked_link = decision.link or SAFETY_DOCS_URL
        try:
            self.context.session.blocked(decision)
        except (SessionError, ValueError, TypeError):
            self._show_error("check.failed")
            return

        self._completed = True
        self._clear_error()
        self._go("blocked")

    def _show_profile_choice(
        self, profile_ids: tuple[str, ...], *, documented: bool = False
    ) -> None:
        self._verification = "documented" if documented else "device"
        self.documented_label.setVisible(documented)
        self.continue_button.setText(
            self.tr(
                "check.continue_documented" if documented else "check.continue"
            )
        )

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(self.tr("check.choose_profile"), None)
        placeholder = self.profile_combo.model().item(0)
        if placeholder is not None:
            placeholder.setEnabled(False)
        for profile_id in profile_ids:
            self.profile_combo.addItem(profile_id, profile_id)
        # A documented profile is never auto-advanced, even when it is the only
        # match. Preselect it so the person can read the warning and continue.
        self.profile_combo.setCurrentIndex(1 if documented and len(profile_ids) == 1 else 0)
        self.profile_combo.blockSignals(False)

        self.profile_label.show()
        self.profile_combo.show()
        self.continue_button.show()
        self._update_continue_enabled()

    def _profile_changed(self, index: int) -> None:
        self._update_continue_enabled()

    def _update_continue_enabled(self) -> None:
        profile_id = self.profile_combo.currentData()
        self.continue_button.setEnabled(
            not self._busy
            and isinstance(profile_id, str)
            and bool(profile_id.strip())
            and self._probe is not None
        )

    def _continue_with_profile(self, checked: bool = False) -> None:
        profile_id = self.profile_combo.currentData()
        if not isinstance(profile_id, str) or not profile_id.strip():
            return
        if not isinstance(self._probe, ProbeData):
            self._show_error("check.failed")
            return
        self._advance(self._probe, profile_id, self._verification)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._clear_error()
            self.busy_label.setText(self.tr("check.running"))
            self.busy_label.show()
            self.retry_button.hide()
            self.profile_label.hide()
            self.profile_combo.hide()
            self.continue_button.hide()
            self.documented_label.hide()
        else:
            self.busy_label.hide()
        self._update_continue_enabled()

    def _show_error(self, key: str) -> None:
        self._error_key = key
        self.error_label.setText(self.tr(key))
        self.error_label.show()
        self.retry_button.show()

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()

    def _show_probe_details(self, probe: ProbeData) -> None:
        model = " ".join(part for part in (probe.brand, probe.model) if part)
        self.model_label.setText(
            f"{model} ({probe.device})" if probe.device else model
        )
        self.android_label.setText(
            f"{probe.android} (SDK {probe.sdk})" if probe.android else ""
        )
        self.build_label.setText(probe.build)
        level = probe.battery.get("level")
        if isinstance(level, (int, float)) and not isinstance(level, bool):
            self.battery_label.setText(f"{int(level)}%")
        else:
            self.battery_label.setText(self.tr("common.not_available"))
        transport = self.context.session.transport
        if transport is Transport.USB:
            self.connection_label.setText(self.tr("check.transport_usb"))
        elif transport is Transport.WIFI:
            self.connection_label.setText(self.tr("check.transport_wifi"))
        else:
            self.connection_label.setText(self.tr("common.not_available"))

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("check.title"))
        self.body_label.setText(self.tr("check.body"))
        self.model_caption.setText(self.tr("check.model"))
        self.android_caption.setText(self.tr("check.android"))
        self.build_caption.setText(self.tr("check.build"))
        self.battery_caption.setText(self.tr("check.battery"))
        self.connection_caption.setText(self.tr("check.connection"))
        self.profile_label.setText(self.tr("check.profile"))
        self.continue_button.setText(
            self.tr(
                "check.continue_documented"
                if self._verification == "documented"
                else "check.continue"
            )
        )
        self.documented_label.setText(self.tr("check.documented_warning"))
        self.retry_button.setText(self.tr("check.retry"))
        self.busy_label.setText(self.tr("check.running"))
        if self.profile_combo.count():
            self.profile_combo.setItemText(0, self.tr("check.choose_profile"))
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))
        if isinstance(self._probe, ProbeData):
            self._show_probe_details(self._probe)

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.profile_label.setAccessibleName(self.profile_label.text())
        self.profile_combo.setAccessibleName(self.profile_label.text())
        self.continue_button.setAccessibleName(self.continue_button.text())
        self.retry_button.setAccessibleName(self.retry_button.text())


__all__ = ["CheckPage"]
