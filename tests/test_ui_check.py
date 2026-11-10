"""Check page support decisions and the unsupported-device screen."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.domain.session import (
    SessionController,
    SessionState,
    Transport,
)
from cleanyourphone_app.domain.support import SKILL_URL
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import AdbInfo, DeviceEntry
from cleanyourphone_app.services.cli import CliError
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.main_window import MainWindow
from cleanyourphone_app.ui.pages import blocked as blocked_module
from cleanyourphone_app.ui.pages.blocked import SAFETY_DOCS_URL, BlockedPage
from cleanyourphone_app.ui.pages.check import CheckPage

USB_DEVICE = DeviceEntry(
    serial="usb-1", state="device", model="Pixel_8", transport="usb"
)


def probe(**overrides) -> ProbeData:
    fields = {
        "brand": "Google",
        "model": "Pixel 8",
        "device": "shiba",
        "android": "14",
        "sdk": 34,
        "build": "AP1A.240505.004",
        "fingerprint": (
            "google/shiba/shiba:14/AP1A.240505.004/11228896:user/release-keys"
        ),
        "managed": False,
        "users": 1,
        "is_tv": False,
        "battery": {"level": 80},
        "profiles": ("pixel-8",),
        "auto_apply_profiles": ("pixel-8",),
    }
    fields.update(overrides)
    return ProbeData(**fields)


class FakeCli:
    """Minimal sidecar stand-in that can block like a real probe call."""

    def __init__(self, result: ProbeData | None = None, error: Exception | None = None):
        self.probe_result = result if result is not None else probe()
        self.probe_error = error
        self.probe_calls = 0
        self._lock = threading.Lock()

    def probe(self) -> ProbeData:
        with self._lock:
            self.probe_calls += 1
        if self.probe_error is not None:
            raise self.probe_error
        return self.probe_result


@pytest.fixture
def fake_cli() -> FakeCli:
    return FakeCli()


@pytest.fixture
def fake_context() -> AppContext:
    context = AppContext.fake(translator=Translator("en"))
    context.session.attach(USB_DEVICE.serial, Transport.USB)
    return context


def make_info() -> AdbInfo:
    return AdbInfo(
        path=Path("C:/tools/adb.exe"),
        version=(37, 0, 1),
        version_text="Version 37.0.1",
    )


def run_check(qtbot, page: CheckPage) -> None:
    """Start the worker and wait for it to finish, like the real page."""
    page.run()
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)


def patch_desktop_services(monkeypatch) -> list[str]:
    opened: list[str] = []

    class FakeDesktopServices:
        @staticmethod
        def openUrl(url) -> bool:
            opened.append(url.toString())
            return True

    monkeypatch.setattr(blocked_module, "QDesktopServices", FakeDesktopServices)
    return opened


# ---------------------------------------------------------------------------
# Check page
# ---------------------------------------------------------------------------


def test_supported_phone_advances_to_backup(qtbot, fake_cli, fake_context):
    fake_cli.probe_result = probe(auto_apply_profiles=("pixel-8",))
    page = CheckPage(fake_context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert fake_context.session.profile_id == "pixel-8"
    assert fake_context.session.state is SessionState.BACKUP
    assert fake_context.session.serial == USB_DEVICE.serial
    assert fake_context.session.transport is Transport.USB
    assert fake_context.session.probe is fake_cli.probe_result
    assert page.next_page == "backup"


def test_no_profile_shows_skill_link(qtbot, fake_cli, fake_context):
    fake_cli.probe_result = probe(auto_apply_profiles=())
    page = CheckPage(fake_context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert page.next_page == "blocked"
    assert page.blocked_link == "https://jparedesds.github.io/cleanyourphone-web/"
    assert page.blocked_reason == "no_device_profile"
    assert fake_context.session.state is SessionState.BLOCKED
    assert fake_context.session.blocked_reason == "no_device_profile"
    assert fake_context.session.blocked_link == SKILL_URL
    assert fake_context.session.probe is None
    assert fake_context.session.profile_id is None


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"managed": True}, "managed"),
        ({"managed": None}, "managed_unknown"),
        ({"users": None}, "users_unknown"),
        ({"users": 2}, "multi_user"),
        ({"sdk": 25}, "android_too_old"),
        ({"is_tv": True}, "tv"),
    ],
)
def test_safety_blockers_link_to_docs_not_the_skill(
    qtbot, fake_cli, fake_context, overrides, reason
):
    fake_cli.probe_result = probe(**overrides)
    page = CheckPage(fake_context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert page.next_page == "blocked"
    assert page.blocked_reason == reason
    assert page.blocked_link == SAFETY_DOCS_URL
    assert page.blocked_link != SKILL_URL
    assert fake_context.session.state is SessionState.BLOCKED
    assert fake_context.session.blocked_reason == reason
    assert fake_context.session.probe is None
    assert fake_context.session.profile_id is None


def test_multiple_profiles_require_a_choice(qtbot, fake_cli, fake_context):
    fake_cli.probe_result = probe(
        auto_apply_profiles=("pixel-8", "pixel-8-alt")
    )
    page = CheckPage(fake_context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert page.next_page is None
    assert page.profile_combo.count() == 3
    assert page.profile_combo.itemData(0) is None
    assert page.profile_combo.isHidden() is False
    assert page.continue_button.isHidden() is False
    assert page.continue_button.isEnabled() is False
    assert fake_context.session.profile_id is None
    assert fake_context.session.probe is None
    assert fake_context.session.state is SessionState.CONNECTING

    index = page.profile_combo.findData("pixel-8-alt")
    page.profile_combo.setCurrentIndex(index)

    assert page.continue_button.isEnabled() is True

    page.continue_button.click()

    assert page.next_page == "backup"
    assert fake_context.session.profile_id == "pixel-8-alt"
    assert fake_context.session.state is SessionState.BACKUP


def test_connected_is_recorded_before_checked(qtbot, fake_cli):
    events: list[str] = []

    class RecordingSession(SessionController):
        def connected(self, *args, **kwargs):
            events.append("connected")
            super().connected(*args, **kwargs)

        def checked(self, *args, **kwargs):
            events.append("checked")
            super().checked(*args, **kwargs)

    session = RecordingSession()
    session.attach(USB_DEVICE.serial, Transport.USB)
    context = AppContext.fake(translator=Translator("en"), session=session)
    page = CheckPage(context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert events == ["connected", "checked"]
    assert session.serial == USB_DEVICE.serial
    assert session.transport is Transport.USB
    assert session.profile_id == "pixel-8"
    assert session.state is SessionState.BACKUP


def test_check_does_not_invent_a_device_without_attach(qtbot, fake_cli):
    context = AppContext.fake(translator=Translator("en"))
    page = CheckPage(context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert page.next_page is None
    assert page.error_label.text() == context.translator.tr("check.failed")
    assert context.session.serial is None
    assert context.session.transport is None
    assert context.session.profile_id is None
    assert context.session.probe is None
    assert context.session.state is SessionState.WELCOME


def test_probe_runs_off_the_ui_thread(qtbot, fake_context):
    class BlockingCli:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()
            self.thread_name = ""

        def probe(self) -> ProbeData:
            self.thread_name = threading.current_thread().name
            self.started.set()
            self.release.wait(2)
            return probe()

    cli = BlockingCli()
    page = CheckPage(fake_context, cli)
    qtbot.addWidget(page)

    page.run()
    qtbot.waitUntil(cli.started.is_set, timeout=3000)

    assert page.busy is True
    assert cli.thread_name != threading.current_thread().name

    cli.release.set()
    qtbot.waitUntil(lambda: page.next_page == "backup", timeout=3000)
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)


def test_probe_failure_shows_retry_and_changes_nothing(qtbot, fake_cli, fake_context):
    fake_cli.probe_error = CliError("probe failed")
    page = CheckPage(fake_context, fake_cli)
    qtbot.addWidget(page)

    run_check(qtbot, page)

    assert page.next_page is None
    assert page.error_label.text() == fake_context.translator.tr("check.failed")
    assert page.error_label.isVisibleTo(page) is True
    assert page.retry_button.isVisibleTo(page) is True
    assert fake_context.session.state is SessionState.CONNECTING
    assert fake_context.session.probe is None
    assert fake_context.session.profile_id is None

    fake_cli.probe_error = None
    page.retry_button.click()
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert fake_cli.probe_calls == 2
    assert page.next_page == "backup"
    assert fake_context.session.state is SessionState.BACKUP


# ---------------------------------------------------------------------------
# Blocked page
# ---------------------------------------------------------------------------


BLOCKED_COPY = [
    ("managed", "blocked.managed"),
    ("managed_unknown", "blocked.managed_unknown"),
    ("users_unknown", "blocked.users_unknown"),
    ("multi_user", "blocked.multi_user"),
    ("android_too_old", "blocked.old_android"),
    ("tv", "blocked.tv"),
]


def test_blocked_page_skill_button_opens_the_skill_site(
    qtbot, fake_context, monkeypatch
):
    opened = patch_desktop_services(monkeypatch)
    page = BlockedPage(fake_context)
    qtbot.addWidget(page)

    page.show_blocked("no_device_profile", SKILL_URL)

    assert page.reason == "no_device_profile"
    assert page.link == SKILL_URL
    assert page.reason_label.text() == fake_context.translator.tr(
        "blocked.no_profile"
    )
    assert page.skill_button.text() == fake_context.translator.tr("blocked.skill")
    assert page.skill_button.property("primary") is True
    assert page.skill_button.isVisibleTo(page) is True
    assert page.docs_button.isVisibleTo(page) is False

    page.skill_button.click()

    assert opened == [SKILL_URL]


def test_blocked_page_untested_build_offers_the_skill(
    qtbot, fake_context, monkeypatch
):
    opened = patch_desktop_services(monkeypatch)
    page = BlockedPage(fake_context)
    qtbot.addWidget(page)

    page.show_blocked("untested_build", SKILL_URL)

    assert page.reason_label.text() == fake_context.translator.tr(
        "blocked.untested_build"
    )
    assert page.skill_button.isVisibleTo(page) is True
    assert page.docs_button.isVisibleTo(page) is False

    page.skill_button.click()

    assert opened == [SKILL_URL]


@pytest.mark.parametrize(("reason", "key"), BLOCKED_COPY)
def test_blocked_page_offers_docs_and_never_the_skill(
    qtbot, fake_context, monkeypatch, reason, key
):
    opened = patch_desktop_services(monkeypatch)
    page = BlockedPage(fake_context)
    qtbot.addWidget(page)

    page.show_blocked(reason, SAFETY_DOCS_URL)

    assert page.reason_label.text() == fake_context.translator.tr(key)
    assert page.skill_button.isVisibleTo(page) is False
    assert page.docs_button.isVisibleTo(page) is True
    assert page.docs_button.text() == fake_context.translator.tr("blocked.docs")

    page.docs_button.click()

    assert opened == [SAFETY_DOCS_URL]


def test_blocked_page_back_returns_to_welcome(qtbot, fake_context):
    page = BlockedPage(fake_context)
    qtbot.addWidget(page)
    targets: list[str] = []
    restarts: list[bool] = []
    page.navigate.connect(targets.append)
    page.restart_requested.connect(lambda: restarts.append(True))

    page.show_blocked("managed", SAFETY_DOCS_URL)
    page.back_button.click()

    assert page.back_button.text() == fake_context.translator.tr("blocked.back")
    assert page.next_page == "welcome"
    assert targets == ["welcome"]
    assert restarts == [True]


def test_blocked_page_hides_external_actions_without_a_link(qtbot, fake_context):
    page = BlockedPage(fake_context)
    qtbot.addWidget(page)

    page.show_blocked("managed", None)

    assert page.skill_button.isVisibleTo(page) is False
    assert page.docs_button.isVisibleTo(page) is False


# ---------------------------------------------------------------------------
# Shell integration
# ---------------------------------------------------------------------------


def test_connect_then_check_reaches_backup_with_the_real_session(qtbot):
    fake_cli = FakeCli()
    devices: list[DeviceEntry] = []
    context = AppContext.fake(
        translator=Translator("en"),
        cli=fake_cli,
        adb_info=make_info(),
        device_lister=lambda _info: list(devices),
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    assert window.current_page_name == "welcome"

    window.welcome_page.usb_button.click()
    devices.append(USB_DEVICE)
    window.connect_page.usb_connect_button.click()

    qtbot.waitUntil(
        lambda: context.session.state is SessionState.BACKUP, timeout=5000
    )
    qtbot.waitUntil(lambda: window.check_page.busy is False, timeout=3000)

    assert window.current_page_name == "backup"
    assert context.session.serial == USB_DEVICE.serial
    assert context.session.transport is Transport.USB
    assert context.session.probe is fake_cli.probe_result
    assert context.session.profile_id == "pixel-8"
    assert fake_cli.probe_calls == 1


def test_window_routes_a_blocked_probe_to_the_blocked_page(qtbot):
    fake_cli = FakeCli(result=probe(auto_apply_profiles=()))
    context = AppContext.fake(
        translator=Translator("en"),
        cli=fake_cli,
        adb_info=make_info(),
        device_lister=lambda _info: [USB_DEVICE],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    qtbot.waitUntil(
        lambda: context.session.state is SessionState.BLOCKED, timeout=5000
    )
    qtbot.waitUntil(lambda: window.check_page.busy is False, timeout=3000)

    assert window.current_page_name == "blocked"
    assert window.blocked_page.reason == "no_device_profile"
    assert window.blocked_page.link == SKILL_URL
    assert window.blocked_page.skill_button.isVisibleTo(window.blocked_page) is True
    assert window.check_page.blocked_link == SKILL_URL


def test_blocked_phone_can_start_a_new_session_after_volver(qtbot):
    fake_cli = FakeCli(result=probe(auto_apply_profiles=()))
    context = AppContext.fake(
        translator=Translator("en"),
        cli=fake_cli,
        adb_info=make_info(),
        device_lister=lambda _info: [USB_DEVICE],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    qtbot.waitUntil(
        lambda: context.session.state is SessionState.BLOCKED, timeout=5000
    )
    qtbot.waitUntil(lambda: window.check_page.busy is False, timeout=3000)
    assert fake_cli.probe_calls == 1

    window.blocked_page.back_button.click()

    assert window.current_page_name == "welcome"
    assert context.session.state is SessionState.WELCOME
    assert context.session.serial is None
    assert context.session.transport is None
    assert context.session.blocked_reason is None
    assert context.session.blocked_link is None
    assert window.check_page.next_page is None
    assert window.check_page.blocked_reason is None
    assert window.check_page.blocked_link is None
    assert window.check_page.profile_combo.count() == 0
    assert window.check_page.error_label.text() == ""

    fake_cli.probe_result = probe()
    window.welcome_page.usb_button.click()
    window.connect_page.usb_connect_button.click()

    qtbot.waitUntil(
        lambda: context.session.state is SessionState.BACKUP, timeout=5000
    )
    qtbot.waitUntil(lambda: window.check_page.busy is False, timeout=3000)

    assert window.current_page_name == "backup"
    assert context.session.serial == USB_DEVICE.serial
    assert context.session.transport is Transport.USB
    assert context.session.profile_id == "pixel-8"
    assert fake_cli.probe_calls == 2
