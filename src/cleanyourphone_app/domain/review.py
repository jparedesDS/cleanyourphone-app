"""The package review model: what is selectable and what is checked.

The CLI plan is the only source of truth. ``DISABLE`` rows start checked,
``ASK`` rows start unchecked, and every other action (``BLOCKED``, ``SKIP``,
``MISSING``, ``KEEP``) is shown as a not-changed row that cannot be selected.
Before Apply, the page calls :meth:`ReviewModel.intersect_with_plan` so a
package that stopped being actionable can never be sent to ``disable``.
"""

from __future__ import annotations

from .models import PlanData, PlanRow

DISABLE = "DISABLE"
ASK = "ASK"
SELECTABLE_ACTIONS: frozenset[str] = frozenset({DISABLE, ASK})


def _action(row: PlanRow) -> str:
    return row.action.strip().upper()


def _unique(packages: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for package in packages:
        if package in seen:
            continue
        seen.add(package)
        ordered.append(package)
    return tuple(ordered)


def plan_allows_review(plan: PlanData) -> bool:
    """Only an exact, tested, auto-applicable device plan may reach Review."""
    if not isinstance(plan, PlanData):
        raise TypeError("plan must be a PlanData")
    return plan.match and plan.verification == "device" and plan.auto_apply


class ReviewModel:
    """Checked state for one CLI plan, kept free of Qt and filesystem code."""

    def __init__(self, plan: PlanData) -> None:
        if not isinstance(plan, PlanData):
            raise TypeError("plan must be a PlanData")
        self.plan = plan
        self._checked: set[str] = {
            row.package for row in plan.rows if _action(row) == DISABLE
        }

    @classmethod
    def from_plan(cls, plan: PlanData) -> ReviewModel:
        return cls(plan)

    # ------------------------------------------------------------- row groups

    def tested_rows(self) -> tuple[PlanRow, ...]:
        return tuple(row for row in self.plan.rows if _action(row) == DISABLE)

    def ask_rows(self) -> tuple[PlanRow, ...]:
        return tuple(row for row in self.plan.rows if _action(row) == ASK)

    def blocked_rows(self) -> tuple[PlanRow, ...]:
        """Every row the user cannot change, including skipped and missing."""
        return tuple(
            row for row in self.plan.rows if _action(row) not in SELECTABLE_ACTIONS
        )

    def selectable_packages(self) -> tuple[str, ...]:
        return _unique(
            [
                row.package
                for row in self.plan.rows
                if _action(row) in SELECTABLE_ACTIONS
            ]
        )

    # --------------------------------------------------------------- selection

    def _require_selectable(self, package: str) -> None:
        if not isinstance(package, str) or not package.strip():
            raise ValueError("package must be a non-empty string")
        if package not in self.selectable_packages():
            raise ValueError(f"{package!r} is not selectable in this plan")

    def is_checked(self, package: str) -> bool:
        if not isinstance(package, str) or not package.strip():
            return False
        return package in self._checked and package in self.selectable_packages()

    def set_checked(self, package: str, checked: bool) -> bool:
        if not isinstance(checked, bool):
            raise TypeError("checked must be a boolean")
        self._require_selectable(package)
        if checked:
            self._checked.add(package)
        else:
            self._checked.discard(package)
        return self.is_checked(package)

    def toggle(self, package: str) -> bool:
        self._require_selectable(package)
        return self.set_checked(package, not self.is_checked(package))

    def selected_packages(self) -> tuple[str, ...]:
        return _unique(
            [
                row.package
                for row in self.plan.rows
                if _action(row) in SELECTABLE_ACTIONS
                and row.package in self._checked
            ]
        )

    def selected_count(self) -> int:
        return len(self.selected_packages())

    # ------------------------------------------------------------- re-planning

    def intersect_with_plan(self, new_plan: PlanData) -> tuple[str, ...]:
        """Keep only still-actionable selections and adopt *new_plan*.

        The intersection deliberately never adds a package. A re-plan that
        introduces a new ``DISABLE`` row leaves it unchecked so the user sees
        the change instead of silently widening the selection.
        """
        if not isinstance(new_plan, PlanData):
            raise TypeError("new_plan must be a PlanData")
        still_selectable = {
            row.package
            for row in new_plan.rows
            if _action(row) in SELECTABLE_ACTIONS
        }
        self._checked &= still_selectable
        self.plan = new_plan
        return self.selected_packages()


__all__ = [
    "ASK",
    "DISABLE",
    "SELECTABLE_ACTIONS",
    "ReviewModel",
    "plan_allows_review",
]
