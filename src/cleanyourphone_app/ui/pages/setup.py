"""First-run ADB setup: consent, the official download and a manual picker.

ADB is never bundled. The download button stays disabled until the user accepts
Google's Android SDK terms, and downloading is the only network action the app
performs. A failed or altered archive leaves the page on screen and never runs
anything; only an accepted path reaches the rest of the app.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.services.downloads import DownloadError
from cleanyourphone_app.ui.pages.base import Page

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
        self._error_key: str | None = None
        self._build_ui()
        self.retranslate()

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

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.terms_label)
        layout.addWidget(self.consent_checkbox)
        layout.addLayout(buttons)
        layout.addWidget(self.offline_label)
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
        self.error_label.setText(self.tr(key))
        self.error_label.show()

    def _clear_error(self) -> None:
        self._error_key = None
        self.error_label.clear()
        self.error_label.hide()

    def download(self) -> None:
        """Download Google's Platform-Tools after explicit consent."""
        if self._busy or not self.consent_checkbox.isChecked():
            return

        self._set_busy(True)
        self._clear_error()
        progress = QProgressDialog(self.tr("setup.downloading"), "", 0, 0, self)
        progress.setWindowTitle(self.tr("setup.title"))
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        if self.isVisible():
            progress.show()
            QApplication.processEvents()

        try:
            adb_path = self.context.downloads.download(
                self.context.adb_locator.cache_dir
            )
        except DownloadError as exc:
            key = (
                "setup.hash_failed"
                if "sha-256" in str(exc).lower()
                else "setup.download_failed"
            )
            self._show_error(key)
            return
        except OSError:
            self._show_error("setup.download_failed")
            return
        finally:
            progress.close()
            self._set_busy(False)

        self.context.set_adb_path(adb_path)
        self._continue()

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

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.download_button.setAccessibleName(self.download_button.text())
        self.have_adb_button.setAccessibleName(self.have_adb_button.text())
        self.consent_checkbox.setAccessibleName(self.consent_checkbox.text())


__all__ = ["ANDROID_SDK_TERMS_URL", "SetupPage"]
