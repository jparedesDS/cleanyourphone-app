"""First-run ADB setup: consent, the official download and a manual picker.

ADB is never bundled. The download button stays disabled until the user accepts
Google's Android SDK terms, and downloading is the only network action the app
performs. A failed or altered archive leaves the page on screen and never runs
anything; only an accepted path reaches the rest of the app.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.services.downloads import DownloadCancelled, DownloadError
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext

ANDROID_SDK_TERMS_URL = "https://developer.android.com/studio/terms"

_ADB_FILTER = "adb.exe (adb.exe);;All files (*)"


class SetupPage(Page):
    """Explain why ADB is needed and install or locate it safely."""

    def __init__(
        self,
        context: AppContext,
        on_ready: Callable[[], str | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(context, parent)
        self._on_ready = on_ready
        self._busy = False
        self._cancel_requested = False
        self._error_key: str | None = None
        self._status_key: str | None = None
        self._cancel_event = threading.Event()
        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._download_succeeded)
        self._call.failed.connect(self._download_failed)
        self._call.finished.connect(self._download_finished)
        self.download_progress: QProgressDialog | None = None
        self._build_ui()
        self.retranslate()

    @property
    def busy(self) -> bool:
        return self._busy

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 44)
        layout.setSpacing(16)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.terms_label = QLabel(self)
        self.terms_label.setWordWrap(True)
        self.terms_label.setTextFormat(Qt.TextFormat.RichText)
        self.terms_label.setOpenExternalLinks(True)
        self.terms_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )

        self.consent_checkbox = QCheckBox(self)
        self.consent_checkbox.toggled.connect(self._update_download_enabled)

        self.download_button = QPushButton(self)
        self.download_button.setProperty("primary", True)
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_button.clicked.connect(self.download)

        self.have_adb_button = QPushButton(self)
        self.have_adb_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.have_adb_button.clicked.connect(self.choose_adb)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.have_adb_button)
        buttons.addStretch(1)

        self.offline_label = QLabel(self)
        self.offline_label.setProperty("role", "muted")
        self.offline_label.setWordWrap(True)

        self.status_label = QLabel(self)
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        self.status_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        for label in (
            self.body_label,
            self.terms_label,
            self.offline_label,
            self.status_label,
            self.error_label,
        ):
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.terms_label)
        layout.addWidget(self.consent_checkbox)
        layout.addLayout(buttons)
        layout.addWidget(self.offline_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.error_label)
        layout.addStretch(1)

        self._update_download_enabled()

    # ---------------------------------------------------------------- actions

    def _update_download_enabled(self, checked: bool | None = None) -> None:
        enabled = bool(self.consent_checkbox.isChecked()) and not self._busy
        self.download_button.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.consent_checkbox.setEnabled(not busy)
        self.have_adb_button.setEnabled(not busy)
        self._update_download_enabled()

    def _show_error(self, key: str) -> None:
        self._error_key = key
        self._status_key = None
        self.error_label.setText(self.tr(key))
        self.error_label.show()
        self.status_label.hide()

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()

    def _show_status(self, key: str) -> None:
        self._status_key = key
        self._error_key = None
        self.status_label.setText(self.tr(key))
        self.status_label.show()
        self.error_label.hide()

    def _clear_status(self) -> None:
        self._status_key = None
        self.status_label.clear()
        self.status_label.hide()

    def _close_progress(self) -> None:
        progress = self.download_progress
        self.download_progress = None
        if progress is not None:
            try:
                progress.canceled.disconnect(self.cancel_download)
            except (RuntimeError, TypeError):
                pass
            progress.close()
            progress.deleteLater()

    def download(self) -> None:
        """Download Google's Platform-Tools after explicit consent.

        The network and extraction calls run on a worker thread; the progress
        dialog stays responsive and its Cancel action requests interruption.
        """
        if self._busy or not self.consent_checkbox.isChecked():
            return
        if self._call.active:
            return

        self._set_busy(True)
        self._cancel_requested = False
        self._cancel_event.clear()
        self._clear_error()
        self._clear_status()
        progress = QProgressDialog(
            self.tr("setup.downloading"), self.tr("common.cancel"), 0, 0, self
        )
        progress.setWindowTitle(self.tr("setup.title"))
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.canceled.connect(self.cancel_download)
        self.download_progress = progress
        if self.isVisible():
            progress.show()

        downloader = self.context.downloads
        destination = self.context.adb_locator.cache_dir
        started = self._call.start(
            lambda: downloader.download(
                destination, cancel=self._cancel_event.is_set
            )
        )
        if not started:
            self._close_progress()
            self._set_busy(False)

    def cancel_download(self) -> None:
        """Ask the download worker to stop between chunks."""
        if not self._call.active:
            return
        self._cancel_requested = True
        self._cancel_event.set()
        if self.download_progress is not None:
            self.download_progress.setLabelText(self.tr("setup.cancelling"))
            self.download_progress.setCancelButton(None)

    def _download_succeeded(self, adb_path: object) -> None:
        self._close_progress()
        if self._cancel_requested:
            self._show_status("setup.download_cancelled")
            return
        if not isinstance(adb_path, (str, os.PathLike)):
            self._show_error("setup.download_failed")
            return
        self.context.set_adb_path(adb_path)
        self._continue()

    def _download_failed(self, error: object) -> None:
        self._close_progress()
        if isinstance(error, DownloadCancelled) or self._cancel_requested:
            self._show_status("setup.download_cancelled")
            return
        if isinstance(error, DownloadError) and "sha-256" in str(error).lower():
            self._show_error("setup.hash_failed")
            return
        self._show_error("setup.download_failed")

    def _download_finished(self) -> None:
        self._close_progress()
        self._set_busy(False)

    def shutdown(self) -> None:
        """Stop a running download when the window is closing."""
        self._cancel_requested = True
        self._cancel_event.set()
        self._call.shutdown(5000)

    def choose_adb(self) -> None:
        """Let the user point at an existing adb.exe and verify its version."""
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.tr("setup.select_adb"),
            "",
            _ADB_FILTER,
        )
        if not filename:
            return

        info = self.context.adb_locator.accept(filename)
        if info is None:
            self._show_error("setup.invalid_adb")
            return

        self._clear_error()
        self.context.use_adb(info)
        self._continue()

    def _continue(self) -> None:
        target = "welcome"
        if self._on_ready is not None:
            target = self._on_ready() or target
        self._go(target)

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("setup.title"))
        self.body_label.setText(self.tr("setup.body"))
        self.terms_label.setText(
            f"{self.tr('setup.terms')} "
            f'<a href="{ANDROID_SDK_TERMS_URL}" style="color:#A78BFA;">'
            f"{self.tr('setup.terms_link')}</a>"
        )
        self.consent_checkbox.setText(self.tr("setup.consent"))
        self.download_button.setText(self.tr("setup.download"))
        self.have_adb_button.setText(self.tr("setup.have_adb"))
        self.offline_label.setText(self.tr("setup.offline"))
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))
        if self._status_key is not None:
            self.status_label.setText(self.tr(self._status_key))

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.download_button.setAccessibleName(self.download_button.text())
        self.have_adb_button.setAccessibleName(self.have_adb_button.text())
        self.consent_checkbox.setAccessibleName(self.consent_checkbox.text())
        if self.download_progress is not None:
            key = "setup.cancelling" if self._cancel_requested else "setup.downloading"
            self.download_progress.setLabelText(self.tr(key))


__all__ = ["ANDROID_SDK_TERMS_URL", "SetupPage"]
