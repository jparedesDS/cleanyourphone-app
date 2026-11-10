#!/usr/bin/env python3
"""Fail the build when a device profile package has no Spanish detail entry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _APP_ROOT / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from cleanyourphone_app.i18n.packages import PackageCatalog  # noqa: E402


def device_package_ids(profiles_dir: Path) -> set[str]:
    """Collect every ``disable``/``ask`` package from ``verification: device``."""
    if not profiles_dir.is_dir():
        raise FileNotFoundError(f"profiles directory not found: {profiles_dir}")

    package_ids: set[str] = set()
    for path in sorted(profiles_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"could not read profile {path}: {error}") from error
        if not isinstance(payload, dict):
            continue
        if payload.get("verification") != "device":
            continue
        for section in ("disable", "ask"):
            entries = payload.get(section, [])
            if entries is None:
                continue
            if not isinstance(entries, list):
                raise ValueError(f"{path}.{section} must be a list")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError(f"{path}.{section} entries must be objects")
                package_id = entry.get("package")
                if not isinstance(package_id, str) or not package_id.strip():
                    raise ValueError(
                        f"{path}.{section} has an entry without a package id"
                    )
                package_ids.add(package_id.strip())
    return package_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that the Spanish package catalog covers every package in "
            "the verification=device profiles."
        )
    )
    parser.add_argument(
        "--profiles",
        required=True,
        type=Path,
        help="root directory containing the profile JSON files",
    )
    parser.add_argument(
        "--catalog",
        required=True,
        type=Path,
        help="packages_es.json catalog to check",
    )
    arguments = parser.parse_args(argv)

    try:
        catalog = PackageCatalog.from_file(arguments.catalog)
        required = device_package_ids(arguments.profiles)
    except (OSError, ValueError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    missing = sorted(required - set(catalog.package_ids()))
    if missing:
        print(
            f"{len(missing)} package(s) missing from {arguments.catalog}:",
            file=sys.stderr,
        )
        for package_id in missing:
            print(package_id, file=sys.stderr)
        return 1

    print(
        f"catalog covers {len(required)} package(s) across device profiles",
        file=sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
