<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — dein Smartphone, ohne Ballast" width="100%">
  </a>
</p>

<p align="center">
  <b>Optionale Windows-App</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill und CLI</a> ·
  <a href="https://cleanyourphone.org/">Website</a> ·
  <a href="https://cleanyourphone.org/#feedback">Feedback</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.fr.md">Français</a> ·
  <b>Deutsch</b> ·
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
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="Keine Telemetrie">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="Getestet auf OnePlus 6T">
</p>

# CleanYourPhone-App

**Die optionale Windows-App für die CleanYourPhone-Skill.** Ein lokaler, reversibler Debloat-Ablauf
für alle, die lieber Schaltflächen als Prompts mögen: verbinden, prüfen, Backup, jedes Paket
überprüfen, in Batches anwenden, verifizieren und rückgängig machen. Die Skill bleibt das
Hauptprodukt; diese App ist der einfache Weg für die Smartphones, die sie verifizieren kann.

[Lade die frühe MVP-Version herunter](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[Skill und CLI](https://github.com/jparedesDS/cleanyourphone) ·
[Verbindungsanleitung](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[Feedback](https://cleanyourphone.org/#feedback)

## Status

`v0.2.3` ist eine frühe MVP-Version, nur für Windows 10/11 x64 und **nicht code-signiert**. Sie wurde
Ende-zu-Ende auf einem **OnePlus 6T (Android 11)** getestet: verbinden, prüfen, Backup, Review, ein
Paket deaktivieren, verifizieren, fertig und rückgängig.

Die App rät bewusst nicht. Sie macht nur weiter, wenn sie eine Übereinstimmung findet:

| Smartphone | Was die App macht |
|---|---|
| Exaktes `device`-Profil mit einem in `tested` gelisteten Build | Geführter Ablauf mit der getesteten Paketliste. |
| `documented`-Profil, das zu Modell, Firmware-Familie und Android-Version passt | Zeigt eine Warnung, verlangt eine ausdrückliche Bestätigung und wendet **ein Paket pro Batch** an. |
| Gleiches Modell, aber anderer Build oder OTA | Stoppt und verlinkt auf die Skill. |
| Kein Profil, verwaltetes Smartphone, mehrere Benutzer, Android < 8 oder TV | Stoppt und verlinkt auf die Skill oder die Sicherheitsdokumentation. |

Ein `documented`-Profil stammt aus einem Firmware-Dump. Es ist ein Beleg, kein Test auf einem echten
Gerät; Pakete können je nach Region, Mobilfunkanbieter oder Update abweichen.

<p align="center">
  <img src="docs/images/app-review.png" alt="Review-Bildschirm der CleanYourPhone-App mit Warnung zu einem documented-Profil, einer ausgewählten App und dem Backup-Pfad, der das Rückgängigmachen ermöglicht" width="760">
</p>

## Was sie macht

- **WLAN oder USB.** Koppel ein Android-11+-Gerät über Drahtloses Debugging oder nutze ein
  Datenkabel. Die App findet das Smartphone, prüft den Build und nutzt während der Sitzung einen
  einzigen Transport.
- **Exakte Profilprüfung.** Zeigt Modell, Android-Version, Build, Akku, Profil und ob der Build
  automatisch anwendbar ist.
- **Pflicht-Backup.** Paketliste, Rollen, Einstellungen und `getprop` vor der ersten Änderung.
- **Jedes Paket prüfen.** `DISABLE`, `ASK`, `BLOCKED` und `SKIP`, mit dem Grund für den Eintrag und
  dem, was kaputtgehen kann. Nichts wird ohne geprüfte Auswahl deaktiviert.
- **Batches und Verifikation.** Fünf Pakete pro Batch für ein `device`-Profil; eines pro Batch für
  ein `documented`-Profil, mit einer Smartphone-Prüfung nach jedem Paket.
- **Das gesamte Journal rückgängig machen.** Eine Aktion stellt jede Änderung wieder her, die die App
  für dieses Smartphone protokolliert hat, auch ältere Sitzungen. Das Backup ist der Fallback.
- **Optionales Private DNS.** Presets für AdGuard, AdGuard Family, Control D und Mullvad, plus eine
  Prüfung, die nicht behauptet, YouTube-Werbung sei blockiert. Siehe
  [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md).
- **Optionaler Vorher-nachher-Benchmark.** Freier RAM, Prozesse und Paketanzahl, alles lokal.
  Approximativ, nicht kausal; weder Seriennummer noch Fingerprint werden gespeichert.
- **Optionales Feedback.** Eine vorausgefüllte, bearbeitbare Checkliste kann nach ausdrücklicher
  Zustimmung an den Maintainer gesendet werden. Keine automatische Telemetrie. Siehe
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md).
- **Update-Prüfung.** Höchstens alle sechs Stunden fragt die App bei GitHub nach der neuesten
  Version. Gibt es eine neuere Version, bietet ein Banner **Jetzt aktualisieren** an: Die App
  lädt den Installer herunter, prüft seine SHA-256, schließt sich, installiert und startet neu.
  Sie installiert nie unbemerkt; deine Einstellungen und Backups bleiben erhalten. Der Installer
  ist nicht signiert, daher kann Windows dich bitten, den Herausgeber zu bestätigen.

<p align="center">
  <img src="docs/images/app-connect.png" alt="Verbindungsbildschirm der CleanYourPhone-App mit Anweisungen für WLAN und USB und dem Link zur Verbindungsanleitung" width="760">
</p>

## Installieren

Lade `CleanYourPhone-Setup-0.2.3.exe` von
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) herunter oder baue
die App lokal.

SHA-256 des veröffentlichten Installers von `v0.2.3`:

```text
2830F4AC481465B719AD29AC4C8C11ECCC2789AE2F953297220EB27807C1BAB9
```

Der Installer arbeitet pro Benutzer, legt eine Verknüpfung im Startmenü an und benötigt keine
Administratorrechte. Er installiert nach `%LOCALAPPDATA%\Programs\CleanYourPhone`.

Windows SmartScreen zeigt möglicherweise **„Windows hat den PC geschützt“**, weil der Build nicht
signiert ist. Wähle **Weitere Informationen → Trotzdem ausführen** erst, nachdem du den Download und
die SHA-256 geprüft hast. Deaktiviere SmartScreen nicht.

Wenn du ADB zum ersten Mal nutzt, folge der
[Verbindungsanleitung](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md). Sie
behandelt den versteckten Bildschirm für Drahtloses Debugging, den Kopplungsport gegenüber dem
Verbindungsport, USB-Datenkabel, Windows-Treiber und die Einstellung für die Desktop-Website im
Browser.

Deinstallieren entfernt die App-Dateien und Verknüpfungen. Es lässt absichtlich das Undo-Journal und
die Smartphone-Backups in `%USERPROFILE%\.cleanyourphone` und die Einstellungen in
`%LOCALAPPDATA%\CleanYourPhone` liegen.

ADB ist nicht gebündelt oder weiterverteilt. Die App findet eine vorhandene Platform-Tools-Installation
oder lädt beim ersten Start das offizielle Archiv von Google herunter. Siehe
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Sicherheitsmodell

Die App ist eine GUI auf Basis derselben CLI; die Leitplanken verschieben sich nicht:

- **Deaktivieren, nie deinstallieren.** Nur `pm disable-user --user 0`; `pm enable` ist der Rückweg.
- **Kein Root, keine Custom-ROM, kein Bootloader-Unlock, kein Shizuku.**
- **Kein Backup, keine Änderungen.** Die Schaltfläche zum Anwenden bleibt ohne verifiziertes Backup
  deaktiviert.
- **Geschützte Pakete und Rollen werden abgelehnt.** Telefonie, Play Services, WebView, Permission
  Controller, Notfallwarnungen, der aktuelle Dialer, SMS, Home und Tastatur können nicht deaktiviert
  werden.
- **Ein Transport pro Sitzung.** Der Wechsel zwischen WLAN/USB mitten in der Sitzung wird abgelehnt;
  starte eine neue Sitzung.
- **Stopp bei Unbekanntem.** Verwaltete Geräte, mehrere Benutzer, Android < 8, TVs und Smartphones
  ohne passendes Profil werden nicht verändert.
- **Keine automatische Telemetrie.** Die App ist lokal. Ihre einzigen Netzwerkaufrufe sind der
  optionale Download der Google Platform-Tools, die GitHub-Update-Prüfung samt Installer-Download
  und das Feedback-Formular, nachdem die Person auf Senden gedrückt hat.

## Build

Voraussetzungen: Windows 10/11 x64, Python 3.12+, Git und Inno Setup 6
(`choco install innosetup -y` oder <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

Das Skript:

1. klont den gepinnten CLI-Tag (`v0.3.4`);
2. friert die CLI als Onedir-Sidecar ein;
3. stellt die 157 Profile bereit;
4. friert die PySide6-App ein;
5. macht einen Smoke-Test beider Executables;
6. kompiliert den Installer pro Benutzer.

Ausgaben:

- `dist/CleanYourPhone/CleanYourPhone.exe` (portable Onedir-App)
- `dist/CleanYourPhone-Setup-0.2.3.exe` (Installer)

Setze `CLEANYOURPHONE_CLI` auf das eingefrorene Sidecar und führe
`python -m pytest tests/test_cli_contract.py` aus, um den Vertragstest mit dem echten Sidecar
einzubeziehen.

## Entwicklung

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

Die App-Suite deckt die Verbindungs-Guards, das Pinning der Seriennummer, die Bestätigung von
`documented`-Profilen, das Anwenden eines Pakets pro Batch, die Backup-Sperre, das
Rückgängigmachen, Feedback-Payloads, die Feedback-Zustimmung und die UI-Texte ab. Das veröffentlichte
Ergebnis der `0.2.3`-Suite ist **533 bestanden, 6 übersprungen**.

## Repository-Übersicht

| Pfad | Was es ist |
|---|---|
| `src/cleanyourphone_app/domain/` | Reine Regeln: Support-Entscheidung, Review-Modell, Sitzung, Batches, Feedback-Payload. |
| `src/cleanyourphone_app/services/` | ADB-Locator, WLAN-Kopplung, CLI-Client, Downloads, Feedback-HTTP-Client, Logging, Einstellungen. |
| `src/cleanyourphone_app/ui/pages/` | Verbinden, Prüfen, Backup, Review, Anwenden, Fertig, Setup, Willkommen, Blockiert. |
| `src/cleanyourphone_app/ui/dialogs/` | Optionaler Feedback-Dialog. |
| `scripts/build-cli-sidecar.ps1` | Baut das gepinnte CLI-Sidecar und stellt die Profile bereit. |
| `scripts/build-app.ps1` | Baut die App, macht einen Smoke-Test und kompiliert den Installer. |
| `packaging/installer.iss` | Inno-Setup-Installer pro Benutzer. |
| `docs/superpowers/` | Historisches Design und Implementierungsplan. |
| `tests/` | Pytest-Suite; 533 bestanden, 6 übersprungen bei `0.2.3`. |

## Einschränkungen

- Nur Windows 10/11 x64. Es gibt noch keine Desktop-App für macOS oder Linux.
- Der Build ist nicht code-signiert.
- Sie unterstützt nur die oben genannten exakten Profile und Builds; jedes andere Smartphone wird an
  die Skill verwiesen.
- Der `documented`-Modus ist von der App-Suite abgedeckt, aber noch nicht durch ein physisches Gerät
  mit `documented`-Profil.
- ADB benötigt weiterhin Entwickleroptionen und einen autorisierten Computer.

## Links

- **Skill und CLI:** <https://github.com/jparedesDS/cleanyourphone>
- **Website:** <https://cleanyourphone.org/>
- **Verbindungsanleitung:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **Feedback und Privatsphäre:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **Profile:** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **Sicherheit:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## Lizenz

MIT. Siehe [LICENSE](LICENSE). Hinweise zu Drittanbietern stehen in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
