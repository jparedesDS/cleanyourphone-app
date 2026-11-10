"""ReviewModel turns a CLI plan into the exact checked selection the user sees."""

from __future__ import annotations

import pytest

from cleanyourphone_app.domain.models import PlanData, PlanRow
from cleanyourphone_app.domain.review import ReviewModel, plan_allows_review


def plan_row(action: str, package: str, why: str = "", breaks: str = "", reason: str = ""):
    return PlanRow(
        action=action,
        package=package,
        why=why,
        breaks=breaks,
        reason=reason,
    )


def make_plan(*rows: PlanRow, profile_id: str = "pixel-8") -> PlanData:
    return PlanData(
        profile_id=profile_id,
        match=True,
        verification="device",
        auto_apply=True,
        rows=tuple(rows),
    )


def plan_with_disable_and_ask() -> PlanData:
    return make_plan(
        plan_row("DISABLE", "disable.pkg", why="unused", breaks="Nothing"),
        plan_row("ASK", "ask.pkg", why="optional", breaks="Its features"),
        plan_row("BLOCKED", "blocked.pkg", reason="it is the current Home app"),
        plan_row("SKIP", "already.pkg", reason="already disabled"),
    )


def plan_with_blocked_row() -> PlanData:
    return make_plan(
        plan_row("BLOCKED", "blocked.pkg", reason="it is the current Home app"),
        plan_row("DISABLE", "disable.pkg", why="unused", breaks="Nothing"),
    )


# ---------------------------------------------------------------------------
# The brief's exact assertions
# ---------------------------------------------------------------------------


def test_documented_plan_with_only_manual_rows_is_allowed():
    plan = PlanData(
        profile_id="pixel-8-documented",
        match=True,
        verification="documented",
        auto_apply=False,
        rows=(plan_row("ASK", "com.example.ask"),),
    )
    assert plan_allows_review(plan) is True


def test_documented_plan_with_a_disable_row_is_rejected():
    plan = PlanData(
        profile_id="pixel-8-documented",
        match=True,
        verification="documented",
        auto_apply=False,
        rows=(plan_row("DISABLE", "com.example.bloat"),),
    )
    assert plan_allows_review(plan) is False


def test_untested_device_plan_is_still_rejected():
    plan = PlanData(
        profile_id="pixel-8",
        match=True,
        verification="device",
        auto_apply=False,
        rows=(plan_row("ASK", "com.example.ask"),),
    )
    assert plan_allows_review(plan) is False


def test_disable_rows_are_checked_and_ask_rows_are_not():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())
    assert model.is_checked("disable.pkg") is True
    assert model.is_checked("ask.pkg") is False
    assert model.selected_packages() == ("disable.pkg",)


def test_checking_an_ask_row_adds_it():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())
    model.toggle("ask.pkg")
    assert model.selected_packages() == ("disable.pkg", "ask.pkg")


def test_blocked_rows_are_not_selectable():
    model = ReviewModel.from_plan(plan_with_blocked_row())
    assert "blocked.pkg" not in model.selectable_packages()


# ---------------------------------------------------------------------------
# Selection and row sections
# ---------------------------------------------------------------------------


def test_selectable_packages_keep_plan_order_and_exclude_non_actionable_rows():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())

    assert model.selectable_packages() == ("disable.pkg", "ask.pkg")
    assert model.tested_rows() == (plan_with_disable_and_ask().rows[0],)
    assert model.ask_rows() == (plan_with_disable_and_ask().rows[1],)


def test_blocked_rows_include_blocked_skipped_missing_and_keep_rows():
    plan = make_plan(
        plan_row("DISABLE", "disable.pkg"),
        plan_row("ASK", "ask.pkg"),
        plan_row("BLOCKED", "blocked.pkg", reason="role"),
        plan_row("SKIP", "skip.pkg", reason="already disabled"),
        plan_row("MISSING", "missing.pkg", reason="not installed"),
        plan_row("KEEP", "keep.pkg", reason="never touch"),
    )
    model = ReviewModel.from_plan(plan)

    assert tuple(row.package for row in model.blocked_rows()) == (
        "blocked.pkg",
        "skip.pkg",
        "missing.pkg",
        "keep.pkg",
    )


def test_toggling_a_non_selectable_row_is_rejected():
    model = ReviewModel.from_plan(plan_with_blocked_row())

    with pytest.raises(ValueError):
        model.toggle("blocked.pkg")
    with pytest.raises(ValueError):
        model.set_checked("blocked.pkg", True)


def test_toggling_an_unknown_row_is_rejected():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())

    with pytest.raises(ValueError):
        model.toggle("not.in.the.plan")


def test_set_checked_can_uncheck_a_disable_row():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())

    model.set_checked("disable.pkg", False)

    assert model.is_checked("disable.pkg") is False
    assert model.selected_packages() == ()


def test_selected_packages_follow_plan_order_not_click_order():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())
    model.toggle("ask.pkg")
    model.set_checked("disable.pkg", False)
    model.set_checked("disable.pkg", True)

    assert model.selected_packages() == ("disable.pkg", "ask.pkg")


# ---------------------------------------------------------------------------
# Re-planning before apply
# ---------------------------------------------------------------------------


def test_intersect_with_plan_removes_packages_that_are_no_longer_actionable():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())
    model.toggle("ask.pkg")
    assert model.selected_packages() == ("disable.pkg", "ask.pkg")

    new_plan = make_plan(
        plan_row("DISABLE", "disable.pkg", why="unused", breaks="Nothing"),
        plan_row("BLOCKED", "ask.pkg", reason="it is the current keyboard"),
    )
    model.intersect_with_plan(new_plan)

    assert model.selected_packages() == ("disable.pkg",)
    assert model.is_checked("ask.pkg") is False


def test_intersect_with_plan_does_not_add_new_disable_rows():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())

    new_plan = make_plan(
        plan_row("DISABLE", "disable.pkg"),
        plan_row("ASK", "ask.pkg"),
        plan_row("DISABLE", "newly.pkg"),
    )
    model.intersect_with_plan(new_plan)

    assert model.selected_packages() == ("disable.pkg",)
    assert model.is_checked("newly.pkg") is False


def test_intersect_with_plan_keeps_a_still_actionable_ask_selection():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())
    model.toggle("ask.pkg")

    new_plan = make_plan(
        plan_row("ASK", "ask.pkg", why="still optional"),
        plan_row("BLOCKED", "disable.pkg", reason="role"),
    )
    model.intersect_with_plan(new_plan)

    assert model.selected_packages() == ("ask.pkg",)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_from_plan_requires_a_plan_data():
    with pytest.raises(TypeError):
        ReviewModel.from_plan("not a plan")


def test_intersect_with_plan_requires_a_plan_data():
    model = ReviewModel.from_plan(plan_with_disable_and_ask())

    with pytest.raises(TypeError):
        model.intersect_with_plan(None)
