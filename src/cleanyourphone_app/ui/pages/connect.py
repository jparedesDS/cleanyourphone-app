"""Connect a phone over Wi-Fi (Android 11+) with a USB fallback.

The pairing code is read from the phone, handed to ``adb pair`` once and then
cleared from the field. It is never written to a page attribute, the session or
a log. Wi-Fi is the primary path for Android 11 and newer; USB works on every
supported version and stays available when pairing fails.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.session import SessionError, Transport
from cleanyourphone_app.services.adb import AdbInfo, DeviceEntry
from cleanyourphone_app.services.adb_wifi import (
    MdnsService,
    MdnsServices,
    WifiConnector,
    WifiError,
)
from cleanyourphone_app.ui.pages.base import Page
from cleanyourphone_app.ui.workers import BackgroundCall

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext

_CODE_PATTERN = re.compile(r"[0-9]{6}\Z")


def parse_endpoint(text: str) -> MdnsService | None:
    """Parse ``host:port`` from a pairing field, rejecting vague input."""
    if not isinstance(text, str):
        return None
    host, separator, port_text = text.strip().rpartition(":")
    if not separator or not host.strip() or not port_text.isdigit():
        return None
    port = int(port_text)
    if not 1 <= port <= 65535:
        return None
    return MdnsService(host=host.strip(), port=port)


def transport_for(device: DeviceEntry) -> Transport:
    """Map a parsed device row to the session transport."""
    try:
        return Transport(device.transport)
    except ValueError:
        if device.serial.startswith("adb-") or ":" in device.serial:
            return Transport.WIFI
        return Transport.USB


class ConnectPage(Page):
    """Pair over Wi-Fi or pick a USB device, then hand it to the check page."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._services: MdnsServices | None = None
        self._error_key: str | None = None
        self._success_key: str | None = None
        self._busy = False
        self._task: str | None = None
        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._task_succeeded)
        self._call.failed.connect(self._task_failed)
        self._call.finished.connect(self._task_finished)
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

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("ConnectTabs")
        self.tabs.addTab(self._build_wifi_tab(), "")
        self.tabs.addTab(self._build_usb_tab(), "")

        self.busy_label = QLabel(self)
        self.busy_label.setProperty("role", "muted")
        self.busy_label.setWordWrap(True)
        self.busy_label.hide()

        self.error_label = QLabel(self)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.success_label = QLabel(self)
        self.success_label.setProperty("role", "success")
        self.success_label.setWordWrap(True)
        self.success_label.hide()

        self.retry_button = QPushButton(self)
        self.retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_button.clicked.connect(self._retry)
        self.retry_button.hide()

        self.usb_fallback_button = QPushButton(self)
        self.usb_fallback_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.usb_fallback_button.clicked.connect(
            lambda checked=False: self.select_tab("usb")
        )
        self.usb_fallback_button.hide()

        failure_row = QHBoxLayout()
        failure_row.setContentsMargins(0, 0, 0, 0)
        failure_row.setSpacing(10)
        failure_row.addWidget(self.retry_button)
        failure_row.addWidget(self.usb_fallback_button)
        failure_row.addStretch(1)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.success_label)
        layout.addLayout(failure_row)

    def _build_wifi_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.wifi_steps_label = QLabel(tab)
        self.wifi_steps_label.setProperty("role", "body")
        self.wifi_steps_label.setWordWrap(True)

        self.ip_label = QLabel(tab)
        self.ip_field = QLineEdit(tab)
        self.ip_field.setObjectName("pairing_ip")
        self.ip_field.setPlaceholderText("192.168.1.42:37123")

        self.code_label = QLabel(tab)
        self.code_field = QLineEdit(tab)
        self.code_field.setObjectName("pairing_code")
        self.code_field.setMaxLength(6)
        self.code_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.code_field.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[0-9]{0,6}"), self)
        )

        self.discover_button = QPushButton(tab)
        self.discover_button.setObjectName("discover_button")
        self.discover_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discover_button.clicked.connect(self.discover)

        self.connect_button = QPushButton(tab)
        self.connect_button.setObjectName("connect_button")
        self.connect_button.setProperty("primary", True)
        self.connect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_button.clicked.connect(self._connect_wifi)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        buttons.addWidget(self.discover_button)
        buttons.addWidget(self.connect_button)
        buttons.addStretch(1)

        layout.addWidget(self.wifi_steps_label)
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_field)
        layout.addWidget(self.code_label)
        layout.addWidget(self.code_field)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return tab

    def _build_usb_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.usb_steps_label = QLabel(tab)
        self.usb_steps_label.setProperty("role", "body")
        self.usb_steps_label.setWordWrap(True)

        self.device_label = QLabel(tab)
        self.device_label.hide()

        self.device_combo = QComboBox(tab)
        self.device_combo.setObjectName("device_combo")
        self.device_combo.hide()

        self.usb_connect_button = QPushButton(tab)
        self.usb_connect_button.setObjectName("usb_connect_button")
        self.usb_connect_button.setProperty("primary", True)
        self.usb_connect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.usb_connect_button.clicked.connect(self._connect_usb)

        layout.addWidget(self.usb_steps_label)
        layout.addWidget(self.device_label)
        layout.addWidget(self.device_combo)
        layout.addWidget(self.usb_connect_button)
        layout.addStretch(1)
        return tab

    # ---------------------------------------------------------------- helpers

    def select_tab(self, mode: str) -> None:
        """Show the Wi-Fi (0) or USB (1) tab."""
        if mode == "usb":
            self.tabs.setCurrentIndex(1)
        elif mode == "wifi":
            self.tabs.setCurrentIndex(0)

    def _connector(self) -> WifiConnector | None:
        if self.context.wifi is not None:
            return self.context.wifi
        info = self.context.locate_adb()
        if info is None:
            return None
        connector = WifiConnector(info)
        self.context.wifi = connector
        return connector

    def _adb_info(self) -> AdbInfo | None:
        return self.context.adb_info or self.context.locate_adb()

    def _record(self, serial: str, transport: Transport) -> bool:
        try:
            self.context.session.attach(serial, transport)
        except (SessionError, ValueError, TypeError):
            self._show_error("connect.failed")
            return False
        return True

    def _show_error(self, key: str) -> None:
        self._error_key = key
        self._success_key = None
        self.error_label.setText(self.tr(key))
        self.error_label.show()
        self.success_label.hide()

    def _show_success(self, key: str) -> None:
        self._success_key = key
        self._error_key = None
        self.error_label.hide()
        self.success_label.setText(self.tr(key))
        self.success_label.show()

    def _show_failure_controls(self, *, usb_fallback: bool = True) -> None:
        self.retry_button.show()
        self.usb_fallback_button.setVisible(usb_fallback)

    def _hide_failure_controls(self) -> None:
        self.retry_button.hide()
        self.usb_fallback_button.hide()

    def _set_busy(self, task: str | None, busy: bool) -> None:
        self._busy = busy
        self._task = task if busy else None
        for widget in (
            self.ip_field,
            self.code_field,
            self.discover_button,
            self.connect_button,
            self.usb_connect_button,
            self.device_combo,
        ):
            widget.setEnabled(not busy)
        if busy:
            self._error_key = None
            self._success_key = None
            self.error_label.hide()
            self.success_label.hide()
            self.busy_label.setText(self.tr("common.loading"))
            self.busy_label.show()
        else:
            self.busy_label.hide()

    def _start_task(self, task: str, call: Callable[[], object]) -> None:
        if self._busy or self._call.active:
            return

        self._set_busy(task, True)
        if not self._call.start(call):
            self._set_busy(None, False)

    def _task_finished(self) -> None:
        self._set_busy(None, False)

    def _task_succeeded(self, result: object) -> None:
        if self._task == "discover":
            self._discovery_succeeded(result)
        elif self._task == "wifi_pair":
            self._pairing_succeeded(result)
        elif self._task == "usb":
            self._usb_succeeded(result)

    def _task_failed(self, error: object) -> None:
        if self._task == "usb":
            self._show_error("connect.failed")
            self._show_failure_controls(usb_fallback=False)
        elif self._task == "wifi_pair":
            self._show_error("connect.pairing_failed")
            self._show_failure_controls()
        else:
            self._show_error("connect.failed")
            self._show_failure_controls()

    # ---------------------------------------------------------------- actions

    def discover(self) -> None:
        """Ask ADB for the pairing and connect endpoints near this PC."""
        if self._busy:
            return
        connector = self._connector()
        if connector is None:
            self._show_error("connect.adb_missing")
            self._show_failure_controls()
            return

        self._start_task("discover", connector.discover)

    def _discovery_succeeded(self, services: object) -> None:
        if not isinstance(services, MdnsServices):
            self._show_error("connect.failed")
            self._show_failure_controls()
            return

        self._services = services
        endpoint = services.pairing or services.connect
        if endpoint is None:
            self._show_error("connect.no_devices")
            self._show_failure_controls()
            return

        self.ip_field.setText(str(endpoint))
        self._hide_failure_controls()
        self._show_success("connect.waiting")

    def _retry(self) -> None:
        if self.tabs.currentIndex() == 1:
            self._hide_failure_controls()
            self._connect_usb()
            return
        self._retry_pairing()

    def _retry_pairing(self) -> None:
        self.select_tab("wifi")
        self._hide_failure_controls()
        self.code_field.setFocus()

    def _connect_wifi(self) -> None:
        if self._busy:
            return
        code = self.code_field.text().strip()
        if _CODE_PATTERN.fullmatch(code) is None:
            self._show_error("connect.invalid_code")
            self._show_failure_controls()
            return

        address = self.ip_field.text().strip()
        pairing = parse_endpoint(address) if address else None
        if address and pairing is None:
            self._show_error("connect.invalid_address")
            self._show_failure_controls()
            return

        connector = self._connector()
        if connector is None:
            self._show_error("connect.adb_missing")
            self._show_failure_controls()
            return

        services = self._services
        handoff_code = code

        def call():
            found = services
            if found is None or found.connect is None:
                found = connector.discover()
            endpoint = pairing or found.pairing
            if endpoint is None or found.connect is None:
                raise WifiError("the pairing or connect endpoint was not found")
            serial = connector.pair_and_connect(
                handoff_code, endpoint, found.connect
            )
            return found, serial

        # The field is cleared at the handoff; only the worker closure holds the
        # code until adb pair returns, and the page never keeps or logs it.
        self.code_field.clear()
        self._start_task("wifi_pair", call)

    def _pairing_succeeded(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 2:
            self._show_error("connect.pairing_failed")
            self._show_failure_controls()
            return
        services, serial = result
        if (
            not isinstance(services, MdnsServices)
            or not isinstance(serial, str)
            or not serial.strip()
        ):
            self._show_error("connect.pairing_failed")
            self._show_failure_controls()
            return

        self._services = services
        if not self._record(serial, Transport.WIFI):
            self._show_failure_controls()
            return
        self._hide_failure_controls()
        self._show_success("connect.connected")
        self._go("check")

    def _connect_usb(self) -> None:
        if self._busy:
            return
        info = self._adb_info()
        if info is None:
            self._show_error("connect.adb_missing")
            self._show_failure_controls(usb_fallback=False)
            return

        self._start_task(
            "usb", lambda: list(self.context.device_lister(info))
        )

    def _usb_succeeded(self, entries: object) -> None:
        if not isinstance(entries, (list, tuple)):
            self._show_error("connect.failed")
            self._show_failure_controls(usb_fallback=False)
            return

        online = [entry for entry in entries if entry.state == "device"]
        if not online:
            self.device_label.hide()
            self.device_combo.hide()
            self._show_error("connect.no_devices")
            self._show_failure_controls(usb_fallback=False)
            return

        if len(online) == 1:
            chosen = online[0]
            self.device_label.hide()
            self.device_combo.hide()
        else:
            selected_serial = self.device_combo.currentData()
            chosen = next(
                (
                    entry
                    for entry in online
                    if selected_serial is not None
                    and entry.serial == selected_serial
                ),
                None,
            )
            if chosen is None:
                self._populate_devices(online)
                self.device_label.show()
                self.device_combo.show()
                self._show_error("connect.multiple_devices")
                return

        if not self._record(chosen.serial, transport_for(chosen)):
            self._show_failure_controls(usb_fallback=False)
            return
        self._hide_failure_controls()
        self._show_success("connect.connected")
        self._go("check")

    def _populate_devices(self, online: list[DeviceEntry]) -> None:
        previous = self.device_combo.currentData()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem(self.tr("connect.choose_device"), None)
        placeholder = self.device_combo.model().item(0)
        if placeholder is not None:
            placeholder.setEnabled(False)
        for entry in online:
            label = entry.model or entry.serial
            self.device_combo.addItem(
                f"{label} · {entry.transport.upper()}", entry.serial
            )
        self.device_combo.setCurrentIndex(0)
        if previous is not None:
            index = self.device_combo.findData(previous)
            if index > 0:
                self.device_combo.setCurrentIndex(index)
        self.device_combo.blockSignals(False)

    def shutdown(self) -> None:
        """Wait briefly for an active service call when the window is closing."""
        self._call.shutdown(5000)

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("connect.title"))
        self.body_label.setText(self.tr("connect.body"))
        self.tabs.setTabText(0, self.tr("connect.wifi_title"))
        self.tabs.setTabText(1, self.tr("connect.usb_title"))

        self.wifi_steps_label.setText(self.tr("connect.wifi_steps"))
        self.ip_label.setText(self.tr("connect.pairing_ip"))
        self.code_label.setText(self.tr("connect.pairing_code"))
        self.discover_button.setText(self.tr("connect.discover"))
        self.connect_button.setText(self.tr("connect.connect"))

        self.usb_steps_label.setText(self.tr("connect.usb_steps"))
        self.device_label.setText(self.tr("connect.choose_device"))
        self.usb_connect_button.setText(self.tr("connect.connect"))

        self.retry_button.setText(self.tr("connect.retry"))
        self.usb_fallback_button.setText(self.tr("connect.use_usb"))
        self.busy_label.setText(self.tr("common.loading"))
        if self._error_key is not None:
            self.error_label.setText(self.tr(self._error_key))
        if self._success_key is not None:
            self.success_label.setText(self.tr(self._success_key))
        if self.device_combo.count():
            self.device_combo.setItemText(0, self.tr("connect.choose_device"))

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.ip_field.setAccessibleName(self.ip_label.text())
        self.code_field.setAccessibleName(self.code_label.text())
        self.discover_button.setAccessibleName(self.discover_button.text())
        self.connect_button.setAccessibleName(self.connect_button.text())
        self.usb_connect_button.setAccessibleName(self.usb_connect_button.text())


__all__ = ["ConnectPage", "parse_endpoint", "transport_for"]
