<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — il tuo telefono, senza il superfluo" width="100%">
  </a>
</p>

<p align="center">
  <b>App opzionale per Windows</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill e CLI</a> ·
  <a href="https://cleanyourphone.org/">Sito web</a> ·
  <a href="https://cleanyourphone.org/#feedback">Feedback</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <b>Italiano</b> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/jparedesDS/cleanyourphone-app/releases"><img src="https://img.shields.io/github/v/release/jparedesDS/cleanyourphone-app?color=a78bfa&labelColor=121316" alt="release"></a>
  <img src="https://img.shields.io/badge/Windows-10%2F11%20x64-a78bfa?labelColor=121316" alt="Windows 10/11 x64">
  <img src="https://img.shields.io/badge/license-MIT-a78bfa?labelColor=121316" alt="MIT">
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="Nessuna telemetria">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="Testata su OnePlus 6T">
</p>

# App di CleanYourPhone

**L'app opzionale per Windows della skill CleanYourPhone.** Un flusso di debloat locale e reversibile
per chi preferisce i pulsanti ai prompt: connetti, controlla, esegui il backup, rivedi ogni pacchetto,
applica a lotti, verifica e annulla. La skill resta il prodotto principale; questa app è il percorso
semplice per i telefoni che riesce a verificare.

[Scarica la Early MVP](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[Skill e CLI](https://github.com/jparedesDS/cleanyourphone) ·
[Guida alla connessione](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[Feedback](https://cleanyourphone.org/#feedback)

## Stato

`v0.2.2` è una Early MVP, solo per Windows 10/11 x64 e **non firmata**. È stata testata da capo a
fondo su un **OnePlus 6T (Android 11)**: connessione, controllo, backup, revisione, disattivazione di
un pacchetto, verifica, completamento e annullamento.

L'app si rifiuta di indovinare, per scelta. Continua solo quando riesce a trovare una corrispondenza:

| Telefono | Cosa fa l'app |
|---|---|
| Profilo `device` esatto con una build elencata in `tested` | Flusso guidato con la lista di pacchetti testata. |
| Profilo `documented` che corrisponde a modello, famiglia di firmware e versione di Android | Mostra un avviso, richiede una conferma esplicita e applica **un pacchetto per lotto**. |
| Stesso modello ma build o OTA diversi | Si ferma e rimanda alla skill. |
| Nessun profilo, telefono gestito, utenti multipli, Android < 8 o TV | Si ferma e rimanda alla skill o ai documenti di sicurezza. |

Un profilo `documented` deriva da un dump del firmware. È una prova documentale, non un test su un
dispositivo reale; i pacchetti possono variare per regione, operatore o aggiornamento.

<p align="center">
  <img src="docs/images/app-review.png" alt="Schermata di revisione dell'app CleanYourPhone con avviso di profilo documented, un'app selezionata e il percorso del backup pronto per l'annullamento" width="760">
</p>

## Cosa fa

- **Wi-Fi o USB.** Associa il telefono con Android 11+ tramite Debug wireless, oppure usa un cavo
  dati. L'app trova il telefono, controlla la build e mantiene un solo trasporto per la sessione.
- **Controllo esatto del profilo.** Mostra modello, versione di Android, build, batteria, profilo e se
  la build è applicabile automaticamente.
- **Backup obbligatorio.** Elenco dei pacchetti, ruoli, impostazioni e `getprop` prima della prima
  modifica.
- **Rivedi ogni pacchetto.** `DISABLE`, `ASK`, `BLOCKED` e `SKIP`, con il motivo dell'inserimento e
  cosa può rompersi. Nulla viene disattivato senza una selezione rivista.
- **Lotti e verifica.** Cinque pacchetti per lotto per un profilo `device`; uno per lotto per un
  profilo `documented`, con un controllo del telefono dopo ciascuno.
- **Annulla l'intero journal.** Una sola azione ripristina ogni modifica registrata dall'app per quel
  telefono, comprese le sessioni precedenti. Il backup è il piano B.
- **DNS privato opzionale.** Preset AdGuard, AdGuard Family, Control D e Mullvad, più un controllo che
  non pretende che gli annunci di YouTube siano bloccati. Vedi
  [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md).
- **Benchmark prima/dopo opzionale.** RAM libera, processi e numero di pacchetti, tutto locale.
  Approssimativo, non causale; non viene salvato alcun numero di serie o fingerprint.
- **Feedback opzionale.** Una checklist precompilata e modificabile può essere inviata al maintainer
  dopo consenso esplicito. Nessuna telemetria automatica. Vedi
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md).
- **Controllo degli aggiornamenti.** Al massimo una volta ogni sei ore l'app chiede a GitHub l'ultima
  release. Se esiste una versione più recente, un banner apre la pagina della release. L'app non
  scarica né installa mai un aggiornamento da sola e non invia dati di account, telefono o utilizzo.

<p align="center">
  <img src="docs/images/app-connect.png" alt="Schermata di connessione di CleanYourPhone con istruzioni per Wi-Fi e USB e il link alla guida alla connessione" width="760">
</p>

## Installazione

Scarica `CleanYourPhone-Setup-0.2.2.exe` da
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest), oppure compila
l'app in locale.

SHA-256 dell'installer pubblicato di `v0.2.2`:

```text
E827AB24CB02E7C18F7577E6C00E263C1CCEC6683E7812E8F22222FC3AF216E3
```

L'installer è per utente, crea un collegamento nel menu Start e non richiede privilegi di
amministratore. Si installa in `%LOCALAPPDATA%\Programs\CleanYourPhone`.

Windows SmartScreen potrebbe mostrare **"Windows ha protetto il PC"** perché la build non è firmata.
Scegli **Ulteriori informazioni → Esegui comunque** solo dopo aver verificato il download e lo
SHA-256. Non disattivare SmartScreen.

Se è la prima volta che usi ADB, segui la
[guida alla connessione](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md).
Copre la schermata nascosta del Debug wireless, la porta di associazione rispetto a quella di
connessione, i cavi USB dati, i driver di Windows e l'impostazione del sito desktop nel browser.

La disinstallazione rimuove i file e i collegamenti dell'app. Lascia intenzionalmente il journal di
annullamento e i backup del telefono in `%USERPROFILE%\.cleanyourphone`, e le impostazioni in
`%LOCALAPPDATA%\CleanYourPhone`.

ADB non è incluso né ridistribuito. L'app trova un'installazione esistente di Platform-Tools oppure
scarica l'archivio ufficiale da Google al primo avvio. Vedi
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Modello di sicurezza

L'app è una GUI sopra la stessa CLI; le protezioni restano le stesse:

- **Disattivare, mai disinstallare.** Solo `pm disable-user --user 0`; `pm enable` è l'annullamento.
- **Niente root, niente ROM personalizzate, niente sblocco del bootloader, niente Shizuku.**
- **Nessun backup, nessuna modifica.** Il pulsante Applica resta disabilitato senza un backup
  verificato.
- **Pacchetti e ruoli protetti vengono rifiutati.** Telefonia, Play Services, WebView, permission
  controller, avvisi di emergenza, il dialer corrente, SMS, Home e la tastiera non possono essere
  disattivati.
- **Un solo trasporto per sessione.** Passare da Wi-Fi a USB a metà sessione viene rifiutato; inizia
  una nuova sessione.
- **Fermati su ciò che non conosci.** Dispositivi gestiti, utenti multipli, Android < 8, TV e telefoni
  senza un profilo corrispondente non vengono modificati.
- **Nessuna telemetria automatica.** L'app è locale. Le sue uniche chiamate di rete sono il download
  opzionale di Platform-Tools da Google, il controllo degli aggiornamenti su GitHub e il modulo di
  feedback dopo che la persona preme Invia.

## Compilazione

Requisiti: Windows 10/11 x64, Python 3.12+, Git e Inno Setup 6
(`choco install innosetup -y` o <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

Lo script:

1. clona il tag fissato della CLI (`v0.3.4`);
2. congela la CLI come sidecar onedir;
3. prepara i 157 profili;
4. congela l'app PySide6;
5. esegue uno smoke test di entrambi gli eseguibili;
6. compila l'installer per utente.

Risultati:

- `dist/CleanYourPhone/CleanYourPhone.exe` (app portabile onedir)
- `dist/CleanYourPhone-Setup-0.2.2.exe` (installer)

Imposta `CLEANYOURPHONE_CLI` sul sidecar congelato ed esegui
`python -m pytest tests/test_cli_contract.py` per includere il test di contratto con il sidecar reale.

## Sviluppo

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

La suite dell'app copre le protezioni della connessione, il pinning del seriale, la conferma del
profilo `documented`, l'applicazione uno per lotto, il blocco senza backup, l'annullamento, i payload
di feedback, il consenso al feedback e i testi dell'interfaccia. Il risultato pubblicato della suite
`0.2.2` è **520 superati, 1 saltato**.

## Mappa del repository

| Percorso | Cos'è |
|---|---|
| `src/cleanyourphone_app/domain/` | Regole pure: decisione di supporto, modello di revisione, sessione, lotti, payload di feedback. |
| `src/cleanyourphone_app/services/` | Localizzatore ADB, associazione Wi-Fi, client CLI, download, client HTTP di feedback, logging, impostazioni. |
| `src/cleanyourphone_app/ui/pages/` | Connetti, controlla, backup, rivedi, applica, completato, setup, benvenuto, bloccato. |
| `src/cleanyourphone_app/ui/dialogs/` | Dialogo di feedback opzionale. |
| `scripts/build-cli-sidecar.ps1` | Compila il sidecar CLI fissato e prepara i profili. |
| `scripts/build-app.ps1` | Compila l'app, le fa uno smoke test e compila l'installer. |
| `packaging/installer.iss` | Installer Inno Setup per utente. |
| `docs/superpowers/` | Design storico e piano di implementazione. |
| `tests/` | Suite pytest; 520 superati, 1 saltato su `0.2.2`. |

## Limitazioni

- Solo Windows 10/11 x64. Non esiste ancora un'app desktop per macOS o Linux.
- La build non è firmata.
- Supporta solo i profili e le build esatti indicati sopra; ogni altro telefono viene rimandato alla
  skill.
- La modalità `documented` è coperta dalla suite dell'app, non ancora da un dispositivo fisico con
  profilo `documented`.
- ADB richiede comunque le Opzioni sviluppatore e un computer autorizzato.

## Link

- **Skill e CLI:** <https://github.com/jparedesDS/cleanyourphone>
- **Sito web:** <https://cleanyourphone.org/>
- **Guida alla connessione:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **Feedback e privacy:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **Profili:** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **Sicurezza:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## Licenza

MIT. Vedi [LICENSE](LICENSE). Le note di terze parti sono in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
