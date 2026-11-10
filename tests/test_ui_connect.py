"""Welcome and connection pages: Wi-Fi pairing, USB fallback and auto-skip."""

import logging
import threading
from pathlib import Path

from cleanyourphone_app.domain.session import SessionState, Transport
from cleanyourphone_app.domain.support import CONNECT_GUIDE_URL
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import AdbError, AdbInfo, DeviceEntry
from cleanyourphone_app.services.adb_wifi import MdnsService, MdnsServices, WifiError
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.main_window import MainWindow
from cleanyourphone_app.ui.pages.connect import ConnectPage
from cleanyourphone_app.ui.pages.welcome import WelcomePage

PAIRING = MdnsService("192.168.1.42", 37123)
CONNECT = MdnsService("192.168.1.42", 37099)
WIFI_SERIAL = "adb-ABC._adb-tls-connect._tcp."
USB_DEVICE = DeviceEntry(
    serial="usb-1", state="device", model="Pixel_8", transport="usb"
)


class FakeLocator:
    def __init__(self, *, info=None, accepted=None, cache_dir="C:/cache"):
        self.info = info
        self.accepted = dict(accepted or {})
        self.cache_dir = cache_dir
        self.find_calls = 0
        self.accept_calls = []

    def find(self):
        self.find_calls += 1
        return self.info

    def accept(self, path):
        candidate = Path(path)
        self.accept_calls.append(candidate)
        return self.accepted.get(candidate)


class DeviceLister:
    def __init__(self, entries=(), error=None, *, started=None, release=None):
        self.entries = list(entries)
        self.error = error
        self.calls = []
        self.started = started
        self.release = release

    def __call__(self, info):
        self.calls.append(info)
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            self.release.wait(2)
        if self.error is not None:
            raise self.error
        return list(self.entries)


class FakeWifi:
    """Duck-typed WifiConnector that records the pair request."""

    def __init__(
        self,
        *,
        services=None,
        serial=WIFI_SERIAL,
        error=None,
        discover_started=None,
        discover_release=None,
        pair_started=None,
        pair_release=None,
    ):
        self.services = services or MdnsServices(pairing=PAIRING, connect=CONNECT)
        self.serial = serial
        self.error = error
        self.discover_calls = 0
        self.pair_calls = []
        self._discover_started = discover_started
        self._discover_release = discover_release
        self._pair_started = pair_started
        self._pair_release = pair_release

    def discover(self):
        self.discover_calls += 1
        if self._discover_started is not None:
            self._discover_started.set()
        if self._discover_release is not None:
            self._discover_release.wait(2)
        return self.services

    def pair_and_connect(self, code, pairing, connect):
        self.pair_calls.append((code, pairing, connect))
        if self._pair_started is not None:
            self._pair_started.set()
        if self._pair_release is not None:
            self._pair_release.wait(2)
        if self.error is not None:
            raise self.error
        return self.serial


def make_info(path="C:/tools/adb.exe"):
    return AdbInfo(
        path=Path(path), version=(37, 0, 1), version_text="Version 37.0.1"
    )


def make_context(tmp_path, *, wifi=None, lister=None, info=None, **overrides):
    info = info if info is not None else make_info()
    lister = lister if lister is not None else DeviceLister()
    values = {
        "translator": Translator("es"),
        "adb_locator": FakeLocator(info=info, cache_dir=tmp_path),
        "wifi": wifi,
        "device_lister": lister,
        "adb_path": None,
        "adb_info": None,
    }
    values.update(overrides)
    context = AppContext.fake(**values)
    return context, lister


def settle(qtbot, page):
    """Wait until the page's worker thread has fully stopped."""
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)


def make_window(qtbot, tmp_path, *, wifi=None, lister=None, info=None):
    context, lister = make_context(
        tmp_path, wifi=wifi, lister=lister, info=info
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.start_flow()
    return window, context, lister


# ---------------------------------------------------------------------------
# Welcome
# ---------------------------------------------------------------------------


def test_welcome_shows_wifi_and_usb(qtbot, tmp_path):
    context, _ = make_context(tmp_path)
    page = WelcomePage(context)
    qtbot.addWidget(page)

    assert page.wifi_button.text() == "Wi-Fi"
    assert page.wifi_button.text() == context.translator.tr("welcome.wifi")
    assert page.usb_button.text() == "USB"
    assert page.usb_button.text() == context.translator.tr("welcome.usb")
    assert page.title_label.text() == context.translator.tr("welcome.title")


def test_wifi_choice_opens_the_pairing_form(qtbot, tmp_path):
    window, context, _ = make_window(qtbot, tmp_path, wifi=FakeWifi())
    assert window.current_page_name == "welcome"

    window.welcome_page.wifi_button.click()

    page = window.connect_page
    assert window.current_page_name == "connect"
    assert page.tabs.currentIndex() == 0
    assert page.ip_field is not None
    assert page.code_field is not None
    assert page.code_field.maxLength() == 6
    assert page.discover_button.text() == "Buscar automáticamente"
    assert page.discover_button.text() == context.translator.tr("connect.discover")
    assert CONNECT_GUIDE_URL in page.help_label.text()
    assert context.translator.tr("connect.help") in page.help_label.text()
    assert page.help_label.openExternalLinks() is True


def test_usb_choice_opens_the_usb_instructions(qtbot, tmp_path):
    window, context, _ = make_window(qtbot, tmp_path, wifi=FakeWifi())

    window.welcome_page.usb_button.click()

    page = window.connect_page
    assert window.current_page_name == "connect"
    assert page.tabs.currentIndex() == 1
    assert page.usb_steps_label.text() == context.translator.tr("connect.usb_steps")
    assert page.usb_steps_label.text().count("USB") >= 1


# ---------------------------------------------------------------------------
# Wi-Fi discovery and pairing
# ---------------------------------------------------------------------------


def test_discovery_fills_the_pairing_address(qtbot, tmp_path):
    wifi = FakeWifi()
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.discover_button.click()
    qtbot.waitUntil(lambda: page.ip_field.text() != "", timeout=3000)
    settle(qtbot, page)

    assert wifi.discover_calls == 1
    assert page.ip_field.text() == "192.168.1.42:37123"
    assert page.code_field.text() == ""


def test_discovery_runs_in_a_worker_and_disables_actions(qtbot, tmp_path):
    started = threading.Event()
    release = threading.Event()
    wifi = FakeWifi(discover_started=started, discover_release=release)
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.discover_button.click()
    qtbot.waitUntil(started.is_set, timeout=3000)

    assert page.busy is True
    assert page.busy_label.isVisibleTo(page) is True
    assert page.discover_button.isEnabled() is False
    assert page.connect_button.isEnabled() is False
    assert page.ip_field.isEnabled() is False

    release.set()
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert page.ip_field.text() == "192.168.1.42:37123"


def test_pairing_runs_in_a_worker_and_clears_the_code_at_handoff(qtbot, tmp_path):
    started = threading.Event()
    release = threading.Event()
    wifi = FakeWifi(pair_started=started, pair_release=release)
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.ip_field.setText("192.168.1.42:37123")
    page.code_field.setText("482913")
    page.connect_button.click()
    qtbot.waitUntil(started.is_set, timeout=3000)
    assert page.busy is True
    assert page.code_field.text() == ""
    assert page.connect_button.isEnabled() is False
    assert page.discover_button.isEnabled() is False
    assert context.session.serial is None

    release.set()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert context.session.serial == WIFI_SERIAL
    assert context.session.transport is Transport.WIFI


def test_successful_pairing_records_the_device_and_opens_check(qtbot, tmp_path, caplog):
    code = "482913"
    wifi = FakeWifi()
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)

    page.ip_field.setText("192.168.1.42:37123")
    page.code_field.setText(code)
    with caplog.at_level(logging.INFO):
        page.connect_button.click()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert wifi.pair_calls == [(code, PAIRING, CONNECT)]
    assert context.session.serial == WIFI_SERIAL
    assert context.session.transport is Transport.WIFI
    assert context.session.state is SessionState.CONNECTING
    assert page.code_field.text() == ""
    assert page.next_page == "check"
    assert targets == ["check"]
    assert code not in caplog.text
    assert code not in repr(vars(page))


def test_pairing_failure_shows_retry_copy_and_usb_fallback(qtbot, tmp_path, caplog):
    code = "731604"
    wifi = FakeWifi(error=WifiError("Pairing failed. Check the code and try again."))
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)

    page.ip_field.setText("192.168.1.42:37123")
    page.code_field.setText(code)
    with caplog.at_level(logging.INFO):
        page.connect_button.click()
    qtbot.waitUntil(lambda: page.error_label.text() != "", timeout=3000)
    settle(qtbot, page)

    assert page.next_page is None
    assert targets == []
    assert page.error_label.text() == context.translator.tr("connect.pairing_failed")
    assert page.error_label.isVisibleTo(page) is True
    assert page.retry_button.isVisibleTo(page) is True
    assert page.retry_button.text() == context.translator.tr("connect.retry")
    assert page.usb_fallback_button.isVisibleTo(page) is True
    assert page.usb_fallback_button.text() == context.translator.tr("connect.use_usb")
    assert page.code_field.text() == ""
    assert context.session.serial is None
    assert code not in caplog.text

    page.usb_fallback_button.click()
    assert page.tabs.currentIndex() == 1


def test_a_short_pairing_code_never_calls_pairing(qtbot, tmp_path):
    wifi = FakeWifi()
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.ip_field.setText("192.168.1.42:37123")
    page.code_field.setText("123")
    page.connect_button.click()

    assert wifi.pair_calls == []
    assert page.error_label.text() == context.translator.tr("connect.invalid_code")
    assert page.next_page is None


def test_an_invalid_address_never_calls_pairing(qtbot, tmp_path):
    wifi = FakeWifi()
    context, _ = make_context(tmp_path, wifi=wifi)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.ip_field.setText("not-an-address")
    page.code_field.setText("123456")
    page.connect_button.click()

    assert wifi.pair_calls == []
    assert page.error_label.text() == context.translator.tr("connect.invalid_address")
    assert page.next_page is None


# ---------------------------------------------------------------------------
# USB connection
# ---------------------------------------------------------------------------


def test_usb_connect_attaches_the_single_online_device(qtbot, tmp_path):
    lister = DeviceLister([USB_DEVICE])
    context, _ = make_context(tmp_path, lister=lister)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert context.session.serial == "usb-1"
    assert context.session.transport is Transport.USB
    assert context.session.state is SessionState.CONNECTING
    assert context.cli.serial == "usb-1"
    assert page.next_page == "check"
    assert lister.calls == [context.adb_info]


def test_the_ip_and_mdns_rows_for_one_phone_collapse_to_one_choice(qtbot, tmp_path):
    mdns = DeviceEntry(
        serial="adb-ABC._adb-tls-connect._tcp.",
        state="device",
        model="ONEPLUS_A6013",
        transport="wifi",
    )
    address = DeviceEntry(
        serial="192.0.2.10:5555",
        state="device",
        model="ONEPLUS_A6013",
        transport="wifi",
    )
    context, _ = make_context(tmp_path, lister=DeviceLister([mdns, address]))
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert page.device_combo.isVisibleTo(page) is False
    assert context.session.serial == "192.0.2.10:5555"
    assert context.session.transport is Transport.WIFI
    assert context.cli.serial == "192.0.2.10:5555"


def test_usb_listing_runs_in_a_worker_and_disables_actions(qtbot, tmp_path):
    started = threading.Event()
    release = threading.Event()
    lister = DeviceLister([USB_DEVICE], started=started, release=release)
    context, _ = make_context(tmp_path, lister=lister)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(started.is_set, timeout=3000)

    assert page.busy is True
    assert page.usb_connect_button.isEnabled() is False
    assert context.session.serial is None

    release.set()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert context.session.serial == "usb-1"


def test_usb_connect_requires_a_deliberate_choice_with_two_devices(qtbot, tmp_path):
    second = DeviceEntry(
        serial="usb-2", state="device", model="Other", transport="usb"
    )
    context, _ = make_context(
        tmp_path, lister=DeviceLister([USB_DEVICE, second])
    )
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.device_combo.count() == 3, timeout=3000)
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert page.device_combo.isVisibleTo(page) is True
    assert page.device_combo.currentData() is None
    assert page.device_combo.model().item(0).isEnabled() is False
    assert page.error_label.text() == context.translator.tr(
        "connect.multiple_devices"
    )
    assert context.session.serial is None

    page.device_combo.setCurrentIndex(page.device_combo.findData("usb-2"))
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert context.session.serial == "usb-2"
    assert page.next_page == "check"


def test_usb_choice_uses_the_serial_when_the_listing_reorders(qtbot, tmp_path):
    second = DeviceEntry(
        serial="usb-2", state="device", model="Other", transport="usb"
    )
    lister = DeviceLister([USB_DEVICE, second])
    context, _ = make_context(tmp_path, lister=lister)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.device_combo.count() == 3, timeout=3000)
    page.device_combo.setCurrentIndex(page.device_combo.findData("usb-2"))

    lister.entries.reverse()
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.next_page == "check", timeout=3000)
    settle(qtbot, page)

    assert context.session.serial == "usb-2"


def test_usb_choice_is_refreshed_when_the_selected_phone_disappears(
    qtbot, tmp_path
):
    second = DeviceEntry(
        serial="usb-2", state="device", model="Other", transport="usb"
    )
    third = DeviceEntry(
        serial="usb-3", state="device", model="Third", transport="usb"
    )
    lister = DeviceLister([USB_DEVICE, second])
    context, _ = make_context(tmp_path, lister=lister)
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.device_combo.count() == 3, timeout=3000)
    page.device_combo.setCurrentIndex(page.device_combo.findData("usb-2"))

    lister.entries = [USB_DEVICE, third]
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert context.session.serial is None
    assert page.device_combo.currentData() is None
    assert page.error_label.text() == context.translator.tr(
        "connect.multiple_devices"
    )


def test_usb_connect_without_a_device_shows_the_empty_copy(qtbot, tmp_path):
    context, _ = make_context(tmp_path, lister=DeviceLister())
    page = ConnectPage(context)
    qtbot.addWidget(page)

    page.select_tab("usb")
    page.usb_connect_button.click()
    qtbot.waitUntil(lambda: page.error_label.text() != "", timeout=3000)
    settle(qtbot, page)

    assert page.error_label.text() == context.translator.tr("connect.no_devices")
    assert page.next_page is None
    assert context.session.serial is None


# ---------------------------------------------------------------------------
# Startup routing after ADB setup
# ---------------------------------------------------------------------------


def test_startup_skips_welcome_when_exactly_one_device_is_online(qtbot, tmp_path):
    lister = DeviceLister([USB_DEVICE])
    window, context, _ = make_window(qtbot, tmp_path, lister=lister)

    assert window.current_page_name == "check"
    assert window.current_step == "check"
    assert context.session.serial == "usb-1"
    assert context.session.transport is Transport.USB
    assert context.cli.serial == "usb-1"
    assert context.session.state is SessionState.CONNECTING
    assert len(lister.calls) == 1


def test_startup_skips_welcome_for_one_online_device_among_offline_rows(
    qtbot, tmp_path
):
    unauthorized = DeviceEntry(
        serial="usb-2", state="unauthorized", model="Other", transport="usb"
    )
    window, context, _ = make_window(
        qtbot, tmp_path, lister=DeviceLister([unauthorized, USB_DEVICE])
    )

    assert window.current_page_name == "check"
    assert context.session.serial == "usb-1"


def test_startup_shows_welcome_without_devices(qtbot, tmp_path):
    window, context, _ = make_window(qtbot, tmp_path, lister=DeviceLister())

    assert window.current_page_name == "welcome"
    assert context.session.serial is None


def test_startup_shows_welcome_with_multiple_online_devices(qtbot, tmp_path):
    second = DeviceEntry(
        serial="usb-2", state="device", model="Other", transport="usb"
    )
    window, context, _ = make_window(
        qtbot, tmp_path, lister=DeviceLister([USB_DEVICE, second])
    )

    assert window.current_page_name == "welcome"
    assert context.session.serial is None


def test_startup_survives_a_device_listing_failure(qtbot, tmp_path):
    lister = DeviceLister(error=AdbError("adb devices failed"))
    window, context, _ = make_window(qtbot, tmp_path, lister=lister)

    assert window.current_page_name == "welcome"
    assert context.session.serial is None
