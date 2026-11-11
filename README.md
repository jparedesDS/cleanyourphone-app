<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — your phone, minus the bloat" width="100%">
  </a>
</p>

<p align="center">
  <b>Optional Windows app</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill and CLI</a> ·
  <a href="https://cleanyourphone.org/">Website</a> ·
  <a href="https://cleanyourphone.org/#feedback">Feedback</a>
</p>

<p align="center">
  <b>English</b> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/jparedesDS/cleanyourphone-app/releases"><img src="https://img.shields.io/github/v/release/jparedesDS/cleanyourphone-app?color=a78bfa&labelColor=121316" alt="release"></a>
  <img src="https://img.shields.io/badge/Windows-10%2F11%20x64-a78bfa?labelColor=121316" alt="Windows 10/11 x64">
  <img src="https://img.shields.io/badge/license-MIT-a78bfa?labelColor=121316" alt="MIT">
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="No telemetry">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="Tested on OnePlus 6T">
</p>

# CleanYourPhone app

**The optional Windows app for the CleanYourPhone skill.** A local, reversible debloat flow for
people who prefer buttons over prompts: connect, check, back up, review every package, apply in
batches, verify and undo. The skill remains the main product; this app is the simple path for the
phones it can verify.

[Download the Early MVP](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[Skill and CLI](https://github.com/jparedesDS/cleanyourphone) ·
[Connection guide](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[Feedback](https://cleanyourphone.org/#feedback)

## Status

`v0.2.1` is an Early MVP, Windows 10/11 x64 only, and **not code-signed**. It was tested end to end
on a **OnePlus 6T (Android 11)**: connect, check, backup, review, disable one package, verify, done
and undo.

The app deliberately refuses to guess. It continues only when it can match:

| Phone | What the app does |
|---|---|
| Exact `device` profile with a build listed in `tested` | Guided flow with the tested package list. |
| `documented` profile that matches model, firmware family and Android version | Shows a warning, requires an explicit acknowledgement and applies **one package per batch**. |
| Same model but a different build or OTA | Stops and links to the skill. |
| No profile, managed phone, multiple users, Android < 8 or TV | Stops and links to the skill or the safety docs. |

A `documented` profile comes from a firmware dump. It is evidence, not a real-device test; packages
can differ by region, carrier or update.

<p align="center">
  <img src="docs/images/app-review.png" alt="CleanYourPhone app review screen with a documented profile warning, one selected app and the undo-ready backup path" width="760">
</p>

## What it does

- **Wi-Fi or USB.** Pair Android 11+ over Wireless debugging, or use a data cable. The app finds the
  phone, checks the build and keeps one transport for the session.
- **Exact profile check.** Shows model, Android version, build, battery, profile and whether the
  build is auto-applicable.
- **Mandatory backup.** Package list, roles, settings and `getprop` before the first change.
- **Review every package.** `DISABLE`, `ASK`, `BLOCKED` and `SKIP`, with why it is listed and what
  can break. Nothing is disabled without a reviewed selection.
- **Batches and verification.** Five packages per batch for a `device` profile; one per batch for a
  `documented` profile, with a phone check after each one.
- **Undo the whole journal.** One action restores every change the app recorded for that phone,
  including older sessions. The backup is the fallback.
- **Optional Private DNS.** AdGuard, AdGuard Family, Control D and Mullvad presets, plus a check
  that does not claim YouTube ads are blocked. See
  [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md).
- **Optional before/after benchmark.** Local free RAM, processes and package counts. Approximate,
  not causal; no serial or fingerprint is stored.
- **Optional feedback.** A prefilled, editable checklist can be sent to the maintainer after explicit
  consent. No automatic telemetry. See
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md).

<p align="center">
  <img src="docs/images/app-connect.png" alt="CleanYourPhone connect screen with Wi-Fi and USB instructions and the connection guide link" width="760">
</p>

## Install

Download `CleanYourPhone-Setup-0.2.1.exe` from
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest), or build it
locally.

SHA-256 of the published `v0.2.1` installer:

```text
B522B70B5F56B837EEE54F60D726C56F742667CF6B8B1BE52A913DD99C2D98E1
```

The installer is per-user, creates a Start Menu shortcut, and does not require administrator rights.
It installs to `%LOCALAPPDATA%\Programs\CleanYourPhone`.

Windows SmartScreen may show **"Windows protected your PC"** because the build is not signed. Choose
**More info → Run anyway** only after verifying the download and the SHA-256. Do not disable
SmartScreen.

If this is your first time using ADB, follow the
[connection guide](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md). It covers
the hidden Wireless debugging screen, the pairing port versus the connection port, USB data cables,
Windows drivers and the browser desktop-site setting.

Uninstalling removes the app files and shortcuts. It intentionally leaves the undo journal and phone
backups in `%USERPROFILE%\.cleanyourphone`, and settings in `%LOCALAPPDATA%\CleanYourPhone`.

ADB is not bundled or redistributed. The app finds an existing Platform-Tools installation or
downloads the official archive from Google on first run. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Safety model

The app is a GUI over the same CLI; the guardrails do not move:

- **Disable, never uninstall.** Only `pm disable-user --user 0`; `pm enable` is the undo.
- **No root, no custom ROM, no bootloader unlock, no Shizuku.**
- **No backup, no changes.** The apply button stays disabled without a verified backup.
- **Protected packages and roles are refused.** Telephony, Play Services, WebView, permission
  controller, emergency alerts, the current dialer, SMS, Home and keyboard cannot be disabled.
- **One transport per session.** Switching Wi-Fi/USB mid-session is refused; start a new session.
- **Stop on unknown.** Managed devices, multiple users, Android < 8, TVs and phones without a matching
  profile are not changed.
- **No automatic telemetry.** The app is local. Its only network calls are the optional Google
  Platform-Tools download and the feedback form after the person presses Send.

## Build

Requirements: Windows 10/11 x64, Python 3.12+, Git, and Inno Setup 6
(`choco install innosetup -y` or <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

The script:

1. clones the pinned CLI tag (`v0.3.3`);
2. freezes the CLI as an onedir sidecar;
3. stages the 156 profiles;
4. freezes the PySide6 app;
5. smoke-tests both executables;
6. compiles the per-user installer.

Outputs:

- `dist/CleanYourPhone/CleanYourPhone.exe` (portable onedir app)
- `dist/CleanYourPhone-Setup-0.2.1.exe` (installer)

Set `CLEANYOURPHONE_CLI` to the frozen sidecar and run
`python -m pytest tests/test_cli_contract.py` to include the real-sidecar contract test.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

The app suite covers the connection guards, serial pinning, documented-profile acknowledgement,
one-per-batch apply, backup gating, undo, feedback payloads, feedback consent and UI copy. The
published `0.2.1` suite result is **520 passed, 1 skipped**.

## Repository map

| Path | What it is |
|---|---|
| `src/cleanyourphone_app/domain/` | Pure rules: support decision, review model, session, batches, feedback payload. |
| `src/cleanyourphone_app/services/` | ADB locator, Wi-Fi pairing, CLI client, downloads, feedback HTTP client, logging, settings. |
| `src/cleanyourphone_app/ui/pages/` | Connect, check, backup, review, apply, done, setup, welcome, blocked. |
| `src/cleanyourphone_app/ui/dialogs/` | Optional feedback dialog. |
| `scripts/build-cli-sidecar.ps1` | Builds the pinned CLI sidecar and stages profiles. |
| `scripts/build-app.ps1` | Builds the app, smoke-tests it and compiles the installer. |
| `packaging/installer.iss` | Per-user Inno Setup installer. |
| `docs/superpowers/` | Historical design and implementation plan. |
| `tests/` | Pytest suite; 520 passing, 1 skipped on `0.2.1`. |

## Limitations

- Windows 10/11 x64 only. There is no macOS or Linux desktop app yet.
- The build is not code-signed.
- It only supports the exact profiles and builds above; every other phone is sent to the skill.
- `documented` mode is covered by the app suite, not yet by a physical documented device.
- ADB still requires Developer options and an authorised computer.

## Links

- **Skill and CLI:** <https://github.com/jparedesDS/cleanyourphone>
- **Website:** <https://cleanyourphone.org/>
- **Connection guide:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **Feedback and privacy:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **Profiles:** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **Safety:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## License

MIT. See [LICENSE](LICENSE). Third-party notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
