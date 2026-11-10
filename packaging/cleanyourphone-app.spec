# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CleanYourPhone desktop app (onedir).

The sidecar and its profiles are staged under ``<repo>/resources`` by
``scripts/build-cli-sidecar.ps1``. ``contents_directory='.'`` keeps
``resources`` and the app executable together at the root of
``dist/CleanYourPhone`` so both the installer and the smoke commands use the
same paths.
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
APP = ROOT / "src" / "cleanyourphone_app"
RESOURCES = ROOT / "resources"

for required in (APP / "ui" / "theme.qss", RESOURCES / "cli", RESOURCES / "profiles"):
    if not required.exists():
        raise SystemExit(
            f"missing packaging input: {required}. "
            "Run scripts/build-cli-sidecar.ps1 before building the app."
        )

datas = [
    (str(APP / "ui" / "theme.qss"), "cleanyourphone_app/ui"),
    (str(APP / "resources" / "logo.svg"), "cleanyourphone_app/resources"),
]
datas += [
    (str(path), "cleanyourphone_app/i18n")
    for path in sorted((APP / "i18n").glob("*.json"))
]

a = Analysis(
    [str(APP / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
a.datas += Tree(str(RESOURCES / "cli"), prefix="resources/cli")
a.datas += Tree(str(RESOURCES / "profiles"), prefix="resources/profiles")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CleanYourPhone",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CleanYourPhone",
)
