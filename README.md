# CleanYourPhone app

**Status: early MVP. The Windows installer `v0.1.0` is published and was tested end to end on a
OnePlus 6T (Android 11).**

This repository holds the optional local app for people who prefer buttons over prompts:
pick a profile, review every package, apply in small batches, and restore from the undo journal.
It can also offer optional Private DNS ad blocking (not YouTube) and show a local before/after
benchmark. No root, no cloud, no telemetry.

The product available today is the agent skill:
[github.com/jparedesDS/cleanyourphone](https://github.com/jparedesDS/cleanyourphone).
The CLI lives in that repository too.

## Release status

- `v0.1.0` publishes the Windows 10/11 x64 installer:
  [releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest).
- Tested on a OnePlus 6T: connect, check, backup, review, disable one package, verify and undo.
- The app only continues on an exact `device` profile with a tested build. On any other phone it
  stops and links to the skill. This is deliberate.
- The build is not code-signed. Verify the SHA-256 before running it.
- The skill remains the main product; the app is the optional path.

## Build the Windows app and installer

Requirements: Windows 10/11 x64, Python 3.12 or newer, Git, and Inno Setup 6
(`choco install innosetup -y` or <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

The script clones the pinned CLI tag (`v0.3.2`), freezes it as an onedir sidecar,
stages its 156 profiles, freezes the Qt app, and compiles the per-user installer.
Outputs:

- `dist/CleanYourPhone/CleanYourPhone.exe` (portable onedir app)
- `dist/CleanYourPhone-Setup-0.1.0.exe` (installer)

The build smoke-tests both executables. Set `CLEANYOURPHONE_CLI` to the frozen
sidecar and run `python -m pytest tests/test_cli_contract.py` to include the
real-sidecar contract test.

## Install 0.1.0

Download `CleanYourPhone-Setup-0.1.0.exe` from
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest), or run the
local build at `dist/CleanYourPhone-Setup-0.1.0.exe`.

SHA-256 of the published `v0.1.0` installer:

```text
48A74C2C9B6FF9000D476B897718EE36319569E3EC5CCAEFFDB3E3EFC533893A
```

It installs for the current user in `%LOCALAPPDATA%\Programs\CleanYourPhone`, creates a Start Menu
shortcut, and does not require administrator rights.

The 0.1.0 build is not code-signed. Windows SmartScreen may show
"Windows protected your PC" on first launch. Choose **More info** and then
**Run anyway** only after verifying the download and the SHA-256. Do not disable
SmartScreen.

If this is your first time using ADB, follow the
[connection guide](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md).

Uninstalling removes the app files and shortcuts. It intentionally leaves your
data in `%USERPROFILE%\.cleanyourphone` (state and phone backups) and
`%LOCALAPPDATA%\CleanYourPhone` (settings). Delete those folders yourself if you
want a clean removal.

ADB is not bundled or redistributed; the app finds an existing installation or
downloads Android SDK Platform Tools from Google on first run. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the CLI, PySide6/Qt and ADB
notices.

## Development

The app is Windows 10/11 x64 only and requires Python 3.12 or newer.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

The app source is MIT. See [LICENSE](LICENSE).
