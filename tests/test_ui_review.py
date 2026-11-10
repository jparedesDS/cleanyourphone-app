"""BackupPage and ReviewPage: the two screens that guard every write."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt

from cleanyourphone_app.domain.models import PlanData, PlanRow, ProbeData
from cleanyourphone_app.domain.session import SessionState, Transport
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import AdbInfo
from cleanyourphone_app.services.cli import CliError, CliResult
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.main_window import MainWindow
from cleanyourphone_app.ui.pages import backup as backup_page_module
from cleanyourphone_app.ui.pages.backup import BackupPage
from cleanyourphone_app.ui.pages.review import ReviewPage
from cleanyourphone_app.ui.widgets.package_row import PackageRow

SERIAL = "usb-1"
FINGERPRINT = "google/shiba/shiba:14/AP1A.240505.004/11228896:user/release-keys"


def probe(**overrides) -> ProbeData:
    fields = {
        "brand": "Google",
        "model": "Pixel 8",
        "device": "shiba",
        "android": "14",
        "sdk": 34,
        "build": "AP1A.240505.004",
        "fingerprint": FINGERPRINT,
        "managed": False,
        "users": 1,
        "is_tv": False,
        "battery": {"level": 80},
        "profiles": ("pixel-8",),
        "auto_apply_profiles": ("pixel-8",),
    }
    fields.update(overrides)
    return ProbeData(**fields)


def plan_row(action: str, package: str, why: str = "", breaks: str = "", reason: str = ""):
    return PlanRow(action=action, package=package, why=why, breaks=breaks, reason=reason)


def make_plan(
    *rows: PlanRow,
    auto_apply: bool = True,
    match: bool = True,
    verification: str = "device",
) -> PlanData:
    return PlanData(
        profile_id="pixel-8",
        match=match,
        verification=verification,
        auto_apply=auto_apply,
        rows=tuple(rows),
    )


def default_plan() -> PlanData:
    return make_plan(
        plan_row("DISABLE", "com.example.disable", "Unused", "Nothing"),
        plan_row("ASK", "com.example.ask", "Optional", "Its features"),
        plan_row("BLOCKED", "com.example.blocked", reason="it is the current Home app"),
        plan_row("SKIP", "com.example.skip", reason="already disabled"),
    )


def documented_plan() -> PlanData:
    return make_plan(
        plan_row("ASK", "com.example.ask", "Optional", "Its features"),
        plan_row("BLOCKED", "com.example.blocked", reason="it is the current Home app"),
        auto_apply=False,
        verification="documented",
    )


def backup_context() -> AppContext:
    context = AppContext.fake(translator=Translator("en"))
    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    return context


def review_context(translator: Translator | None = None) -> AppContext:
    context = AppContext.fake(translator=translator or Translator("en"))
    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    context.session.backup_done(Path("C:/backup/20260101_120000"))
    return context


def documented_context(translator: Translator | None = None) -> AppContext:
    context = AppContext.fake(translator=translator or Translator("en"))
    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(
        SERIAL, Transport.USB, probe(), "pixel-8", "documented"
    )
    context.session.checked(probe(), "pixel-8")
    context.session.backup_done(Path("C:/backup/20260101_120000"))
    return context


def write_backup(root: Path, name: str = "20260102_120000") -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "timestamp": name,
        "serial": SERIAL,
        "probe": {"fingerprint": FINGERPRINT},
    }
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


class FakeBackupCli:
    def __init__(
        self,
        result: CliResult | None = None,
        error: Exception | None = None,
        root: Path | None = None,
    ):
        self.backup_result = result or CliResult(("backup",), 0, "", "")
        self.backup_error = error
        self.backup_calls = 0
        self.thread_name = ""
        self.root = root
        self.written: list[Path] = []

    def backup(self) -> CliResult:
        self.backup_calls += 1
        self.thread_name = threading.current_thread().name
        if self.backup_error is not None:
            raise self.backup_error
        if self.backup_result.returncode == 0 and self.root is not None:
            name = f"20260102_{120000 + self.backup_calls - 1:06d}"
            self.written.append(write_backup(self.root, name))
        return self.backup_result


class FakePlanCli:
    def __init__(self, *plans: PlanData | Exception):
        if not plans:
            plans = (default_plan(),)
        self.plans = list(plans)
        self.plan_calls: list[str] = []
        self.thread_name = ""

    def plan(self, profile_id: str) -> PlanData:
        self.plan_calls.append(profile_id)
        self.thread_name = threading.current_thread().name
        result = self.plans.pop(0) if len(self.plans) > 1 else self.plans[0]
        if isinstance(result, Exception):
            raise result
        return result


ADS_PROVIDERS = {
    "adguard": {
        "host": "dns.adguard-dns.com",
        "description": "AdGuard DNS: ads and trackers",
    },
    "controld": {
        "host": "p2.freedns.controld.com",
        "description": "Control D free: ads and trackers",
    },
}


class FakeAdsPlanCli(FakePlanCli):
    def __init__(
        self,
        *plans: PlanData | Exception,
        providers: dict[str, dict[str, str]] | None = None,
        provider_error: Exception | None = None,
    ):
        super().__init__(*plans)
        self.providers = providers if providers is not None else ADS_PROVIDERS
        self.provider_error = provider_error
        self.provider_calls = 0

    def dns_providers(self) -> dict[str, dict[str, str]]:
        self.provider_calls += 1
        if self.provider_error is not None:
            raise self.provider_error
        return {name: dict(item) for name, item in self.providers.items()}


def wait_for_review_page(qtbot, page: ReviewPage) -> None:
    qtbot.waitUntil(
        lambda: not page.busy and (page.model is not None or page.error_label.isVisibleTo(page)),
        timeout=3000,
    )


# ---------------------------------------------------------------------------
# BackupPage
# ---------------------------------------------------------------------------


def test_backup_page_records_the_newest_matching_folder(qtbot, tmp_path):
    root = tmp_path / ".cleanyourphone" / "backup"
    older = write_backup(root, "20260101_120000")
    context = backup_context()
    cli = FakeBackupCli(root=root)

    page = BackupPage(context, cli, root=root)
    qtbot.addWidget(page)
    page.show()

    qtbot.waitUntil(lambda: page.next_page == "review", timeout=3000)
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert cli.backup_calls == 1
    assert len(cli.written) == 1
    newest = cli.written[0]
    assert page.backup_path == newest
    assert older != page.backup_path
    assert context.session.backup_path == newest
    assert context.session.state is SessionState.REVIEW
    assert str(newest) in page.path_label.text()
    assert page.retry_button.isVisibleTo(page) is False


def test_backup_runs_off_the_ui_thread(qtbot, tmp_path):
    class BlockingCli(FakeBackupCli):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def backup(self) -> CliResult:
            self.started.set()
            self.release.wait(2)
            return super().backup()

    root = tmp_path / "backup"
    context = backup_context()
    cli = BlockingCli()
    cli.root = root
    page = BackupPage(context, cli, root=root)
    qtbot.addWidget(page)

    page.run()
    qtbot.waitUntil(cli.started.is_set, timeout=3000)

    assert page.busy is True
    assert cli.thread_name != threading.current_thread().name

    cli.release.set()
    qtbot.waitUntil(lambda: page.next_page == "review", timeout=3000)


def test_backup_failure_stops_with_a_clear_error_and_no_skip(qtbot, tmp_path):
    context = backup_context()
    cli = FakeBackupCli(result=CliResult(("backup",), 1, "", "adb failed"))

    page = BackupPage(context, cli, root=tmp_path / "backup")
    qtbot.addWidget(page)
    page.show()

    qtbot.waitUntil(lambda: page.busy is False and page.error_label.isVisibleTo(page))
    qtbot.waitUntil(lambda: cli.backup_calls == 1, timeout=3000)

    assert page.next_page is None
    assert page.error_label.text() == context.translator.tr("backup.failed")
    assert page.retry_button.isVisibleTo(page) is True
    assert page.backup_path is None
    assert context.session.backup_path is None
    assert context.session.state is SessionState.BACKUP
    assert not hasattr(page, "skip_button")


def test_backup_without_a_matching_folder_never_continues(qtbot, tmp_path):
    context = backup_context()
    cli = FakeBackupCli()
    root = tmp_path / "backup"
    # A backup for another phone exists; it must not unlock Review.
    other = root / "other"
    other.mkdir(parents=True)
    (other / "meta.json").write_text(
        json.dumps(
            {
                "timestamp": "20260102_120000",
                "serial": "usb-2",
                "probe": {"fingerprint": FINGERPRINT},
            }
        ),
        encoding="utf-8",
    )

    page = BackupPage(context, cli, root=root)
    qtbot.addWidget(page)
    page.show()

    qtbot.waitUntil(lambda: page.busy is False and page.error_label.isVisibleTo(page))

    assert page.next_page is None
    assert page.backup_path is None
    assert context.session.backup_path is None
    assert context.session.state is SessionState.BACKUP
    assert page.error_label.text() == context.translator.tr("backup.failed")


def test_backup_with_only_a_preexisting_matching_folder_never_continues(
    qtbot, tmp_path
):
    context = backup_context()
    root = tmp_path / "backup"
    stale = write_backup(root, "20260102_120000")
    old = time.time() - 300
    os.utime(stale / "meta.json", (old, old))
    os.utime(stale, (old, old))
    # The CLI reports success but does not create a new folder.
    cli = FakeBackupCli()

    page = BackupPage(context, cli, root=root)
    qtbot.addWidget(page)
    page.show()

    qtbot.waitUntil(lambda: page.busy is False and page.error_label.isVisibleTo(page))

    assert cli.backup_calls == 1
    assert page.next_page is None
    assert page.backup_path is None
    assert context.session.backup_path is None
    assert context.session.state is SessionState.BACKUP
    assert page.error_label.text() == context.translator.tr("backup.failed")
    assert stale.exists()


def test_backup_worker_exception_stops_with_a_clear_error(qtbot, tmp_path):
    context = backup_context()
    cli = FakeBackupCli(error=CliError("backup crashed"))

    page = BackupPage(context, cli, root=tmp_path / "backup")
    qtbot.addWidget(page)
    page.show()

    qtbot.waitUntil(lambda: page.busy is False and page.error_label.isVisibleTo(page))

    assert page.next_page is None
    assert page.error_label.text() == context.translator.tr("backup.failed")
    assert page.retry_button.isVisibleTo(page) is True
    assert page.backup_path is None
    assert context.session.backup_path is None
    assert context.session.state is SessionState.BACKUP


def test_backup_retry_can_succeed_after_a_failure(qtbot, tmp_path):
    root = tmp_path / "backup"
    stale = write_backup(root)
    context = backup_context()
    cli = FakeBackupCli(result=CliResult(("backup",), 1, "", "no adb"), root=root)

    page = BackupPage(context, cli, root=root)
    qtbot.addWidget(page)
    page.show()
    qtbot.waitUntil(lambda: page.busy is False and cli.backup_calls == 1)

    cli.backup_result = CliResult(("backup",), 0, "Backup written", "")
    page.retry_button.click()
    qtbot.waitUntil(lambda: page.next_page == "review", timeout=3000)

    assert cli.backup_calls == 2
    assert len(cli.written) == 1
    assert cli.written[0] != stale
    assert context.session.state is SessionState.REVIEW
    assert context.session.backup_path == cli.written[0]


# ---------------------------------------------------------------------------
# PackageRow
# ---------------------------------------------------------------------------


def test_package_row_shows_the_package_why_and_breaks(qtbot):
    row = PackageRow(
        plan_row("DISABLE", "com.example.disable", "Unused", "Nothing"),
        checked=True,
        tr=Translator("en").tr,
    )
    qtbot.addWidget(row)

    assert row.name_label.text() == "com.example.disable"
    assert row.package_label.text() == "com.example.disable"
    assert "Unused" in row.why_label.text()
    assert "Nothing" in row.breaks_label.text()
    assert row.checkbox.isChecked() is True
    assert row.status_label.text() == "Disable"


def test_package_row_prefers_a_friendly_name_and_still_shows_the_id(qtbot):
    row = PackageRow(
        plan_row("DISABLE", "com.example.disable", "Unused", "Nothing"),
        checked=True,
        friendly_name="Digital Wellbeing",
        tr=Translator("en").tr,
    )
    qtbot.addWidget(row)

    assert row.name_label.text() == "Digital Wellbeing"
    assert row.package_label.text() == "com.example.disable"
    assert row.package_label.isHidden() is False


def test_package_row_accepts_catalog_none(qtbot):
    row = PackageRow(plan_row("ASK", "com.example.ask", "Optional", "Features"), catalog=None)
    qtbot.addWidget(row)

    assert "Optional" in row.why_label.text()


def test_clicking_the_row_toggles_the_checkbox(qtbot):
    row = PackageRow(plan_row("ASK", "com.example.ask", "Optional", "Features"))
    qtbot.addWidget(row)
    row.show()
    states: list[bool] = []
    row.toggled.connect(lambda package, checked: states.append(checked))

    qtbot.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())

    assert row.checkbox.isChecked() is True
    assert states == [True]
    assert row.status_label.text() == "Disable"


def test_blocked_package_row_has_no_checkbox(qtbot):
    row = PackageRow(
        plan_row("BLOCKED", "com.example.blocked", reason="it is the current Home app"),
        selectable=False,
        tr=Translator("en").tr,
    )
    qtbot.addWidget(row)

    assert row.checkbox.isHidden() is True
    assert "current Home app" in row.reason_label.text()
    assert row.status_label.text() == "Not changed"


# ---------------------------------------------------------------------------
# ReviewPage
# ---------------------------------------------------------------------------


def test_review_defaults_disable_checked_and_ask_unchecked(qtbot):
    cli = FakePlanCli(default_plan())
    context = review_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    assert cli.plan_calls == ["pixel-8"]
    assert page.model is not None
    assert page.model.is_checked("com.example.disable") is True
    assert page.model.is_checked("com.example.ask") is False
    assert page.row_widgets["com.example.disable"].checkbox.isChecked() is True
    assert page.row_widgets["com.example.ask"].checkbox.isChecked() is False
    assert page.continue_button.text() == "Disable 1 apps"
    assert page.continue_button.isEnabled() is True
    assert page.continue_button.property("primary") is True


def test_checking_an_ask_row_updates_the_primary_button(qtbot):
    page = ReviewPage(review_context(), FakePlanCli(default_plan()))
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    page.row_widgets["com.example.ask"].checkbox.setChecked(True)

    assert page.model.is_checked("com.example.ask") is True
    assert page.continue_button.text() == "Disable 2 apps"
    assert page.continue_button.isEnabled() is True


def test_documented_plan_requires_acknowledgement_before_continue(qtbot):
    cli = FakePlanCli(documented_plan(), documented_plan())
    context = documented_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    assert page.documented_card.isHidden() is False
    assert page.documented_ack.isChecked() is False
    assert page.model.selected_packages() == ()
    assert page.continue_button.isEnabled() is False

    page.row_widgets["com.example.ask"].checkbox.setChecked(True)
    assert page.continue_button.isEnabled() is False

    page.documented_ack.setChecked(True)
    assert page.continue_button.isEnabled() is True

    page.continue_button.click()
    qtbot.waitUntil(lambda: page.next_page == "apply", timeout=3000)

    assert context.session.selected_packages == ("com.example.ask",)
    assert context.session.verification == "documented"


def test_unchecking_everything_disables_the_primary_button(qtbot):
    page = ReviewPage(review_context(), FakePlanCli(default_plan()))
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    page.row_widgets["com.example.disable"].checkbox.setChecked(False)

    assert page.model.selected_packages() == ()
    assert page.continue_button.text() == "Disable 0 apps"
    assert page.continue_button.isEnabled() is False
    assert page.empty_label.isVisibleTo(page) is True


def test_blocked_rows_are_collapsed_and_not_selectable(qtbot):
    page = ReviewPage(review_context(), FakePlanCli(default_plan()))
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    assert page.blocked_container.isHidden() is True
    assert page.blocked_button.text() == "Show not changed"
    assert page.row_widgets["com.example.blocked"].checkbox.isHidden() is True
    assert page.row_widgets["com.example.skip"].checkbox.isHidden() is True
    assert page.blocked_count_label.text() == "2"

    page.blocked_button.click()

    assert page.blocked_container.isVisibleTo(page) is True
    assert page.blocked_button.text() == "Hide not changed"

    page.blocked_button.click()
    assert page.blocked_container.isHidden() is True


def test_apply_replans_and_drops_a_package_that_is_no_longer_actionable(qtbot):
    first = default_plan()
    second = make_plan(
        plan_row("ASK", "com.example.ask", "Optional", "Its features"),
        plan_row("BLOCKED", "com.example.disable", reason="it is the current keyboard"),
    )
    cli = FakePlanCli(first, second)
    context = review_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    page.row_widgets["com.example.ask"].checkbox.setChecked(True)
    assert page.continue_button.text() == "Disable 2 apps"

    page.continue_button.click()
    qtbot.waitUntil(lambda: page.next_page == "apply", timeout=3000)
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert cli.plan_calls == ["pixel-8", "pixel-8"]
    assert context.session.selected_packages == ("com.example.ask",)
    assert context.session.state is SessionState.REVIEW
    assert context.session.can_apply() is True
    assert page.next_page == "apply"

    # ApplyPage owns the transition; the reviewed session must be startable.
    context.session.start_apply()
    assert context.session.state is SessionState.APPLYING


def test_apply_stops_when_the_replan_removes_every_selection(qtbot):
    first = default_plan()
    second = make_plan(
        plan_row("BLOCKED", "com.example.disable", reason="role"),
        plan_row("BLOCKED", "com.example.ask", reason="role"),
    )
    cli = FakePlanCli(first, second)
    context = review_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    page.row_widgets["com.example.ask"].checkbox.setChecked(True)
    page.continue_button.click()
    qtbot.waitUntil(lambda: cli.plan_calls == ["pixel-8", "pixel-8"], timeout=3000)
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert page.next_page is None
    assert context.session.state is SessionState.REVIEW
    assert context.session.selected_packages == ()
    assert page.model.selected_packages() == ()
    assert page.continue_button.isEnabled() is False
    assert page.empty_label.isVisibleTo(page) is True


def test_apply_stops_when_the_replan_fails(qtbot):
    first = default_plan()
    cli = FakePlanCli(first, CliError("plan failed"))
    context = review_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    page.continue_button.click()
    qtbot.waitUntil(lambda: len(cli.plan_calls) == 2, timeout=3000)
    qtbot.waitUntil(lambda: page.busy is False, timeout=3000)

    assert page.next_page is None
    assert page.error_label.text() == context.translator.tr("review.plan_failed")
    assert page.error_label.isVisibleTo(page) is True
    assert context.session.state is SessionState.REVIEW
    assert context.session.selected_packages == ()
    assert page.model.selected_packages() == ("com.example.disable",)
    assert page.continue_button.isEnabled() is True


def test_review_rejects_a_plan_that_is_not_an_exact_tested_device_plan(qtbot):
    cli = FakePlanCli(make_plan(plan_row("DISABLE", "com.example.disable"), auto_apply=False))
    context = review_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    assert page.next_page is None
    assert page.model is None
    assert page.error_label.text() == context.translator.tr("review.plan_changed")
    assert page.retry_button.isVisibleTo(page) is True
    assert page.continue_button.isEnabled() is False
    assert context.session.state is SessionState.REVIEW


def test_initial_plan_failure_can_be_retried(qtbot):
    cli = FakePlanCli(CliError("probe failed"), default_plan())
    context = review_context()
    page = ReviewPage(context, cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    assert page.model is None
    assert page.error_label.text() == context.translator.tr("review.plan_failed")
    assert page.retry_button.isVisibleTo(page) is True

    page.retry_button.click()
    wait_for_review_page(qtbot, page)

    assert cli.plan_calls == ["pixel-8", "pixel-8"]
    assert page.model is not None
    assert page.error_label.isVisibleTo(page) is False
    assert page.continue_button.isEnabled() is True


def test_spanish_review_copy_uses_desactivar_and_dejar_como_esta(qtbot):
    page = ReviewPage(review_context(Translator("es")), FakePlanCli(default_plan()))
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)

    assert page.continue_button.text() == "Desactivar 1 apps"
    assert page.row_widgets["com.example.ask"].status_label.text() == "Dejar como está"
    assert "quitar" not in page.continue_button.text().lower()
    assert "quitar" not in page.row_widgets["com.example.ask"].status_label.text().lower()


def test_review_shows_an_optional_unchecked_ads_card(qtbot):
    cli = FakeAdsPlanCli(default_plan())
    page = ReviewPage(review_context(Translator("es")), cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)
    qtbot.waitUntil(lambda: page.ads_combo.count() == 2, timeout=3000)

    assert cli.provider_calls == 1
    assert page.ads_checkbox.text() == "Bloquear anuncios"
    assert page.ads_checkbox.isChecked() is False
    assert page.ads_provider is None
    assert page.ads_combo.isEnabled() is False
    assert page.ads_combo.currentData() == "adguard"
    assert page.ads_combo.currentText() == "AdGuard"
    assert "YouTube" in page.ads_caveat_label.text()
    assert page.ads_caveat_label.isVisibleTo(page) is True


def test_checking_ads_selects_adguard_for_the_apply_step(qtbot):
    cli = FakeAdsPlanCli(default_plan())
    page = ReviewPage(review_context(Translator("es")), cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)
    qtbot.waitUntil(lambda: page.ads_combo.count() == 2, timeout=3000)

    emitted: list[str | None] = []
    page.ads_selected.connect(emitted.append)
    page.ads_checkbox.setChecked(True)

    assert page.ads_combo.isEnabled() is True
    assert page.ads_provider == "adguard"

    page.continue_button.click()
    qtbot.waitUntil(lambda: page.next_page == "apply", timeout=3000)

    assert emitted == ["adguard"]
    assert page.ads_provider == "adguard"


def test_review_ads_card_falls_back_to_adguard_when_providers_fail(qtbot):
    cli = FakeAdsPlanCli(default_plan(), provider_error=CliError("offline"))
    page = ReviewPage(review_context(Translator("es")), cli)
    qtbot.addWidget(page)
    page.show()
    wait_for_review_page(qtbot, page)
    qtbot.waitUntil(lambda: page.ads_combo.count() == 1, timeout=3000)

    assert page.ads_combo.currentData() == "adguard"
    assert page.ads_checkbox.isChecked() is False
    assert page.ads_provider is None


# ---------------------------------------------------------------------------
# Shell wiring
# ---------------------------------------------------------------------------


def make_info() -> AdbInfo:
    return AdbInfo(
        path=Path("C:/tools/adb.exe"),
        version=(37, 0, 1),
        version_text="Version 37.0.1",
    )


def test_main_window_registers_real_backup_and_review_pages(qtbot):
    context = AppContext.fake(
        translator=Translator("en"),
        adb_info=make_info(),
        device_lister=lambda _info: [],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    assert isinstance(window.backup_page, BackupPage)
    assert isinstance(window.review_page, ReviewPage)
    assert window.current_page_name == "welcome"


def test_shell_gives_review_the_package_catalog(qtbot):
    plan = make_plan(
        plan_row(
            "DISABLE",
            "com.google.android.apps.wellbeing",
            "Digital Wellbeing: screen-time tracking",
            "Screen-time dashboard and app timers",
        ),
        plan_row("ASK", "com.example.unknown", "Unknown app", "Its features"),
    )
    context = AppContext.fake(
        translator=Translator("es"),
        cli=FakePlanCli(plan),
        adb_info=make_info(),
        device_lister=lambda _info: [],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    window.show_page("review")

    qtbot.waitUntil(lambda: window.review_page.model is not None, timeout=3000)

    assert window.review_page.catalog is context.package_catalog
    known = window.review_page.row_widgets["com.google.android.apps.wellbeing"]
    assert "Bienestar digital" in known.why_label.text()
    assert "tiempo de pantalla" in known.why_label.text()
    assert known.english_note_label.isHidden() is True

    unknown = window.review_page.row_widgets["com.example.unknown"]
    assert "Unknown app" in unknown.why_label.text()
    assert unknown.english_note_label.text() == "Detalles en inglés"
    assert unknown.english_note_label.isHidden() is False


def test_shell_keeps_english_review_details_in_english_ui(qtbot):
    plan = make_plan(
        plan_row(
            "DISABLE",
            "com.google.android.apps.wellbeing",
            "Digital Wellbeing: screen-time tracking",
            "Screen-time dashboard and app timers",
        ),
        plan_row("ASK", "com.example.unknown", "Unknown app", "Its features"),
    )
    context = AppContext.fake(
        translator=Translator("en"),
        cli=FakePlanCli(plan),
        adb_info=make_info(),
        device_lister=lambda _info: [],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    window.show_page("review")

    qtbot.waitUntil(lambda: window.review_page.model is not None, timeout=3000)

    known = window.review_page.row_widgets["com.google.android.apps.wellbeing"]
    assert "Digital Wellbeing" in known.why_label.text()
    assert "Bienestar digital" not in known.why_label.text()
    assert "Screen-time dashboard" in known.breaks_label.text()
    assert known.english_note_label.isHidden() is True

    unknown = window.review_page.row_widgets["com.example.unknown"]
    assert "Unknown app" in unknown.why_label.text()
    assert unknown.english_note_label.isHidden() is True


def test_switching_language_refreshes_review_details(qtbot):
    plan = make_plan(
        plan_row(
            "DISABLE",
            "com.google.android.apps.wellbeing",
            "Digital Wellbeing: screen-time tracking",
            "Screen-time dashboard and app timers",
        ),
        plan_row("ASK", "com.example.unknown", "Unknown app", "Its features"),
    )
    context = AppContext.fake(
        translator=Translator("en"),
        cli=FakePlanCli(plan),
        adb_info=make_info(),
        device_lister=lambda _info: [],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    window.show_page("review")

    qtbot.waitUntil(lambda: window.review_page.model is not None, timeout=3000)
    known = window.review_page.row_widgets["com.google.android.apps.wellbeing"]
    unknown = window.review_page.row_widgets["com.example.unknown"]
    assert "Digital Wellbeing" in known.why_label.text()

    window.set_language("es")

    assert "Bienestar digital" in known.why_label.text()
    assert unknown.english_note_label.text() == "Detalles en inglés"
    assert unknown.english_note_label.isHidden() is False

    window.set_language("en")

    assert "Digital Wellbeing" in known.why_label.text()
    assert "Bienestar digital" not in known.why_label.text()
    assert unknown.english_note_label.isHidden() is True


def test_backup_then_review_runs_through_the_real_shell(qtbot, tmp_path, monkeypatch):
    root = tmp_path / ".cleanyourphone" / "backup"
    monkeypatch.setattr(backup_page_module, "default_backup_root", lambda: root)

    cli = FakeBackupCli(root=root)
    cli.plan = FakePlanCli(default_plan()).plan  # type: ignore[attr-defined]
    context = AppContext.fake(
        translator=Translator("en"),
        cli=cli,
        adb_info=make_info(),
        device_lister=lambda _info: [],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    window.show_page("backup")

    qtbot.waitUntil(lambda: window.current_page_name == "review", timeout=5000)
    qtbot.waitUntil(lambda: window.review_page.model is not None, timeout=3000)

    assert context.session.state is SessionState.REVIEW
    assert len(cli.written) == 1
    assert context.session.backup_path == cli.written[0]
    assert window.review_page.model.selected_packages() == ("com.example.disable",)


def test_shell_passes_the_review_ads_provider_to_apply(qtbot):
    cli = FakeAdsPlanCli(default_plan())
    context = AppContext.fake(
        translator=Translator("es"),
        cli=cli,
        adb_info=make_info(),
        device_lister=lambda _info: [],
    )
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    window.start_flow()

    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    context.session.backup_done(Path("C:/backup/20260101_120000"))
    window.show_page("review")

    qtbot.waitUntil(lambda: window.review_page.model is not None, timeout=3000)
    qtbot.waitUntil(lambda: window.review_page.ads_combo.count() == 2, timeout=3000)

    window.review_page.ads_checkbox.setChecked(True)
    window.review_page.continue_button.click()

    qtbot.waitUntil(lambda: window.current_page_name == "apply", timeout=3000)

    assert window.apply_page.ads_provider == "adguard"
