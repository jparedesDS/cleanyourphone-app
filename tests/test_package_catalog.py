"""Spanish package details: catalog lookup, coverage and row fallback."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cleanyourphone_app.domain.models import PlanRow
from cleanyourphone_app.i18n.packages import PackageCatalog
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.ui.widgets.package_row import PackageRow

APP_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    APP_ROOT / "src" / "cleanyourphone_app" / "i18n" / "packages_es.json"
)
CHECK_SCRIPT = APP_ROOT / "scripts" / "check_package_catalog.py"
SOURCE_PROFILES = Path(
    os.environ.get(
        "CLEANYOURPHONE_PROFILES",
        str(APP_ROOT.parent / "cleanyourphone" / "profiles"),
    )
)

DEVICE_PROFILE_NAMES = ("pixel-8", "oneplus-a6013", "sm-s918b", "hyperos")


@pytest.fixture(scope="module")
def catalog() -> PackageCatalog:
    return PackageCatalog.from_file(CATALOG_PATH)


def plan_row(
    package: str,
    why: str = "English reason",
    breaks: str = "English breakage",
    *,
    action: str = "ASK",
) -> PlanRow:
    return PlanRow(action=action, package=package, why=why, breaks=breaks)


# ---------------------------------------------------------------------------
# PackageCatalog
# ---------------------------------------------------------------------------


def test_known_package_returns_spanish(catalog):
    text, translated = catalog.lookup(
        "com.google.android.apps.wellbeing", "why", "screen time"
    )
    assert translated is True
    assert text
    assert text != "screen time"


def test_known_package_returns_spanish_breaks(catalog):
    text, translated = catalog.lookup(
        "com.google.android.apps.wellbeing", "breaks", "English breakage"
    )
    assert translated is True
    assert text
    assert text != "English breakage"


def test_unknown_package_falls_back_to_english(catalog):
    text, translated = catalog.lookup("com.example.unknown", "why", "English reason")
    assert text == "English reason"
    assert translated is False


def test_missing_field_falls_back_to_english(catalog):
    text, translated = catalog.lookup(
        "com.example.unknown", "breaks", "English breakage"
    )
    assert text == "English breakage"
    assert translated is False


def test_catalog_rejects_an_entry_without_both_fields():
    with pytest.raises(ValueError, match="breaks"):
        PackageCatalog.from_dict({"com.example.app": {"why": "Razón"}})


def test_catalog_rejects_a_blank_field():
    with pytest.raises(ValueError, match="why"):
        PackageCatalog.from_dict(
            {"com.example.app": {"why": "  ", "breaks": "Nada visible"}}
        )


def test_catalog_rejects_a_non_object_root(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        PackageCatalog.from_file(path)


def test_catalog_contains_the_98_device_profile_packages(catalog):
    package_ids = catalog.package_ids()
    assert len(package_ids) == 98
    assert len(set(package_ids)) == 98


def test_every_catalog_entry_has_spanish_why_and_breaks(catalog):
    for package_id in catalog.package_ids():
        for field in ("why", "breaks"):
            text, translated = catalog.lookup(package_id, field, "")
            assert translated is True, package_id
            assert text.strip(), f"{package_id}.{field}"


@pytest.mark.skipif(
    not SOURCE_PROFILES.is_dir(), reason="source profile checkout is not available"
)
def test_catalog_covers_every_source_device_profile_package(catalog):
    required: set[str] = set()
    matched_profiles: set[str] = set()
    for path in SOURCE_PROFILES.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        if payload.get("verification") != "device":
            continue
        matched_profiles.add(path.stem)
        for section in ("disable", "ask"):
            for entry in payload.get(section, []):
                required.add(entry["package"])

    assert len(required) == 98
    assert set(DEVICE_PROFILE_NAMES) <= matched_profiles
    missing = sorted(required - set(catalog.package_ids()))
    assert missing == []


# ---------------------------------------------------------------------------
# Coverage script
# ---------------------------------------------------------------------------


def write_profile(
    root: Path,
    name: str,
    packages: tuple[str, ...],
    *,
    verification: str = "device",
) -> Path:
    path = root / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "id": name,
                "verification": verification,
                "disable": [{"package": package} for package in packages[:1]],
                "ask": [{"package": package} for package in packages[1:]],
            }
        ),
        encoding="utf-8",
    )
    return path


def write_catalog(path: Path, packages: tuple[str, ...]) -> Path:
    path.write_text(
        json.dumps(
            {
                package: {"why": "Razón", "breaks": "Consecuencia"}
                for package in packages
            }
        ),
        encoding="utf-8",
    )
    return path


def run_coverage_script(profiles: Path, catalog_path: Path) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [
            sys.executable,
            str(CHECK_SCRIPT),
            "--profiles",
            str(profiles),
            "--catalog",
            str(catalog_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )


def test_coverage_script_exits_zero_when_every_device_package_is_covered(tmp_path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_profile(profiles, "device-one", ("com.example.one", "com.example.two"))
    catalog_path = write_catalog(
        tmp_path / "catalog.json", ("com.example.one", "com.example.two")
    )

    result = run_coverage_script(profiles, catalog_path)

    assert result.returncode == 0, result.stderr
    assert "com.example" not in result.stderr


def test_coverage_script_exits_one_with_every_missing_package_id(tmp_path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_profile(
        profiles, "device-one", ("com.example.covered", "com.example.missing")
    )
    catalog_path = write_catalog(tmp_path / "catalog.json", ("com.example.covered",))

    result = run_coverage_script(profiles, catalog_path)

    assert result.returncode == 1
    assert "com.example.missing" in result.stderr
    assert "com.example.covered" not in result.stderr


def test_coverage_script_only_checks_device_profiles(tmp_path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_profile(profiles, "device-one", ("com.example.covered",))
    write_profile(
        profiles,
        "documented-one",
        ("com.example.not-covered",),
        verification="documented",
    )
    write_profile(
        profiles,
        "reference-one",
        ("com.example.also-not-covered",),
        verification="reference",
    )
    catalog_path = write_catalog(tmp_path / "catalog.json", ("com.example.covered",))

    result = run_coverage_script(profiles, catalog_path)

    assert result.returncode == 0, result.stderr


def test_coverage_script_loads_device_profiles_recursively(tmp_path):
    profiles = tmp_path / "profiles"
    (profiles / "vendor").mkdir(parents=True)
    write_profile(profiles / "vendor", "device-one", ("com.example.covered",))
    catalog_path = write_catalog(tmp_path / "catalog.json", ("com.example.covered",))

    result = run_coverage_script(profiles, catalog_path)

    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# PackageRow fallback
# ---------------------------------------------------------------------------


def test_package_row_shows_spanish_details_when_the_catalog_has_them(qtbot, catalog):
    row = PackageRow(
        plan_row(
            "com.google.android.apps.wellbeing",
            "Digital Wellbeing: screen-time tracking",
            "Screen-time dashboard and app timers",
        ),
        catalog,
        tr=Translator("es").tr,
    )
    qtbot.addWidget(row)

    assert "Bienestar digital" in row.why_label.text()
    assert "Digital Wellbeing" not in row.why_label.text()
    assert "tiempo de pantalla" in row.why_label.text()
    assert "temporizadores" in row.breaks_label.text()
    assert row.english_note_label.isHidden() is True


def test_package_row_shows_english_and_a_visible_note_when_untranslated(
    qtbot, catalog
):
    row = PackageRow(
        plan_row("com.example.unknown", "English reason", "English breakage"),
        catalog,
        tr=Translator("es").tr,
    )
    qtbot.addWidget(row)

    assert "English reason" in row.why_label.text()
    assert "English breakage" in row.breaks_label.text()
    assert row.english_note_label.text() == "Detalles en inglés"
    assert row.english_note_label.isHidden() is False


def test_package_row_without_a_catalog_still_shows_english_and_the_note(qtbot):
    row = PackageRow(
        plan_row("com.example.unknown", "English reason", "English breakage"),
        None,
        tr=Translator("es").tr,
    )
    qtbot.addWidget(row)

    assert "English reason" in row.why_label.text()
    assert "English breakage" in row.breaks_label.text()
    assert row.english_note_label.text() == "Detalles en inglés"
    assert row.english_note_label.isHidden() is False


def test_package_row_never_blanks_a_known_package(qtbot, catalog):
    row = PackageRow(
        plan_row("com.example.unknown", "English reason", "English breakage"),
        catalog,
    )
    qtbot.addWidget(row)

    assert row.why_label.text().strip()
    assert row.breaks_label.text().strip()
    assert row.name_label.text().strip()


def test_package_row_fills_blank_english_from_the_spanish_catalog(qtbot, catalog):
    row = PackageRow(
        plan_row("com.google.android.apps.wellbeing", "", ""),
        catalog,
        tr=Translator("es").tr,
    )
    qtbot.addWidget(row)

    assert "Bienestar digital" in row.why_label.text()
    assert "tiempo de pantalla" in row.breaks_label.text()
    assert row.english_note_label.isHidden() is True
