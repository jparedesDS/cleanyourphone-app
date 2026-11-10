"""ApplyController: batches, re-plans, partial state and the undo path."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cleanyourphone_app.domain.apply import ApplyController, ApplyProgress, ApplyResult
from cleanyourphone_app.domain.models import PlanData, PlanRow
from cleanyourphone_app.services.cli import CliResult

BACKUP = Path("C:/backup/20260101_120000")
PASS_CHECKS = [{"check": "Device", "status": "PASS", "detail": "Pixel 8"}]


def row(action: str, package: str) -> PlanRow:
    return PlanRow(action=action, package=package)


def plan(*packages: str, action: str = "DISABLE") -> PlanData:
    return PlanData(
        profile_id="pixel-8",
        match=True,
        verification="device",
        auto_apply=True,
        rows=tuple(row(action, package) for package in packages),
    )


class FakeApplyCli:
    """Records every call in the exact argv shape the real client uses."""

    def __init__(
        self,
        *,
        plans: list[PlanData | Exception] | None = None,
        verify_checks: list[dict[str, str]] | None = None,
    ) -> None:
        self.plans = (
            list(plans)
            if plans is not None
            else [plan("a", "b", "c", "d", "e", "f")]
        )
        self.calls: list[CliResult] = []
        self.plan_calls: list[str] = []
        self.disable_calls: list[tuple[str, ...]] = []
        self.disable_results: list[int] = []
        self.list_disabled_result: set[str] = set()
        self.list_disabled_error: Exception | None = None
        self.verify_calls = 0
        self.verify_checks = list(verify_checks or PASS_CHECKS)
        self.verify_queue: list[list[dict[str, str]]] = []
        self.verify_error: Exception | None = None
        self.restore_dry_run_result = CliResult(
            ("restore", "--dry-run"),
            0,
            "WOULD ENABLE com.example.disabled\nDry run. Nothing changed.",
            "",
        )
        self.restore_result = CliResult(("restore",), 0, "Restore complete.", "")
        self.restore_from_backup_calls: list[tuple[Path, bool]] = []
        self.restore_from_backup_result = CliResult(
            ("restore", "--from-backup", str(BACKUP), "--yes"),
            0,
            "Restore from backup complete.",
            "",
        )

    def plan(self, profile_id: str) -> PlanData:
        self.plan_calls.append(profile_id)
        self.calls.append(
            CliResult(("--json", "plan", "--profile", profile_id), 0, "", "")
        )
        result = self.plans.pop(0) if len(self.plans) > 1 else self.plans[0]
        if isinstance(result, Exception):
            self.plans = [result]
            raise result
        return result

    def disable(self, packages) -> CliResult:
        batch = tuple(packages)
        self.disable_calls.append(batch)
        returncode = self.disable_results.pop(0) if self.disable_results else 0
        result = CliResult(("disable", *batch), returncode, "", "")
        self.calls.append(result)
        return result

    def list_disabled(self) -> set[str]:
        self.calls.append(
            CliResult(("--json", "list", "--state", "disabled"), 0, "", "")
        )
        if self.list_disabled_error is not None:
            raise self.list_disabled_error
        return set(self.list_disabled_result)

    def verify(self) -> dict:
        self.verify_calls += 1
        self.calls.append(CliResult(("--json", "verify"), 0, "", ""))
        if self.verify_error is not None:
            raise self.verify_error
        checks = self.verify_queue.pop(0) if self.verify_queue else self.verify_checks
        return {"checks": [dict(check) for check in checks]}

    def restore_dry_run(self) -> CliResult:
        self.calls.append(self.restore_dry_run_result)
        return self.restore_dry_run_result

    def restore(self) -> CliResult:
        self.calls.append(self.restore_result)
        return self.restore_result

    def restore_from_backup(self, backup: Path, yes: bool = True) -> CliResult:
        self.restore_from_backup_calls.append((Path(backup), yes))
        self.calls.append(self.restore_from_backup_result)
        return self.restore_from_backup_result


def test_success_runs_plan_before_each_batch_and_verifies_once_per_batch():
    cli = FakeApplyCli()
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(
        selected=("a", "b", "c", "d", "e", "f"), profile_id="pixel-8"
    )

    assert result.completed is True
    assert cli.calls[0].args[:4] == ("--json", "plan", "--profile", "pixel-8")
    assert cli.disable_calls == [("a", "b", "c", "d", "e"), ("f",)]
    assert cli.plan_calls == ["pixel-8", "pixel-8"]
    assert cli.verify_calls == 2
    assert result.failed_batch is None
    assert result.remaining_disabled == ()
    assert result.verify["checks"][0]["status"] == "PASS"


def test_failed_batch_reports_remaining_disabled_packages():
    cli = FakeApplyCli()
    cli.disable_results = [0, 1]
    cli.list_disabled_result = {"a", "b"}
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(("a", "b", "c", "d", "e", "f"), "pixel-8")

    assert result.completed is False
    assert result.failed_batch == ("f",)
    assert set(result.remaining_disabled) == {"a", "b"}
    assert result.rollback_verified is False
    assert result.verify["checks"][0]["status"] == "PASS"


def test_undo_uses_dry_run_then_restore():
    cli = FakeApplyCli()
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.undo()

    assert result.restored is True
    assert cli.calls[-2].args == ("restore", "--dry-run")
    assert cli.calls[-1].args == ("restore",)


def test_replan_removing_a_selected_package_prevents_it_from_being_disabled():
    first = plan("a", "b", "c", "d", "e", "f")
    second = plan("a", "b", "c", "d", "e", "f", action="BLOCKED")
    cli = FakeApplyCli(plans=[first, second])
    cli.list_disabled_result = {"a"}
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(("a", "b", "c", "d", "e", "f"), "pixel-8")

    assert cli.disable_calls == [("a", "b", "c", "d", "e")]
    assert "f" not in {package for batch in cli.disable_calls for package in batch}
    assert result.completed is False
    assert result.failed_batch is None
    assert result.remaining_disabled == ("a",)
    assert cli.plan_calls == ["pixel-8", "pixel-8"]


def test_a_replan_dropping_one_package_from_a_non_empty_batch_is_partial():
    dropped = PlanData(
        profile_id="pixel-8",
        match=True,
        verification="device",
        auto_apply=True,
        rows=(
            row("DISABLE", "a"),
            row("BLOCKED", "b"),
            row("DISABLE", "c"),
            row("DISABLE", "d"),
            row("DISABLE", "e"),
            row("DISABLE", "f"),
        ),
    )
    cli = FakeApplyCli(plans=[dropped, plan("a", "b", "c", "d", "e", "f")])
    cli.list_disabled_result = {"a"}
    events: list[ApplyProgress] = []
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(
        ("a", "b", "c", "d", "e", "f"),
        "pixel-8",
        on_progress=events.append,
    )

    assert cli.disable_calls == [("a", "c", "d", "e"), ("f",)]
    assert "b" not in {package for batch in cli.disable_calls for package in batch}
    assert result.completed is False
    assert result.failed_batch is None
    assert events[1].completed == ("a", "c", "d", "e")
    assert events[3].completed == ("a", "c", "d", "e", "f")


def test_restore_failure_offers_the_backup_without_silently_retrying():
    cli = FakeApplyCli()
    cli.restore_result = CliResult(("restore",), 1, "", "serial does not match")
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.undo()

    assert result.restored is False
    assert result.fallback_backup == BACKUP
    restore_calls = [call.args for call in cli.calls if call.args and call.args[0] == "restore"]
    assert restore_calls == [("restore", "--dry-run"), ("restore",)]
    assert cli.restore_from_backup_calls == []

    fallback = controller.restore_from_backup()

    assert fallback.restored is True
    assert cli.restore_from_backup_calls == [(BACKUP, True)]


def test_dry_run_failure_does_not_start_restore():
    cli = FakeApplyCli()
    cli.restore_dry_run_result = CliResult(
        ("restore", "--dry-run"), 1, "", "journal unavailable"
    )
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.undo()

    assert result.restored is False
    assert result.dry_run_failed is True
    assert result.fallback_backup == BACKUP
    assert [call.args for call in cli.calls] == [("restore", "--dry-run")]


def test_a_failed_verify_stops_before_the_next_batch():
    cli = FakeApplyCli()
    cli.verify_queue = [
        [{"check": "Home", "status": "FAIL", "detail": "no Home app"}],
    ]
    cli.list_disabled_result = {"a"}
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(("a", "b", "c", "d", "e", "f"), "pixel-8")

    assert result.completed is False
    assert result.failed_batch == ("a", "b", "c", "d", "e")
    assert result.remaining_disabled == ("a",)
    assert cli.disable_calls == [("a", "b", "c", "d", "e")]
    assert cli.verify_calls == 1


def test_a_failed_batch_that_rolled_back_cleanly_is_reported_verified():
    cli = FakeApplyCli()
    cli.disable_results = [1]
    cli.list_disabled_result = set()
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(("a", "b"), "pixel-8")

    assert result.completed is False
    assert result.failed_batch == ("a", "b")
    assert result.remaining_disabled == ()
    assert result.rollback_verified is True


def test_stop_requested_between_batches_sends_nothing_more():
    cli = FakeApplyCli()
    checks = iter([False, True])
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(
        ("a", "b", "c", "d", "e", "f"),
        "pixel-8",
        should_stop=lambda: next(checks, True),
    )

    assert cli.disable_calls == [("a", "b", "c", "d", "e")]
    assert result.completed is False
    assert result.failed_batch is None
    assert result.remaining_disabled == ()


def test_progress_reports_each_batch_and_its_completed_packages():
    cli = FakeApplyCli(plans=[plan(*[f"p{index}" for index in range(1, 8)])])
    events: list[ApplyProgress] = []
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(
        tuple(f"p{index}" for index in range(1, 8)),
        "pixel-8",
        on_progress=events.append,
    )

    assert result.completed is True
    assert [event.phase for event in events] == [
        "started",
        "done",
        "started",
        "done",
    ]
    assert [event.batch_index for event in events] == [1, 1, 2, 2]
    assert [event.total_batches for event in events] == [2, 2, 2, 2]
    assert events[1].completed == ("p1", "p2", "p3", "p4", "p5")
    assert events[3].completed == tuple(f"p{index}" for index in range(1, 8))


def test_plan_failure_stops_without_sending_the_batch():
    cli = FakeApplyCli(plans=[RuntimeError("plan crashed")])
    cli.list_disabled_result = set()
    controller = ApplyController(cli, backup=BACKUP)

    result = controller.run(("a", "b"), "pixel-8")

    assert result.completed is False
    assert result.failed_batch == ("a", "b")
    assert result.rollback_verified is False
    assert cli.disable_calls == []


def test_run_rejects_an_empty_selection_or_profile():
    cli = FakeApplyCli()
    controller = ApplyController(cli, backup=BACKUP)

    with pytest.raises(ValueError):
        controller.run((), "pixel-8")
    with pytest.raises(ValueError):
        controller.run(("a",), "")

    assert cli.calls == []


def test_apply_result_is_frozen():
    result = ApplyResult(completed=True, verify={"checks": []})

    with pytest.raises(FrozenInstanceError):
        result.completed = False  # type: ignore[misc]
