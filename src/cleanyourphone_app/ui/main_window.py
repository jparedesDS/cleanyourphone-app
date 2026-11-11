"""The native window shell: header, step indicator, language switch and stack.

Feature pages are added later through :meth:`MainWindow.register_page`. Until
then each flow state has a small translated placeholder so the shell can be
built and tested on its own. The window always starts on ``welcome`` and the
language switch is part of the fixed header, so it is visible on every screen.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.apply import ApplySummary
from cleanyourphone_app.domain.session import SessionError
from cleanyourphone_app.services.adb import AdbError, AdbInfo, DeviceEntry
from cleanyourphone_app.services.logging import LOGGER_NAME
from cleanyourphone_app.services.updates import (
    UpdateCancelled,
    UpdateInfo,
    UpdateInstallError,
    default_update_dir,
    download_update,
    launch_update_helper,
)
from cleanyourphone_app.ui.dialogs import FeedbackDialog
from cleanyourphone_app.ui.pages.apply import ApplyPage
from cleanyourphone_app.ui.pages.backup import BackupPage
from cleanyourphone_app.ui.pages.blocked import SAFETY_DOCS_URL, BlockedPage
from cleanyourphone_app.ui.pages.check import CheckPage
from cleanyourphone_app.ui.pages.connect import ConnectPage, transport_for
from cleanyourphone_app.ui.pages.done import DonePage
from cleanyourphone_app.ui.pages.review import ReviewPage
from cleanyourphone_app.ui.pages.setup import SetupPage
from cleanyourphone_app.ui.pages.welcome import WelcomePage
from cleanyourphone_app.ui.workers import BackgroundCall
from cleanyourphone_app.version import __version__

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext

FLOW_PAGES: tuple[str, ...] = (
    "welcome",
    "connect",
    "check",
    "backup",
    "review",
    "apply",
    "done",
)

PAGE_NAMES: tuple[str, ...] = (*FLOW_PAGES, "blocked", "error", "setup")

PAGE_ALIASES: dict[str, str] = {
    "connecting": "connect",
    "checking": "check",
    "applying": "apply",
}

STEP_FOR_PAGE: dict[str, str] = {
    "welcome": "welcome",
    "connect": "connect",
    "check": "check",
    "backup": "backup",
    "review": "review",
    "apply": "apply",
    "done": "done",
    "setup": "welcome",
}

_LOGO_PATH = Path(__file__).resolve().parents[1] / "resources" / "logo.svg"


class _PlaceholderPage(QWidget):
    """Translated stand-in until the real feature page is registered."""

    def __init__(self, name: str, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self._context = context
        self.setObjectName(name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 44)
        layout.setSpacing(18)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.hint_label = QLabel(self)
        self.hint_label.setProperty("role", "muted")
        self.hint_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        if name == "welcome":
            layout.addWidget(self.hint_label)
        layout.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        tr = self._context.translator.tr
        title = tr(f"{self._name}.title")
        body = tr(f"{self._name}.body")
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.title_label.setAccessibleName(title)
        self.body_label.setAccessibleName(body)
        if self._name == "welcome":
            self.hint_label.setText(tr("welcome.hint"))


class MainWindow(QMainWindow):
    """One native window with a fixed header and a replaceable page stack."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self._pages: dict[str, QWidget] = {}
        self._current_step = "welcome"
        self._real_pages = False
        self.setup_page: SetupPage | None = None
        self.welcome_page: WelcomePage | None = None
        self.connect_page: ConnectPage | None = None
        self.check_page: CheckPage | None = None
        self.backup_page: BackupPage | None = None
        self.review_page: ReviewPage | None = None
        self.apply_page: ApplyPage | None = None
        self.done_page: DonePage | None = None
        self.blocked_page: BlockedPage | None = None

        self.setObjectName("MainWindow")
        self.setMinimumSize(900, 640)
        self.resize(980, 700)

        self._pending_update: UpdateInfo | None = None
        self._update_check_manual = False
        self._update_cancel = threading.Event()
        self._update_progress: QProgressDialog | None = None
        self._update_call = BackgroundCall(self)
        self._update_call.succeeded.connect(self._update_succeeded)
        self._update_call.failed.connect(self._update_failed)
        self._update_call.finished.connect(self._update_finished)
        self._download_call = BackgroundCall(self)
        self._download_call.succeeded.connect(self._download_succeeded)
        self._download_call.failed.connect(self._download_failed)
        self._download_call.finished.connect(self._download_finished)

        self._build_ui()
        self._register_default_pages()
        self._load_theme()
        self.retranslate()
        self.show_page("welcome")
        QTimer.singleShot(1500, self._maybe_check_updates)

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("Root")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QFrame(central)
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 16, 28, 14)
        header_layout.setSpacing(14)

        self.logo_label = QLabel(header)
        self.logo_label.setObjectName("Logo")
        self.logo_label.setFixedSize(38, 38)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QIcon(str(_LOGO_PATH))
        if icon.isNull():
            self.logo_label.setText("C")
            self.logo_label.setProperty("role", "brand")
        else:
            self.setWindowIcon(icon)
            self.logo_label.setPixmap(icon.pixmap(34, 34))

        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(1)
        self.app_name_label = QLabel(header)
        self.app_name_label.setProperty("role", "brand")
        self.tagline_label = QLabel(header)
        self.tagline_label.setProperty("role", "muted")
        brand_layout.addWidget(self.app_name_label)
        brand_layout.addWidget(self.tagline_label)

        self.language_switch = QWidget(header)
        self.language_switch.setObjectName("LanguageSwitch")
        switch_layout = QHBoxLayout(self.language_switch)
        switch_layout.setContentsMargins(0, 0, 0, 0)
        switch_layout.setSpacing(5)

        self.language_label = QLabel(self.language_switch)
        self.language_label.setProperty("role", "muted")
        switch_layout.addWidget(self.language_label)

        self._language_group = QButtonGroup(self)
        self._language_group.setExclusive(True)
        self.language_buttons: dict[str, QPushButton] = {}
        for code in ("es", "en"):
            button = QPushButton(self.language_switch)
            button.setObjectName(f"language_{code}")
            button.setProperty("role", "language")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, language=code: self.set_language(language)
            )
            self._language_group.addButton(button)
            self.language_buttons[code] = button
            switch_layout.addWidget(button)

        self.update_button = QPushButton(header)
        self.update_button.setObjectName("update_button")
        self.update_button.setProperty("role", "language")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.setAutoDefault(False)
        self.update_button.clicked.connect(
            lambda checked=False: self._check_updates(manual=True)
        )

        self.feedback_button = QPushButton(header)
        self.feedback_button.setObjectName("feedback_button")
        self.feedback_button.setProperty("role", "language")
        self.feedback_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.feedback_button.setAutoDefault(False)
        self.feedback_button.clicked.connect(self._open_feedback)

        header_layout.addWidget(self.logo_label)
        header_layout.addLayout(brand_layout)
        header_layout.addStretch(1)
        header_layout.addWidget(self.update_button)
        header_layout.addWidget(self.feedback_button)
        header_layout.addWidget(self.language_switch)
        root_layout.addWidget(header)

        self.update_banner = QFrame(central)
        self.update_banner.setObjectName("UpdateBanner")
        self.update_banner.hide()
        update_layout = QHBoxLayout(self.update_banner)
        update_layout.setContentsMargins(28, 8, 28, 8)
        update_layout.setSpacing(10)

        self.update_banner_label = QLabel(self.update_banner)
        self.update_banner_label.setProperty("role", "body")
        self.update_banner_label.setWordWrap(True)

        self.update_open_button = QPushButton(self.update_banner)
        self.update_open_button.setObjectName("update_open_button")
        self.update_open_button.setProperty("primary", True)
        self.update_open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_open_button.setAutoDefault(False)
        self.update_open_button.clicked.connect(self._open_update)

        self.update_later_button = QPushButton(self.update_banner)
        self.update_later_button.setObjectName("update_later_button")
        self.update_later_button.setProperty("role", "language")
        self.update_later_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_later_button.setAutoDefault(False)
        self.update_later_button.clicked.connect(self._dismiss_update)

        update_layout.addWidget(self.update_banner_label, 1)
        update_layout.addWidget(self.update_open_button)
        update_layout.addWidget(self.update_later_button)
        root_layout.addWidget(self.update_banner)

        step_bar = QFrame(central)
        step_bar.setObjectName("StepBar")
        step_layout = QHBoxLayout(step_bar)
        step_layout.setContentsMargins(28, 9, 28, 9)
        step_layout.setSpacing(6)

        self.step_labels: dict[str, QLabel] = {}
        for step in FLOW_PAGES:
            label = QLabel(step_bar)
            label.setObjectName(f"step_{step}")
            label.setProperty("role", "step")
            label.setProperty("current", step == "welcome")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.step_labels[step] = label
            step_layout.addWidget(label, 1)
        root_layout.addWidget(step_bar)

        self.stack = QStackedWidget(central)
        self.stack.setObjectName("PageStack")
        root_layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        self.statusBar().setObjectName("AppStatusBar")
        self.statusBar().setSizeGripEnabled(False)

    def _register_default_pages(self) -> None:
        for name in PAGE_NAMES:
            self.register_page(name, _PlaceholderPage(name, self.context))

    def _ensure_real_pages(self) -> None:
        """Register the first-run pages once, replacing their placeholders."""
        if self._real_pages:
            return

        self.welcome_page = WelcomePage(self.context)
        self.welcome_page.transport_selected.connect(self._open_connect)
        self.register_page("welcome", self.welcome_page)

        self.connect_page = ConnectPage(self.context)
        self.register_page("connect", self.connect_page)

        self.check_page = CheckPage(self.context)
        self.register_page("check", self.check_page)

        self.backup_page = BackupPage(self.context)
        self.register_page("backup", self.backup_page)

        self.review_page = ReviewPage(
            self.context, catalog=self.context.package_catalog
        )
        self.register_page("review", self.review_page)

        self.apply_page = ApplyPage(self.context)
        self.apply_page.completed.connect(self._present_done)
        self.review_page.ads_selected.connect(self.apply_page.set_ads_provider)
        self.register_page("apply", self.apply_page)

        self.done_page = DonePage(self.context)
        self.register_page("done", self.done_page)

        self.blocked_page = BlockedPage(self.context)
        self.blocked_page.restart_requested.connect(self._restart_after_block)
        self.register_page("blocked", self.blocked_page)

        self.setup_page = SetupPage(self.context, on_ready=self.start_flow)
        self.register_page("setup", self.setup_page)
        self._real_pages = True

    def _open_connect(self, mode: str) -> None:
        if self.connect_page is None:
            return
        self.connect_page.select_tab(mode)
        self.show_page("connect")

    def _open_feedback(self, checked: bool = False) -> None:
        """Open the opt-in feedback form; nothing is sent until Send."""
        dialog = FeedbackDialog(self.context, self)
        dialog.exec()

    # ------------------------------------------------------------- updates

    def _maybe_check_updates(self) -> None:
        """Check at most once every six hours, without blocking the window."""
        if self._update_call.active or self._pending_update is not None:
            return
        now = int(time.time())
        if now - self.context.settings.last_update_check < 6 * 60 * 60:
            return
        self._check_updates(manual=False)

    def _check_updates(self, *, manual: bool) -> None:
        if self._update_call.active:
            return
        self._update_check_manual = manual
        self.context.settings.last_update_check = int(time.time())
        try:
            self.context.settings.save()
        except OSError:
            logging.getLogger(LOGGER_NAME).warning(
                "could not save the last update check"
            )
        self.update_button.setEnabled(False)
        self.update_button.setText(self.context.translator.tr("update.checking"))
        started = self._update_call.start(
            lambda: self.context.update_checker(__version__)
        )
        if not started:
            self._update_finished()
            if manual:
                self.statusBar().showMessage(
                    self.context.translator.tr("update.failed"), 5000
                )

    def _update_succeeded(self, result: object) -> None:
        if not isinstance(result, UpdateInfo):
            if self._update_check_manual:
                self.statusBar().showMessage(
                    self.context.translator.tr("update.up_to_date"), 5000
                )
            return
        self._pending_update = result
        tr = self.context.translator.tr
        self.update_banner_label.setText(
            tr("update.available").format(version=result.version)
        )
        self.update_open_button.setText(
            tr("update.install") if result.can_install else tr("update.open")
        )
        self.update_later_button.setText(tr("update.later"))
        self.update_banner.show()

    def _update_failed(self, error: object) -> None:
        logging.getLogger(LOGGER_NAME).warning("update check failed: %s", error)
        if self._update_check_manual:
            self.statusBar().showMessage(
                self.context.translator.tr("update.failed"), 6000
            )

    def _update_finished(self) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText(self.context.translator.tr("update.check"))

    def _open_update(self, checked: bool = False) -> None:
        """Offer the update; only a frozen install can download and run it."""
        info = self._pending_update
        if info is None:
            return
        tr = self.context.translator.tr
        if not info.can_install or not getattr(sys, "frozen", False):
            QDesktopServices.openUrl(QUrl(info.url))
            return
        if self._writes_in_flight():
            QMessageBox.information(self, tr("update.check"), tr("update.busy"))
            return

        box = QMessageBox(self)
        box.setWindowTitle(tr("update.check"))
        box.setText(tr("update.confirm").format(version=info.version))
        install_button = box.addButton(
            tr("update.install"), QMessageBox.ButtonRole.AcceptRole
        )
        open_button = box.addButton(
            tr("update.open"), QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(tr("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is install_button:
            self._start_update_download(info)
        elif box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl(info.url))

    def _start_update_download(self, info: UpdateInfo) -> None:
        tr = self.context.translator.tr
        self._update_cancel.clear()
        self._update_progress = QProgressDialog(
            tr("update.downloading"),
            tr("common.cancel"),
            0,
            0,
            self,
        )
        self._update_progress.setWindowTitle(tr("update.check"))
        self._update_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._update_progress.setMinimumDuration(0)
        self._update_progress.canceled.connect(self._cancel_update_download)
        self._update_progress.show()
        started = self._download_call.start(
            lambda: download_update(
                info,
                default_update_dir(),
                cancel=self._update_cancel.is_set,
            )
        )
        if not started:
            self._close_update_progress()
            QMessageBox.warning(
                self, tr("update.check"), tr("update.failed_download")
            )

    def _cancel_update_download(self) -> None:
        self._update_cancel.set()

    def _download_succeeded(self, result: object) -> None:
        self._close_update_progress()
        if not isinstance(result, Path):
            return
        tr = self.context.translator.tr
        try:
            launch_update_helper(
                result,
                sys.executable,
                pid=os.getpid(),
                directory=result.parent,
            )
        except UpdateInstallError as exc:
            logging.getLogger(LOGGER_NAME).warning("could not start update: %s", exc)
            QMessageBox.warning(
                self, tr("update.check"), tr("update.failed_download")
            )
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _download_failed(self, error: object) -> None:
        self._close_update_progress()
        tr = self.context.translator.tr
        if isinstance(error, UpdateCancelled):
            self.statusBar().showMessage(tr("update.cancelled"), 5000)
            return
        logging.getLogger(LOGGER_NAME).warning("update download failed: %s", error)
        QMessageBox.warning(self, tr("update.check"), tr("update.failed_download"))

    def _download_finished(self) -> None:
        self._close_update_progress()

    def _close_update_progress(self) -> None:
        progress = self._update_progress
        self._update_progress = None
        if progress is not None:
            progress.close()
            progress.deleteLater()

    def _dismiss_update(self, checked: bool = False) -> None:
        self.update_banner.hide()

    def start_flow(self) -> str:
        """Choose setup, check or welcome from the ADB and device state.

        Called by :func:`cleanyourphone_app.ui.app.run` and again when the setup
        page finishes. Device discovery is best effort: a listing failure never
        stops the app from reaching the welcome screen.
        """
        self._ensure_real_pages()

        info = self.context.locate_adb()
        if info is None:
            return self.show_page("setup")

        device = self._single_online_device(info)
        if device is not None:
            try:
                self.context.session.attach(device.serial, transport_for(device))
                self.context.cli.set_serial(device.serial)
            except (SessionError, ValueError, TypeError):
                logging.getLogger(LOGGER_NAME).warning(
                    "could not pin the only online device at startup"
                )
            else:
                return self.show_page("check")

        return self.show_page("welcome")

    def _single_online_device(self, info: AdbInfo) -> DeviceEntry | None:
        try:
            entries = self.context.device_lister(info)
        except (AdbError, OSError):
            logging.getLogger(LOGGER_NAME).warning(
                "could not list devices while starting the flow"
            )
            return None
        if not isinstance(entries, (list, tuple)):
            return None
        online = [entry for entry in entries if entry.state == "device"]
        return online[0] if len(online) == 1 else None

    def _load_theme(self) -> None:
        theme = Path(__file__).with_name("theme.qss").read_text(encoding="utf-8")
        self.setStyleSheet(theme)

    # --------------------------------------------------------------- pages

    @staticmethod
    def _canonical(name: str) -> str:
        return PAGE_ALIASES.get(name, name)

    def register_page(self, name: str, page: QWidget) -> None:
        """Add or replace a page in the stack, preserving the current page."""
        canonical = self._canonical(name)
        page.setObjectName(canonical)
        previous = self._pages.get(canonical)
        was_current = previous is not None and self.stack.currentWidget() is previous
        if previous is not None:
            self.stack.removeWidget(previous)
            previous.deleteLater()

        self._pages[canonical] = page
        self.stack.addWidget(page)
        if was_current:
            self.stack.setCurrentWidget(page)

        navigate = getattr(page, "navigate", None)
        if navigate is not None and hasattr(navigate, "connect"):
            navigate.connect(self.show_page)

        retranslate = getattr(page, "retranslate", None)
        if callable(retranslate):
            retranslate()

    def show_page(self, name: str) -> str:
        """Show *name* and return its canonical page name."""
        canonical = self._canonical(name)
        page = self._pages.get(canonical)
        if page is None:
            raise KeyError(
                f"unknown page {name!r}; register it before navigating to it"
            )
        self.stack.setCurrentWidget(page)
        if canonical == "blocked":
            reason = self.context.session.blocked_reason
            link = self.context.session.blocked_link
            if link is None and reason is not None:
                link = SAFETY_DOCS_URL
            self._show_blocked(reason, link)
        step = STEP_FOR_PAGE.get(canonical)
        if step is not None:
            self._set_current_step(step)
        return canonical

    def _show_blocked(self, reason: str | None, link: str | None) -> None:
        page = self.blocked_page
        if page is None or self._pages.get("blocked") is not page:
            return
        page.show_blocked(reason, link)

    def _restart_after_block(self) -> None:
        """Throw away the blocked session before returning to Welcome."""
        try:
            self.context.session.reset()
            self.context.cli.set_serial(None)
        except (SessionError, ValueError, TypeError):
            logging.getLogger(LOGGER_NAME).warning(
                "could not reset the blocked session"
            )
            return
        if self.check_page is not None:
            self.check_page.reset()
        for page in (
            self.backup_page,
            self.review_page,
            self.apply_page,
            self.done_page,
        ):
            reset = getattr(page, "reset", None)
            if callable(reset):
                reset()

    def _present_done(self, summary: object) -> None:
        """Show the summary; the benchmark result travels inside it."""
        if not isinstance(summary, ApplySummary) or self.done_page is None:
            return
        self.done_page.show_summary(summary)

    @property
    def current_page_name(self) -> str:
        page = self.stack.currentWidget()
        return page.objectName() if page is not None else ""

    @property
    def current_step(self) -> str:
        return self._current_step

    def _set_current_step(self, step: str) -> None:
        self._current_step = step
        for name, label in self.step_labels.items():
            active = name == step
            if label.property("current") == active:
                continue
            label.setProperty("current", active)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

    # ------------------------------------------------------------ language

    def set_language(self, language: str) -> None:
        """Switch language, persist the choice and retranslate the shell."""
        normalized = self.context.translator.set_language(language)
        self.context.settings.language = normalized
        try:
            self.context.settings.save()
        except OSError:
            logging.getLogger(LOGGER_NAME).warning(
                "could not save the language setting"
            )
        self.retranslate()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._writes_in_flight():
            self.statusBar().showMessage(
                self.context.translator.tr("apply.do_not_close")
            )
            event.ignore()
            return

        if self._download_call.active:
            self._update_cancel.set()
            self._download_call.shutdown(2000)
        self._update_call.shutdown(2000)
        for page in (
            self.setup_page,
            self.connect_page,
            self.check_page,
            self.backup_page,
            self.review_page,
            self.apply_page,
            self.done_page,
        ):
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                shutdown()
        super().closeEvent(event)

    def _writes_in_flight(self) -> bool:
        return bool(
            (self.apply_page is not None and self.apply_page.close_blocked)
            or (self.done_page is not None and self.done_page.close_blocked)
        )

    def retranslate(self) -> None:
        tr = self.context.translator.tr
        self.setWindowTitle(tr("app.name"))
        self.app_name_label.setText(tr("app.name"))
        self.tagline_label.setText(tr("app.tagline"))
        self.feedback_button.setText(tr("feedback.open"))
        self.feedback_button.setAccessibleName(tr("feedback.open"))
        self.update_button.setText(
            tr("update.checking") if self._update_call.active else tr("update.check")
        )
        self.update_button.setToolTip(tr("update.check"))
        self.update_button.setAccessibleName(tr("update.check"))
        self.update_later_button.setText(tr("update.later"))
        if self._pending_update is not None:
            self.update_open_button.setText(
                tr("update.install")
                if self._pending_update.can_install
                else tr("update.open")
            )
            self.update_banner_label.setText(
                tr("update.available").format(version=self._pending_update.version)
            )
        else:
            self.update_open_button.setText(tr("update.open"))
        self.language_label.setText(tr("common.language"))
        self.language_switch.setAccessibleName(tr("common.language"))

        for step, label in self.step_labels.items():
            text = tr(f"step.{step}")
            label.setText(text)
            label.setAccessibleName(text)

        for code, button in self.language_buttons.items():
            button.setText(code.upper())
            if code == "es":
                button.setToolTip(tr("language.switch_to_spanish"))
            else:
                button.setToolTip(tr("language.switch_to_english"))
            button.setAccessibleName(button.toolTip())
            button.setChecked(self.context.translator.language == code)

        for page in self._pages.values():
            retranslate = getattr(page, "retranslate", None)
            if callable(retranslate):
                retranslate()

        self.statusBar().showMessage(tr("app.local_only"))


__all__ = ["FLOW_PAGES", "PAGE_NAMES", "MainWindow"]
