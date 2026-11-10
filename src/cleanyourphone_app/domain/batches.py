"""Split a package selection into batches that the CLI can verify one by one."""

from __future__ import annotations

from collections.abc import Sequence


def split_batches(packages: Sequence[str], size: int = 5) -> list[list[str]]:
    """Return batches of at most ``size`` unique packages, preserving order.

    Duplicates are skipped and no empty batch is emitted. A ``size`` below one
    is a programming error, so it raises ``ValueError`` instead of guessing.
    """
    if size < 1:
        raise ValueError("batch size must be at least 1")

    unique: list[str] = []
    seen: set[str] = set()
    for package in packages:
        if package in seen:
            continue
        seen.add(package)
        unique.append(package)

    return [unique[start : start + size] for start in range(0, len(unique), size)]
