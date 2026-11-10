# CleanYourPhone app MVP: design

Date: 2026-11-10

Status: draft for review

## Intent

Give Windows users a safe, short, guided path through the existing CleanYourPhone safety rules. The app is not a second debloat engine. It is a local desktop front end for the CLI, limited to phones with an exact `verification: device` profile and a tested build.

The app opens, helps the user connect the phone (Wi-Fi first), backs up, shows exactly what will be disabled, applies it in verified batches of five, and leaves an undo action. If the phone is not an exact supported case, the app stops before changing anything and points the user to the skill on the website.

## Why

The skill is the main product, but some people will not use a terminal or an agent. The app should make the same conservative flow approachable without weakening it. The current app repository is empty; this design defines the first shippable MVP, not the final product.

## Users

- A Windows 10/11 x64 user with a supported Android phone.
- They want buttons, a short flow and clear explanations.
- They may not know what ADB is.
- They may be Spanish or English speaking.
- They are not a managed/work phone, a TV, a multi-user phone, or a phone older than Android 8.

## Goals

1. Open the app and finish the flow with the fewest possible user actions.
2. Prefer ADB over Wi-Fi; fall back to USB when Wi-Fi pairing is not possible.
3. Use the existing CLI as the only source of safety rules.
4. Never change the phone without a fresh backup.
5. Never apply a documented/reference profile or an untested build.
6. Show every package that will be disabled, why it is listed and what can break.
7. Apply in batches of five, verify after each batch, and roll back a failed batch.
8. Leave a clear undo action.
9. If the phone is unsupported, explain why, link to the skill website, and change nothing.
10. Keep the app local: no account, no cloud, no telemetry.

## Non-goals

- macOS or Linux.
- Building or shipping the app for Android.
- Root, ROMs, bootloader unlock, Shizuku, Magisk or uninstalling packages.
- Editing profiles or building new package lists.
- Per-package restore. MVP undo restores the whole journal for that phone, including older
  CleanYourPhone sessions, and says so clearly before confirming.
- Auto-update or an in-app store.
- Code signing in the first MVP.
- Bundling Google Platform-Tools binaries.

## Anti-goals

- A dashboard full of advanced options.
- A generic "clean everything" button.
- A flow that continues when the model, build, roles, backup or ADB state is unknown.
- A promise of zero failures. The promise is: stop before changing anything when the state is not safe, and keep the undo path.
- Reading or uploading the user's package list, accounts, messages or files.

## Supported scope

The app allows changes only when all of these are true:

- `probe` reports a normal phone, not a TV.
- `managed` is `false`, not unknown.
- `users` is exactly `1`.
- SDK is 26 or newer.
- A profile with `verification: "device"` matches the model.
- The current build is in that profile's `tested` list, so `auto_apply` is true.
- The CLI role and protected-package checks pass.
- A fresh backup exists for the current fingerprint.

If any condition fails, the app stops and shows a reason. For a missing exact device profile or untested build, the primary action is **"Hacerlo con la skill"**, opening `https://jparedesds.github.io/cleanyourphone-web/`. For a managed phone, TV, multi-user phone or old Android, the app links to the relevant safety documentation instead of pretending the skill will bypass the same rule.

## Flow

1. **Welcome.** "Conecta tu móvil". Short explanation: local, reversible, no root, no uninstall. Buttons: **Wi-Fi** and **USB**. A small "¿Ya está conectado?" link runs discovery first.
2. **Connect.**
   - Wi-Fi on Android 11+: show the phone steps to open Wireless debugging and "Pair device with pairing code"; accept the pairing code and, when discovery fails, the IP:port fields.
   - Android 8-10: USB only in the MVP. The current auto-apply device profiles are Android 11+, so the extra legacy Wi-Fi path is not built yet.
   - USB: show the Developer options and "Allow USB debugging" steps; detect the device automatically.
   - The app can skip this screen when exactly one usable device is already connected. If there is more than one, show a chooser labelled by model and transport (USB or Wi-Fi), never by raw serial.
3. **Check.** Run `cleanyourphone --json probe`. Show model, Android version, build, battery and connection. Run the supported-scope checks. If unsupported, show the stop screen and link; nothing has changed.
4. **Backup.** Run `backup` automatically. Show a progress indicator and the backup path. If it fails, stop; there is no skip.
5. **Review.** Run `cleanyourphone --json plan --profile <id>`.
   - **Tested list:** every `DISABLE` row is checked by default. The user can uncheck any row.
   - **Ask list:** every `ASK` row is unchecked by default. The user can check the apps they want to disable.
   - **Blocked/skipped:** collapsed section with counts and reasons; not actionable.
   - Each row shows a friendly name if available, the package id, `why`, and `breaks`.
   - The primary button says exactly how many packages will be disabled: "Desactivar 7 apps". It is disabled when the selection is empty.
6. **Apply.** Split the selected packages into batches of at most five. Immediately before each batch, re-run `plan --json` and intersect the batch with the rows that are still actionable; this is defense in depth because `disable` does not re-check profile membership. For each batch, call the CLI `disable` command, which re-checks protected packages, roles and the backup, verifies the phone and attempts to roll back the batch if verification fails. Show "Lote 2 de 3" and the package names. Do not allow closing the window during a batch; allow "Detener al terminar este lote" between batches. After a failed batch, inspect the actual disabled set and show which selected packages remain disabled instead of claiming the phone is unchanged.
7. **Done.** Show the number disabled, the verification result, the backup path and the undo button. The undo action explains that it restores **every CleanYourPhone change recorded for this phone**, shows a dry-run summary, asks for confirmation, then calls `restore`. If an older journal exists on launch, show a banner offering to review and undo it with the same wording.

## Screen copy rules

- Say **desactivar**, not **quitar** or **desinstalar**. The app never uninstalls.
- Say **dejar como está**, not **mantener** or **no limpiar**.
- Every stop screen says what happened, what was not changed, and what to do next.
- Every unsupported-device screen links to the skill website.
- The app never claims "sin fallos" or "seguro al 100%". It says "si algo no cuadra, no se cambia nada y puedes deshacer".
- Spanish and English are both first-class. Default to the Windows UI language when it is Spanish or English; otherwise English. A language switch is always visible.
- Profile `why` and `breaks` strings are English-only in the CLI. The app bundles a Spanish catalog keyed by package id for the packages in the bundled device profiles. Missing entries fall back to English with a visible "Detalles en inglés" note; the app does not invent translations.

## Safety invariants

1. The app never calls `adb` directly for package changes. The CLI performs every write.
2. The app never applies a package that is not in the selected profile's `DISABLE` or `ASK` rows.
3. The app never applies a profile whose verification is not `device` or whose build is not in `tested`.
4. The app never proceeds without a backup created in this session for the current fingerprint.
5. The app never bypasses a CLI refusal. It displays the refusal and stops.
6. The app never offers a "skip backup" or "ignore warning" control.
7. The app never uses `pm uninstall`, `pm hide`, `pm clear`, root, Shizuku or a custom ROM.
8. The app never logs pairing codes, serial numbers, account identifiers or package contents.
9. The app never sends telemetry. Its only network request is the user-initiated Platform-Tools download from Google.

## Architecture

- **UI:** Python 3.12, PySide6 (Qt Widgets), one native window. No web view, no local server.
- **Engine:** the CleanYourPhone CLI, built as a frozen sidecar executable from a pinned release tag (initially `v0.2.2`). The app calls it with `subprocess`, sets `ADB` to the selected adb path, and keeps the CLI as the only write path.
- **Structured reads:** `cleanyourphone --json probe`, `--json plan --profile <id>` and `--json verify` for machine-readable data. `--json` is a top-level flag in the current CLI.
- **Writes:** `backup`, `disable`, `restore`. The app uses exit codes and captured output; it does not parse human output for safety decisions.
- **Batch model:** the app calls `disable` with at most five packages per call. The CLI verifies and rolls back each batch. The app stops after the first failed batch.
- **State:** session state in memory. Persistent files are the CLI's backup and undo journal under `%USERPROFILE%\.cleanyourphone\`, plus app settings in `%LOCALAPPDATA%\CleanYourPhone\settings.json`. No database.
- **Logs:** local rotating log in `%LOCALAPPDATA%\CleanYourPhone\logs\`. Redact serials, pairing codes, IP addresses and package lists from the log. "Copiar detalles" copies the last error without those values.
- **Build:** PyInstaller one-folder app; Inno Setup per-user installer. The build fetches the pinned CLI tag, builds the sidecar, includes the profiles, and smoke-tests `cleanyourphone --version` and `cleanyourphone validate` from the frozen exe.

## ADB acquisition

Google's Platform-Tools licence does not clearly allow redistribution of the prebuilt `adb`. The MVP therefore does not put Google's binaries in the installer.

On first run, the app looks for adb in this order:

1. `ADB` environment variable.
2. `adb` on `PATH`.
3. `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`.
4. The app's own cache at `%LOCALAPPDATA%\CleanYourPhone\platform-tools\adb.exe`.

If none exists, show a one-time **Android Platform-Tools** screen:

- Explain that Google requires a separate download and link to Google's SDK terms.
- **Descargar de Google**: download the official Windows Platform-Tools zip, verify a pinned SHA-256, extract only the files needed to run adb, and store them in the app cache.
- **Ya tengo ADB**: file picker for `adb.exe`.
- If offline, the user can cancel and return later.

This is the one intentional network request. It happens only with user action and only when adb is missing. The app never redistributes Google's binaries.

If a fully offline installer is required later, the alternative is to build adb from AOSP under Apache-2.0 and bundle that build. That is a separate distribution project.

## Wi-Fi connection

### Android 11 and newer

1. Phone: Developer options → Wireless debugging → Pair device with pairing code.
2. App: use `adb mdns services` to find `_adb-tls-pairing._tcp` and `_adb-tls-connect._tcp`.
3. App: `adb pair <host>:<pair-port> <code>`.
4. App: `adb connect <host>:<connect-port>`.
5. If mDNS fails, show two fields for the pairing IP:port and the code, then one field for the connection IP:port.

### Android 8 to 10

Not in the MVP. The current auto-apply device profiles are Android 11+, so older phones use USB
only if they ever gain a supported device profile. The legacy `adb tcpip 5555` flow is deferred.

### Minimum ADB version

The app requires Platform-Tools 31.0.0 or newer for Wireless debugging and `adb mdns`. If it finds
an older adb, it offers the official download or the file picker instead of letting Wi-Fi pairing
fail silently.

### Failure handling

- If pairing fails, show the exact phone step that is usually missing and offer USB.
- If the phone sleeps or the Wi-Fi network changes, show "Reconectar" and keep the selected profile.
- Never store the pairing code. Do not put it in logs.

## Visual design

- Graphite `#121316` background, panel `#1B1C21`, text `#F3F1EC`, purple `#A78BFA`, muted `#A19E96`.
- Same logo and wordmark as the website. Segoe UI for copy, Cascadia Code for package ids and commands.
- One primary action per screen. Large touch targets. Keyboard focus visible. No dense tables.
- Window minimum 900×640; scales to 125%/150% Windows scaling.
- No external fonts, no stock photos, no mockups inside the app.

## Error model

Every error screen has:

- **Qué ha pasado:** one sentence in plain language.
- **Qué no se ha cambiado:** explicit reassurance when true.
- **Qué puedes hacer:** one or two actions.
- **Detalles:** expandable, redacted, with "Copiar detalles" and "Abrir logs".
- **Hacerlo con la skill:** shown when the limitation is profile/build coverage, with the website link.

Examples:

- No exact profile → "No tenemos un perfil probado para este móvil y esta versión. No se ha cambiado nada." + skill link.
- Build changed after OTA → same, plus "El perfil existe, pero esta compilación no está probada."
- Managed phone → "Este móvil está gestionado por una empresa. La app no puede cambiar paquetes." + safety docs.
- Backup failure → "No se pudo crear la copia. No se ha cambiado nada." + retry.
- Role read failure → "No se pudo comprobar el teléfono, SMS, Home o teclado. No se ha cambiado nada." + retry.
- Batch verification failure → "El lote intentó deshacerse. Revisamos el móvil; estos paquetes siguen desactivados: …" + "Deshacer todo" + logs. Never claim the phone is unchanged until the app has checked the actual disabled set.

## Testing

- Unit tests for the session state machine, batch splitting, supported-scope decisions, ADB output parsing, Wi-Fi discovery parsing, CLI error mapping and settings.
- UI tests with `pytest-qt` for the happy path and stop screens, using a fake CLI executable with canned JSON and exit codes.
- Contract tests against the real CLI in a temporary profile/state directory: `--json probe`, `--json plan` and `--json verify` shapes.
- Manual device checklist on at least one supported phone: Wi-Fi pairing, USB fallback, backup, review, one batch, verification, undo. No profile is promoted or claimed as tested by this app.
- Packaging test on a clean Windows VM: install, launch, first-run ADB download (or select existing adb), CLI version check.
- CI on `windows-latest` Python 3.12: tests, build, artifact. No code signing in MVP.

## Distribution

- App version `0.1.0`.
- Installer: `CleanYourPhone-Setup-0.1.0.exe`, per-user, no admin.
- GitHub release in `cleanyourphone-app` with installer, SHA-256 and release notes.
- Website: after the first release, change the app status card to a download link and update the app README. Until the release exists, keep the current status-only copy.
- No auto-update. The app can show "Buscar actualización" that opens the releases page; it does not download or install updates silently.

## Approaches considered

### A. Python + PySide6 with the CLI as a sidecar (chosen)

One language, direct reuse of the CLI, a native Windows window, and a packaging path that is well understood. Cost: larger installer and a Qt UI that is functional rather than web-modern.

### B. Tauri + web UI + Python CLI sidecar

A more modern UI and a smaller shell, but two languages, more packaging and process-management complexity, and a longer path to the first reliable MVP. Revisit after the flow is proven.

### C. C#/.NET WPF or WinUI with native ADB calls

The best Windows integration, but it duplicates the protected list, role checks, backup and undo rules. That is a safety and maintenance risk. Rejected for the MVP.

## Decisions

- Windows 10/11 x64 first.
- PySide6, not Tauri or WPF.
- Only exact `device` profiles with a tested build.
- `DISABLE` rows checked by default; `ASK` rows unchecked by default.
- No per-package restore in MVP; undo restores the whole journal for that phone and says so.
- One transport per session; cross-transport undo uses `restore --from-backup` with an explicit reconstruction warning.
- The app calls `disable` in batches of five rather than `apply`, so the UI controls progress and can stop between batches while the CLI still verifies and rolls back each batch.
- Before each batch, the app re-runs `plan --json` and intersects the batch with the still-actionable rows.
- Android 8-10 Wi-Fi is deferred; USB only if an older phone ever gets a supported device profile.
- ADB is acquired on first run, not redistributed.
- Minimum adb version is 31.0.0 for Wi-Fi pairing and mDNS; older adb is treated as not suitable.
- The app bundles a Spanish catalog for the supported profiles' `why`/`breaks` strings, with English fallback.
- Bilingual English/Spanish from the first release.
- No telemetry, no account, no cloud.

## Session and undo: pin one transport

The CLI keys backups and the undo journal by the exact ADB serial. USB and Wi-Fi have different
serials, and a wireless debugging port can change after a reconnect. Reconnecting the phone another
way can make `disable` say it has no backup and `restore` say there is nothing to restore.

The MVP pins one transport for the whole session:

- The app records the exact serial and backup path in memory.
- The connection stays the same for check → backup → review → apply → undo.
- The app does not offer a USB/Wi-Fi switch in the middle of a session.
- If undo is needed later and the original serial is not connected, the app asks the user to
  reconnect the same way. It offers `restore --from-backup` only after explaining that it
  reconstructs the state from the backup rather than replaying the exact journal.
- If real use shows that transport changes are common, the future fix is to key backups and the
  journal by a stable fingerprint in the CLI. That is not part of this MVP.

## Open risks

- The Wi-Fi pairing UI varies by OEM and Android version; mDNS may be blocked by Windows firewall or the router. USB fallback must be first-class.
- The first-run ADB download is an extra step and needs internet. If that is unacceptable, the project needs an Apache-2.0 adb build.
- PySide6 + PyInstaller produces a large installer; unsigned builds will trigger SmartScreen.
- The CLI's `disable` output is human-readable. The app can rely on exit codes and its selected list, but better machine-readable write output is a future improvement.
- Testing is limited to the phones available to the maintainer. The app must not claim broad device support.
- The Spanish catalog can lag behind profile changes. Unknown packages fall back to English; the app must not show a half-translated row without the fallback note.
- Undo across USB and Wi-Fi is not seamless in the MVP because the CLI keys state by serial. The app must explain the limitation instead of failing silently.
- The app could become a second product with its own maintenance burden. Keep the MVP narrow and reuse the CLI.

## What is left to the builder

- Choose the exact PySide6 widget structure and visual polish.
- Choose the ADB download UI copy and checksum update process.
- Choose the installer branding, licence notices and file layout.
- Define the precise redaction rules for logs.
- Write the Spanish catalog for the packages in the bundled device profiles, with English fallback.
- Choose the pinned Platform-Tools download version and its SHA-256 update process.
- Write the detailed implementation plan and test fixtures.
