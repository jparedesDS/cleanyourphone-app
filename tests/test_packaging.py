"""Packaging contracts for the frozen app, sidecar and per-user installer.

These tests are static unless a ``dist`` build already exists, so a normal
``pytest`` run never needs PyInstaller or Inno Setup. The artifact tests turn on
after ``scripts/build-app.ps1`` has produced ``dist/CleanYourPhone``.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from cleanyourphone_app.services.settings import Settings

APP_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_SCRIPT = APP_ROOT / "scripts" / "build-cli-sidecar.ps1"
APP_SCRIPT = APP_ROOT / "scripts" / "build-app.ps1"
SPEC = APP_ROOT / "packaging" / "cleanyourphone-app.spec"
INSTALLER = APP_ROOT / "packaging" / "installer.iss"
NOTICES = APP_ROOT / "THIRD_PARTY_NOTICES.md"
CI = APP_ROOT / ".github" / "workflows" / "ci.yml"

DIST = APP_ROOT / "dist"
APP_EXE = DIST / "CleanYourPhone" / "CleanYourPhone.exe"
SIDECAR_EXE = DIST / "CleanYourPhone" / "resources" / "cli" / "cleanyourphone.exe"
BUNDLED_PROFILES = DIST / "CleanYourPhone" / "resources" / "profiles"
SETUP_EXE = DIST / "CleanYourPhone-Setup-0.1.0.exe"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Build scripts
# ---------------------------------------------------------------------------


def test_sidecar_build_pins_the_cli_tag_and_builds_a_onedir_exe():
    script = read(SIDECAR_SCRIPT)
    assert "https://github.com/jparedesDS/cleanyourphone" in script
    assert "v0.3.2" in script
    assert "v0.2.2" not in script
    assert ".build/cli-src" in script
    assert ".build/cli-venv" in script
    assert "cleanyourphone.phone" in script
    assert "--onedir" in script
    assert "--name" in script and "cleanyourphone" in script
    assert "Lib/site-packages" in script
    assert "profiles" in script
    assert "CleanYourPhone 0.3.2" in script
    assert "156" in script


def test_app_build_runs_the_sidecar_then_the_installer():
    script = read(APP_SCRIPT)
    assert "build-cli-sidecar.ps1" in script
    assert "cleanyourphone-app.spec" in script
    assert "installer.iss" in script
    assert "ISCC" in script
    assert "CleanYourPhone.exe" in script
    assert "CleanYourPhone 0.3.2" in script
    assert "CleanYourPhone-Setup-0.1.0.exe" in script


# ---------------------------------------------------------------------------
# PyInstaller spec
# ---------------------------------------------------------------------------


def test_app_spec_bundles_the_ui_theme_translations_sidecar_and_profiles():
    spec = read(SPEC)
    assert "theme.qss" in spec
    assert "i18n" in spec
    assert "resources" in spec
    assert "resources\\cli" in spec or "resources/cli" in spec
    assert "resources\\profiles" in spec or "resources/profiles" in spec
    assert "COLLECT" in spec
    assert "contents_directory" in spec
    assert "CleanYourPhone" in spec


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------


def test_installer_is_per_user_and_never_touches_user_data():
    iss = read(INSTALLER)
    assert r"DefaultDirName={localappdata}\Programs\CleanYourPhone" in iss
    assert "PrivilegesRequired=lowest" in iss
    assert r"{autoprograms}\CleanYourPhone" in iss
    assert "THIRD_PARTY_NOTICES.md" in iss
    assert "CleanYourPhone-Setup-0.1.0" in iss
    assert not re.search(r"(?m)^\[UninstallDelete\]", iss)


# ---------------------------------------------------------------------------
# Notices and CI
# ---------------------------------------------------------------------------


def test_third_party_notices_cover_pyside_qt_and_the_cli():
    notices = read(NOTICES)
    assert "PySide6" in notices
    assert "LGPL" in notices
    assert "MIT" in notices
    assert "cleanyourphone" in notices.lower()
    assert "ADB" in notices
    assert "not bundled" in notices.lower() or "not redistributed" in notices.lower()


def test_ci_builds_smokes_and_uploads_the_installer():
    workflow = read(CI)
    assert "windows-latest" in workflow
    assert "build-cli-sidecar.ps1" in workflow
    assert "build-app.ps1" in workflow
    assert r"dist\CleanYourPhone\resources\cli\cleanyourphone.exe --version" in workflow
    assert r"dist\CleanYourPhone\CleanYourPhone.exe --version" in workflow
    assert "CleanYourPhone 0.3.2" in workflow
    assert "CleanYourPhone 0.2.2" not in workflow
    assert "choco install innosetup" in workflow
    assert "actions/upload-artifact" in workflow
    assert "CleanYourPhone-Setup-0.1.0.exe" in workflow


# ---------------------------------------------------------------------------
# Runtime wiring
# ---------------------------------------------------------------------------


def test_runtime_environment_points_the_sidecar_at_bundled_data(
    tmp_path, monkeypatch
):
    from cleanyourphone_app.ui import app as app_module

    (tmp_path / "resources" / "profiles").mkdir(parents=True)
    monkeypatch.setattr(app_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_module.sys, "_MEIPASS", str(tmp_path), raising=False)

    env = app_module.runtime_environment("C:/tools/adb.exe")

    assert env["CLEANYOURPHONE_PROFILES"] == str(tmp_path / "resources" / "profiles")
    assert env["CLEANYOURPHONE_BACKUP"] == str(
        Path.home() / ".cleanyourphone" / "backup"
    )
    assert env["CLEANYOURPHONE_STATE"] == str(Path.home() / ".cleanyourphone")
    assert env["ADB"] == "C:/tools/adb.exe"


def test_bundled_sidecar_command_is_used_when_the_exe_exists(tmp_path, monkeypatch):
    from cleanyourphone_app.ui import app as app_module

    sidecar = tmp_path / "resources" / "cli" / "cleanyourphone.exe"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_bytes(b"")
    monkeypatch.setattr(app_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_module.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert app_module.sidecar_command() == (str(sidecar),)


def test_create_context_wires_the_frozen_sidecar(tmp_path, monkeypatch):
    from cleanyourphone_app.ui import app as app_module

    sidecar = tmp_path / "resources" / "cli" / "cleanyourphone.exe"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_bytes(b"")
    (tmp_path / "resources" / "profiles").mkdir()
    monkeypatch.setattr(app_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_module.sys, "_MEIPASS", str(tmp_path), raising=False)

    context = app_module.create_context(Settings.in_memory(language="en"))

    assert context.cli._command == (str(sidecar),)
    assert context.cli._env["CLEANYOURPHONE_PROFILES"] == str(
        tmp_path / "resources" / "profiles"
    )


# ---------------------------------------------------------------------------
# Built artifacts (enabled after scripts/build-app.ps1)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SIDECAR_EXE.is_file(), reason="sidecar has not been built")
def test_built_sidecar_reports_the_pinned_version():
    result = subprocess.run(
        [str(SIDECAR_EXE), "--version"],
        capture_output=True,
        text=True,
        env=_sidecar_env(),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CleanYourPhone 0.3.2"


@pytest.mark.skipif(
    not SIDECAR_EXE.is_file() or not BUNDLED_PROFILES.is_dir(),
    reason="sidecar and profiles have not been built",
)
def test_built_sidecar_validates_156_profiles():
    result = subprocess.run(
        [str(SIDECAR_EXE), "validate"],
        capture_output=True,
        text=True,
        env=_sidecar_env(),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "156 profile(s) valid" in result.stdout


@pytest.mark.skipif(not APP_EXE.is_file(), reason="app has not been built")
def test_built_app_reports_its_version():
    result = subprocess.run(
        [str(APP_EXE), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CleanYourPhone app 0.1.0"


@pytest.mark.skipif(not SETUP_EXE.is_file(), reason="installer has not been built")
def test_installer_artifact_exists():
    assert SETUP_EXE.stat().st_size > 0


def _sidecar_env() -> dict[str, str]:
    env = dict(os.environ)
    env["CLEANYOURPHONE_PROFILES"] = str(BUNDLED_PROFILES)
    return env
