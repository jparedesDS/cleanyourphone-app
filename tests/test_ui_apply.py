"""ApplyPage and DonePage: visible batch progress and an honest undo path."""

from __future__ import annotations

import threading
from pathlib import Path

from cleanyourphone_app.domain.apply import (
    ApplyController,
    ApplyProgress,
    ApplyResult,
    ApplySummary,
    UndoResult,
)
from cleanyourphone_app.domain.batches import split_batches
from cleanyourphone_app.domain.models import PlanData, PlanRow, ProbeData
from cleanyourphone_app.domain.session import SessionState, Transport
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import AdbInfo
from cleanyourphone_app.services.cli import CliResult
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.main_window import MainWindow
from cleanyourphone_app.ui.pages.apply import ApplyPage
from cleanyourphone_app.ui.pages.done import DonePage

SERIAL = "usb-1"
FINGERPRINT = "google/shiba/shiba:14/AP1A.240505.004/11228896:user/release-keys"
BACKUP = Path("C:/backup/20260101_120000")
PASS_CHECKS = [{"check": "Device", "status": "PASS", "detail": "Pixel 8"}]


def probe() -> ProbeData:
    return ProbeData(
        brand="Google",
        model="Pixel 8",
        device="shiba",
        android="14",
        sdk=34,
        build="AP1A.240505.004",
        fingerprint=FINGERPRINT,
        managed=False,
        users=1,
        is_tv=False,
        battery={"level": 80},
        profiles=("pixel-8",),
        auto_apply_profiles=("pixel-8",),
    )


def review_context(
    selected=("com.example.a", "com.example.b"),
    translator: Translator | None = None,
) -> AppContext:
    context = AppContext.fake(translator=translator or Translator("es"))
    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    context.session.backup_done(BACKUP)
    context.session.set_selection(selected)
    return context


def backup_context(selected=("com.example.a", "com.example.b")) -> AppContext:
    context = AppContext.fake(translator=Translator("es"))
    context.session.attach(SERIAL, Transport.USB)
    context.session.connected(SERIAL, Transport.USB, probe(), "pixel-8")
    context.session.checked(probe(), "pixel-8")
    context.session.set_selection(selected)
    return context


class FakeApplyController:
    """Deterministic worker double that can pause inside a batch."""

    def __init__(
        self,
        *,
        block_at: int | None = None,
        fail_result=None,
        drop: tuple[str, ...] = (),
        force_completed: bool = False,
    ) -> None:
        self.block_at = block_at
        self.fail_result = fail_result
        self.drop = set(drop)
        self.force_completed = force_completed
        self.run_calls: list[tuple[tuple[str, ...], str]] = []
        self.ads_providers: list[str | None] = []
        self.disabled: list[tuple[str, ...]] = []
        self.stopped = False
        self.dropped = False
        self.batch_started = threading.Event()
        self.release = threading.Event()

    def run(
        self,
        selected,
        profile_id,
        on_progress=None,
        should_stop=None,
        ads_provider=None,
    ):
        selected = tuple(selected)
        self.run_calls.append((selected, profile_id))
        self.ads_providers.append(ads_provider)
        batches = split_batches(selected)
        applied: list[str] = []
        for index, original in enumerate(batches, start=1):
            if should_stop is not None and should_stop():
                self.stopped = True
                break
            batch = tuple(package for package in original if package not in self.drop)
            if len(batch) != len(original):
                self.dropped = True
            if not batch:
                continue
            self.disabled.append(batch)
            if on_progress is not None:
                on_progress(
                    ApplyProgress(
                        index,
                        len(batches),
                        batch,
                        tuple(applied),
                        "started",
                    )
                )
            if self.block_at == index:
                self.batch_started.set()
                self.release.wait(5)
            applied.extend(batch)
            if on_progress is not None:
                on_progress(
                    ApplyProgress(
                        index,
                        len(batches),
                        batch,
                        tuple(applied),
                        "done",
                    )
                )
            if self.fail_result is not None:
                return self.fail_result
        return ApplyResult(
            completed=self.force_completed
            or (
                not self.stopped
                and not self.dropped
                and len(applied) == len(selected)
            ),
            verify={"checks": [dict(check) for check in PASS_CHECKS]},
        )


class FakeUndoController:
    def __init__(
        self,
        *,
        preview_result: CliResult | None = None,
        undo_result: UndoResult | None = None,
        fallback_result: UndoResult | None = None,
    ) -> None:
        self.backup = BACKUP
        self.preview_calls = 0
        self.undo_calls = 0
        self.restore_calls: list[Path] = []
        self.preview_result = preview_result or CliResult(
            ("restore", "--dry-run"),
            0,
            "WOULD ENABLE com.example.disabled\nDry run. Nothing changed.",
            "",
        )
        self.undo_result = undo_result or UndoResult(
            restored=True,
            dry_run="WOULD ENABLE com.example.disabled",
        )
        self.fallback_result = fallback_result or UndoResult(
            restored=True, used_backup=True
        )

    def preview_undo(self):
        self.preview_calls += 1
        return self.preview_result

    def undo(self):
        self.undo_calls += 1
        return self.undo_result

    def restore_from_backup(self):
        self.restore_calls.append(BACKUP)
        return self.fallback_result


class FakeAdsFlowCli:
    """Real-controller double that records package and DNS call order."""

    def __init__(self, packages: tuple[str, ...]) -> None:
        self.packages = tuple(packages)
        self.events: list[str] = []
        self.disable_calls: list[tuple[str, ...]] = []
        self.dns_set_calls: list[str] = []
        self.dns_check_calls = 0
        self.dns_set_result = CliResult(
            ("dns", "set", "adguard"), 0, "Private DNS set.", ""
        )
        self.dns_check_result = {
            "ad_domain": "doubleclick.net",
            "ad_ip": "0.0.0.0",
            "ad_state": "blocked",
            "ad_blocked": True,
            "control_domain": "wikipedia.org",
            "control_ip": "203.0.113.7",
            "control_state": "ok",
            "online": True,
        }

    def plan(self, profile_id: str) -> PlanData:
        self.events.append("plan")
        return PlanData(
            profile_id="pixel-8",
            match=True,
            verification="device",
            auto_apply=True,
            rows=tuple(
                PlanRow(action="DISABLE", package=package)
                for package in self.packages
            ),
        )

    def disable(self, packages) -> CliResult:
        batch = tuple(packages)
        self.disable_calls.append(batch)
        self.events.append("disable:" + ",".join(batch))
        return CliResult(("disable", *batch), 0, "", "")

    def verify(self) -> dict:
        self.events.append("verify")
        return {"checks": [dict(check) for check in PASS_CHECKS]}

    def list_disabled(self) -> set[str]:
        return {package for batch in self.disable_calls for package in batch}

    def dns_set(self, provider: str) -> CliResult:
        self.dns_set_calls.append(provider)
        self.events.append("dns_set:" + provider)
        return self.dns_set_result

    def dns_check(self) -> dict:
        self.dns_check_calls += 1
        self.events.append("dns_check")
        return dict(self.dns_check_result)


def make_summary(
    *,
    completed: bool = True,
    applied=("com.example.a", "com.example.b", "com.example.c"),
    selected=None,
    failed_batch=None,
    remaining_disabled=(),
    stopped: bool = False,
    verify=None,
    ads_provider=None,
    ads_check=None,
    ads_error=None,
) -> ApplySummary:
    selected = tuple(selected) if selected is not None else tuple(applied)
    result = ApplyResult(
        completed=completed,
        failed_batch=failed_batch,
        remaining_disabled=tuple(remaining_disabled),
        rollback_verified=False,
        verify=verify if verify is not None else {"checks": [dict(PASS_CHECKS[0])]},
        ads_provider=ads_provider,
        ads_check=ads_check,
        ads_error=ads_error,
    )
    return ApplySummary(
        result=result,
        applied=tuple(applied),
        selected=selected,
        stopped=stopped,
    )


# ---------------------------------------------------------------------------
# ApplyPage
# ---------------------------------------------------------------------------


def test_apply_button_is_disabled_without_a_selection_or_a_backup(qtbot):
    without_selection = ApplyPage(review_context(selected=()))
    qtbot.addWidget(without_selection)
    without_selection.show()
    assert without_selection.apply_button.isEnabled() is False

    without_backup = ApplyPage(backup_context(("com.example.a",)))
    qtbot.addWidget(without_backup)
    without_backup.show()
    assert without_backup.apply_button.isEnabled() is False

    without_backup.apply_button.click()
    assert without_backup.context.session.state is SessionState.BACKUP
    assert without_backup.context.session.selected_packages == ("com.example.a",)


def test_apply_starts_once_and_shows_batch_two_of_three(qtbot):
    selected = tuple(f"com.example.p{index}" for index in range(1, 13))
    context = review_context(selected)
    start_calls: list[bool] = []
    original_start = context.session.start_apply

    def counting_start() -> None:
        start_calls.append(True)
        original_start()

    context.session.start_apply = counting_start  # type: ignore[method-assign]
    controller = FakeApplyController(block_at=2)
    page = ApplyPage(context, controller=controller)
    qtbot.addWidget(page)
    page.show()

    assert context.session.state is SessionState.REVIEW
    assert page.apply_button.isEnabled() is True
    page.apply_button.click()

    assert context.session.state is SessionState.APPLYING
    qtbot.waitUntil(controller.batch_started.is_set, timeout=3000)
    qtbot.waitUntil(lambda: page.batch_label.text() == "Lote 2 de 3", timeout=3000)

    assert page.progress_bar.maximum() == 3
    assert page.progress_bar.value() == 1
    texts = [
        page.package_list.item(index).text()
        for index in range(page.package_list.count())
    ]
    assert "com.example.p1" in texts
    assert "com.example.p12" in texts

    page.apply_button.click()
    assert len(controller.run_calls) == 1
    assert len(start_calls) == 1

    controller.release.set()
    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)
    assert context.session.state is SessionState.DONE
    assert context.session.completed_batches == 3


def test_stop_after_this_batch_stops_before_the_next_batch(qtbot):
    selected = tuple(f"com.example.p{index}" for index in range(1, 13))
    context = review_context(selected)
    controller = FakeApplyController(block_at=1)
    page = ApplyPage(context, controller=controller)
    qtbot.addWidget(page)
    page.show()
    page.apply_button.click()

    qtbot.waitUntil(controller.batch_started.is_set, timeout=3000)
    assert page.stop_button.isVisibleTo(page) is True
    assert page.stop_button.text() == "Detener al terminar este lote"

    page.stop_button.click()
    controller.release.set()

    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)

    assert controller.stopped is True
    assert len(controller.disabled) == 1
    assert controller.disabled[0] == tuple(split_batches(selected)[0])
    assert page.last_summary is not None
    assert page.last_summary.stopped is True
    assert context.session.state is SessionState.DONE
    assert context.session.completed_batches == 1


def test_partial_replan_never_counts_a_dropped_package(qtbot):
    selected = (
        "com.example.a",
        "com.example.b",
        "com.example.c",
        "com.example.d",
        "com.example.e",
        "com.example.f",
    )
    context = review_context(selected)
    controller = FakeApplyController(drop=("com.example.b",))
    page = ApplyPage(context, controller=controller)
    qtbot.addWidget(page)
    page.show()

    page.apply_button.click()
    qtbot.waitUntil(lambda: page.error_label.isVisibleTo(page), timeout=3000)
    qtbot.waitUntil(lambda: not page.busy, timeout=3000)

    assert "com.example.b" not in {
        package for batch in controller.disabled for package in batch
    }
    page.undo_button.click()
    assert page.last_summary is not None
    assert "com.example.b" not in page.last_summary.applied

    done = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(done)
    done.show_summary(page.last_summary)
    done.show()

    assert done.count_label.text() == "5 apps desactivadas"


def test_a_completed_result_never_overwrites_applied_with_the_selection(qtbot):
    selected = ("com.example.a", "com.example.b", "com.example.c")
    context = review_context(selected)
    controller = FakeApplyController(
        drop=("com.example.b",),
        force_completed=True,
    )
    page = ApplyPage(context, controller=controller)
    qtbot.addWidget(page)
    page.show()

    page.apply_button.click()
    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)

    assert page.last_summary is not None
    assert page.last_summary.result.completed is True
    assert page.last_summary.applied == ("com.example.a", "com.example.c")


def test_failed_batch_shows_remaining_disabled_and_an_undo_action(qtbot):
    selected = ("com.example.a", "com.example.b", "com.example.c")
    context = review_context(selected)
    failure = ApplyResult(
        completed=False,
        failed_batch=("com.example.c",),
        remaining_disabled=("com.example.a", "com.example.b"),
        rollback_verified=False,
        verify={"checks": [{"check": "Home", "status": "FAIL", "detail": "no"}]},
    )
    controller = FakeApplyController(fail_result=failure)
    page = ApplyPage(context, controller=controller)
    qtbot.addWidget(page)
    page.show()

    page.apply_button.click()
    qtbot.waitUntil(lambda: page.error_label.isVisibleTo(page), timeout=3000)
    qtbot.waitUntil(lambda: not page.busy, timeout=3000)

    assert page.next_page is None
    assert "com.example.a" in page.remaining_label.text()
    assert "com.example.b" in page.remaining_label.text()
    assert page.undo_button.isVisibleTo(page) is True
    assert page.undo_button.text() == "Deshacer todo"

    page.undo_button.click()

    assert page.next_page == "done"
    assert page.last_summary is not None
    assert page.last_summary.result is failure


# ---------------------------------------------------------------------------
# DonePage
# ---------------------------------------------------------------------------


def test_apply_page_forwards_the_selected_ads_provider(qtbot):
    selected = ("com.example.a", "com.example.b")
    context = review_context(selected)
    controller = FakeApplyController()
    page = ApplyPage(context, controller=controller)
    qtbot.addWidget(page)
    page.show()

    page.set_ads_provider("adguard")
    page.apply_button.click()

    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)

    assert controller.ads_providers == ["adguard"]


def test_ads_flow_sets_dns_after_packages_and_done_shows_blocked(qtbot):
    selected = ("com.example.a", "com.example.b")
    context = review_context(selected)
    cli = FakeAdsFlowCli(selected)
    page = ApplyPage(context, controller=ApplyController(cli, backup=BACKUP))
    qtbot.addWidget(page)
    page.show()

    page.set_ads_provider("adguard")
    page.apply_button.click()
    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)

    assert cli.disable_calls == [selected]
    assert cli.dns_set_calls == ["adguard"]
    assert cli.dns_check_calls == 1
    assert cli.events.index("dns_set:adguard") > cli.events.index(
        "disable:" + ",".join(selected)
    )
    assert cli.events.index("dns_check") > cli.events.index("dns_set:adguard")

    summary = page.last_summary
    assert summary is not None
    assert summary.result.completed is True
    assert summary.result.ads_provider == "adguard"
    assert summary.result.ads_check["ad_blocked"] is True
    assert summary.result.ads_error is None

    done = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(done)
    done.show_summary(summary)
    done.show()

    assert done.ads_label.isVisibleTo(done) is True
    assert done.ads_label.text() == "Anuncios bloqueados"
    assert "YouTube" in done.ads_caveat_label.text()
    assert done.ads_caveat_label.isVisibleTo(done) is True


def test_ads_set_failure_keeps_packages_and_done_shows_the_error(qtbot):
    selected = ("com.example.a", "com.example.b")
    context = review_context(selected)
    cli = FakeAdsFlowCli(selected)
    cli.dns_set_result = CliResult(
        ("dns", "set", "adguard"), 1, "", "private dns failed"
    )
    page = ApplyPage(context, controller=ApplyController(cli, backup=BACKUP))
    qtbot.addWidget(page)
    page.show()

    page.set_ads_provider("adguard")
    page.apply_button.click()
    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)

    assert cli.dns_set_calls == ["adguard"]
    assert cli.dns_check_calls == 0
    assert page.last_summary is not None
    assert page.last_summary.result.completed is True
    assert page.last_summary.result.ads_error == "set"

    done = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(done)
    done.show_summary(page.last_summary)
    done.show()

    assert done.count_label.text() == "2 apps desactivadas"
    assert done.ads_label.isVisibleTo(done) is True
    assert "No se pudo activar" in done.ads_label.text()


def test_apply_without_ads_never_calls_dns(qtbot):
    selected = ("com.example.a", "com.example.b")
    context = review_context(selected)
    cli = FakeAdsFlowCli(selected)
    page = ApplyPage(context, controller=ApplyController(cli, backup=BACKUP))
    qtbot.addWidget(page)
    page.show()

    page.apply_button.click()
    qtbot.waitUntil(lambda: page.next_page == "done", timeout=3000)

    assert cli.dns_set_calls == []
    assert cli.dns_check_calls == 0
    assert page.last_summary is not None
    assert page.last_summary.result.ads_provider is None


def test_done_shows_an_offline_ads_check_as_not_verified(qtbot):
    context = review_context()
    page = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(page)
    page.show_summary(
        make_summary(
            applied=("com.example.a",),
            ads_provider="adguard",
            ads_check={
                "ad_domain": "doubleclick.net",
                "ad_ip": "",
                "ad_state": "unknown",
                "ad_blocked": None,
                "control_domain": "wikipedia.org",
                "control_ip": "",
                "control_state": "unknown",
                "online": False,
            },
            ads_error="offline",
        )
    )
    page.show()

    assert page.ads_label.isVisibleTo(page) is True
    assert "No se pudo comprobar" in page.ads_label.text()
    assert page.ads_caveat_label.isVisibleTo(page) is True


def test_done_hides_the_ads_status_when_ads_were_off(qtbot):
    context = review_context()
    page = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(page)
    page.show_summary(make_summary())
    page.show()

    assert page.ads_label.isHidden() is True
    assert page.ads_caveat_label.isHidden() is True


def test_done_shows_the_count_the_backup_path_and_undo(qtbot):
    context = review_context(
        ("com.example.a", "com.example.b", "com.example.c"),
    )
    page = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(page)

    page.show_summary(make_summary())
    page.show()

    assert page.count_label.text() == "3 apps desactivadas"
    assert str(BACKUP) in page.backup_label.text()
    assert page.undo_button.text() == "Deshacer todo"
    assert page.undo_button.isVisibleTo(page) is True


def test_undo_asks_for_confirmation_and_shows_the_dry_run_summary(qtbot):
    context = review_context()
    controller = FakeUndoController()
    page = DonePage(context, controller=controller)
    qtbot.addWidget(page)
    page.show_summary(make_summary())
    page.show()

    page.undo_button.click()
    qtbot.waitUntil(
        lambda: page.confirm_panel.isVisibleTo(page) and page.confirm_button.isEnabled(),
        timeout=3000,
    )

    assert controller.preview_calls == 1
    assert controller.undo_calls == 0
    assert "WOULD ENABLE com.example.disabled" in page.dry_run_output.text()
    assert page.dry_run_output.isVisibleTo(page) is True
    assert "sesiones anteriores" in page.confirm_body_label.text()

    page.confirm_button.click()
    qtbot.waitUntil(
        lambda: controller.undo_calls == 1 and not page.busy, timeout=3000
    )

    assert "Deshecho" in page.status_label.text()
    assert page.confirm_panel.isHidden() is True


def test_undo_failure_offers_restore_from_backup_without_retrying(qtbot):
    context = review_context()
    controller = FakeUndoController(
        undo_result=UndoResult(
            restored=False,
            dry_run="WOULD ENABLE com.example.disabled",
            fallback_backup=BACKUP,
        )
    )
    page = DonePage(context, controller=controller)
    qtbot.addWidget(page)
    page.show_summary(make_summary())
    page.show()

    page.undo_button.click()
    qtbot.waitUntil(
        lambda: page.confirm_panel.isVisibleTo(page) and page.confirm_button.isEnabled(),
        timeout=3000,
    )
    page.confirm_button.click()
    qtbot.waitUntil(lambda: page.fallback_panel.isVisibleTo(page), timeout=3000)

    assert controller.undo_calls == 1
    assert controller.restore_calls == []
    assert "copia" in page.fallback_warning_label.text()

    page.fallback_button.click()
    qtbot.waitUntil(lambda: controller.restore_calls and not page.busy, timeout=3000)

    assert controller.undo_calls == 1
    assert controller.restore_calls == [BACKUP]
    assert "Restaurado" in page.status_label.text()


def test_successful_undo_clears_the_stale_remaining_state(qtbot):
    context = review_context(("com.example.a", "com.example.b", "com.example.c"))
    controller = FakeUndoController()
    page = DonePage(context, controller=controller)
    qtbot.addWidget(page)
    page.show_summary(
        make_summary(
            completed=False,
            applied=("com.example.a",),
            selected=("com.example.a", "com.example.b", "com.example.c"),
            failed_batch=("com.example.b", "com.example.c"),
            remaining_disabled=("com.example.b",),
        )
    )
    page.show()

    assert page.remaining_label.isVisibleTo(page) is True

    page.undo_button.click()
    qtbot.waitUntil(
        lambda: page.confirm_panel.isVisibleTo(page) and page.confirm_button.isEnabled(),
        timeout=3000,
    )
    page.confirm_button.click()
    qtbot.waitUntil(
        lambda: controller.undo_calls == 1 and not page.busy, timeout=3000
    )

    assert "Deshecho" in page.status_label.text()
    assert page.remaining_caption.isHidden() is True
    assert page.remaining_label.isHidden() is True
    assert page.count_label.isHidden() is True
    assert page.summary_warning_label.isHidden() is True


def test_stopped_summary_says_the_rest_was_not_changed(qtbot):
    context = review_context(("com.example.a", "com.example.b", "com.example.c"))
    page = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(page)
    page.show_summary(
        make_summary(
            completed=False,
            applied=("com.example.a", "com.example.b"),
            selected=("com.example.a", "com.example.b", "com.example.c"),
            stopped=True,
        )
    )
    page.show()

    assert "2 apps desactivadas" in page.count_label.text()
    assert "no se han cambiado" in page.status_label.text()
    assert page.remaining_label.isHidden() is True


def test_failed_summary_keeps_the_real_remaining_packages_visible(qtbot):
    context = review_context(("com.example.a", "com.example.b", "com.example.c"))
    page = DonePage(context, controller=FakeUndoController())
    qtbot.addWidget(page)
    page.show_summary(
        make_summary(
            completed=False,
            applied=("com.example.a",),
            selected=("com.example.a", "com.example.b", "com.example.c"),
            failed_batch=("com.example.b", "com.example.c"),
            remaining_disabled=("com.example.b",),
        )
    )
    page.show()

    assert "com.example.b" in page.remaining_label.text()
    assert "no se ha cambiado nada" not in page.status_label.text().lower()
    assert page.undo_button.isVisibleTo(page) is True


# ---------------------------------------------------------------------------
# Shell wiring
# ---------------------------------------------------------------------------


def make_info() -> AdbInfo:
    return AdbInfo(
        path=Path("C:/tools/adb.exe"),
        version=(37, 0, 1),
        version_text="Version 37.0.1",
    )


def test_main_window_registers_apply_and_done_and_blocks_close(qtbot):
    selected = tuple(f"com.example.p{index}" for index in range(1, 4))
    context = AppContext.fake(
        translator=Translator("es"),
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
    context.session.backup_done(BACKUP)
    context.session.set_selection(selected)
    window.show_page("apply")

    assert isinstance(window.apply_page, ApplyPage)
    assert isinstance(window.done_page, DonePage)

    controller = FakeApplyController(block_at=1)
    window.apply_page._controller = controller
    window.apply_page.apply_button.click()
    qtbot.waitUntil(controller.batch_started.is_set, timeout=3000)

    assert window.close() is False
    assert window.isVisible() is True

    controller.release.set()
    qtbot.waitUntil(lambda: window.current_page_name == "done", timeout=3000)

    assert window.done_page.count_label.text() == "3 apps desactivadas"
    assert window.close() is True


def test_preview_failure_keeps_the_failed_summary_and_scoped_copy(qtbot):
    selected = ("com.example.a", "com.example.b", "com.example.c")
    context = AppContext.fake(
        translator=Translator("es"),
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
    context.session.backup_done(BACKUP)
    context.session.set_selection(selected)
    window.show_page("apply")

    failure = ApplyResult(
        completed=False,
        failed_batch=("com.example.c",),
        remaining_disabled=("com.example.b",),
        rollback_verified=False,
        verify={"checks": [{"check": "Home", "status": "FAIL", "detail": "no"}]},
    )
    window.apply_page._controller = FakeApplyController(fail_result=failure)
    undo_controller = FakeUndoController(
        preview_result=CliResult(
            ("restore", "--dry-run"), 1, "", "journal unavailable"
        )
    )
    window.done_page._controller = undo_controller

    window.apply_page.apply_button.click()
    qtbot.waitUntil(
        lambda: window.apply_page.error_label.isVisibleTo(window.apply_page),
        timeout=3000,
    )
    qtbot.waitUntil(lambda: not window.apply_page.busy, timeout=3000)
    window.apply_page.undo_button.click()
    qtbot.waitUntil(lambda: window.current_page_name == "done", timeout=3000)

    done = window.done_page
    assert undo_controller.preview_calls == 0
    assert done.summary_warning_label.isVisibleTo(done) is True
    assert done.remaining_label.isVisibleTo(done) is True
    assert "com.example.b" in done.remaining_label.text()

    done.undo_button.click()
    qtbot.waitUntil(
        lambda: done.error_label.isVisibleTo(done) and not done.busy,
        timeout=3000,
    )

    assert undo_controller.preview_calls == 1
    assert done.summary_warning_label.isVisibleTo(done) is True
    assert done.remaining_label.isVisibleTo(done) is True
    assert "com.example.b" in done.remaining_label.text()
    assert done.fallback_panel.isVisibleTo(done) is True
    text = done.error_label.text().lower()
    assert "no se ha cambiado nada" not in text
    assert "nothing has been changed" not in text
    assert "deshacer" in text
