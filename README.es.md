<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — tu móvil, sin lo que sobra" width="100%">
  </a>
</p>

<p align="center">
  <b>App opcional para Windows</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill y CLI</a> ·
  <a href="https://cleanyourphone.org/">Web</a> ·
  <a href="https://cleanyourphone.org/#feedback">Feedback</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <b>Español</b> ·
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
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="Sin telemetría">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="Probada en OnePlus 6T">
</p>

# App de CleanYourPhone

**La app opcional para Windows de la skill CleanYourPhone.** Un flujo de debloat local y reversible
para quien prefiere botones a prompts: conectar, comprobar, hacer backup, revisar cada paquete,
aplicar por lotes, verificar y deshacer. La skill sigue siendo el producto principal; esta app es el
camino sencillo para los móviles que puede verificar.

[Descarga la Early MVP](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[Skill y CLI](https://github.com/jparedesDS/cleanyourphone) ·
[Guía de conexión](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[Feedback](https://cleanyourphone.org/#feedback)

## Estado

`v0.2.3` es una Early MVP, solo para Windows 10/11 x64 y **sin firma de código**. Se probó de
principio a fin en un **OnePlus 6T (Android 11)**: conectar, comprobar, backup, revisar, desactivar un
paquete, verificar, terminar y deshacer.

La app se niega a adivinar por diseño. Solo continúa cuando puede emparejar:

| Móvil | Qué hace la app |
|---|---|
| Perfil `device` exacto con una build incluida en `tested` | Flujo guiado con la lista de paquetes probada. |
| Perfil `documented` que coincide en modelo, familia de firmware y versión de Android | Muestra un aviso, exige una confirmación explícita y aplica **un paquete por lote**. |
| Mismo modelo pero otra build u OTA | Se para y enlaza a la skill. |
| Sin perfil, móvil gestionado, varios usuarios, Android < 8 o TV | Se para y enlaza a la skill o a la documentación de seguridad. |

Un perfil `documented` procede de un dump de firmware. Es evidencia, no una prueba en un móvil real;
los paquetes pueden cambiar según región, operadora o actualización.

<p align="center">
  <img src="docs/images/app-review.png" alt="Pantalla de revisión de la app CleanYourPhone con aviso de perfil documentado, una app seleccionada y la ruta de backup lista para deshacer" width="760">
</p>

## Qué hace

- **Wi-Fi o USB.** Empareja con Depuración inalámbrica en Android 11 o posterior, o usa un cable de
  datos. La app encuentra el móvil, comprueba la build y mantiene un solo transporte para la sesión.
- **Comprobación exacta del perfil.** Enseña modelo, versión de Android, build, batería, perfil y si
  la build se puede aplicar automáticamente.
- **Backup obligatorio.** Lista de paquetes, roles, ajustes y `getprop` antes del primer cambio.
- **Revisa cada paquete.** `DISABLE`, `ASK`, `BLOCKED` y `SKIP`, con el motivo por el que está en la
  lista y qué se puede romper. Nada se desactiva sin una selección revisada.
- **Lotes y verificación.** Cinco paquetes por lote para un perfil `device`; uno por lote para un
  perfil `documented`, con una comprobación del móvil después de cada uno.
- **Deshaz todo el journal.** Una sola acción restaura cada cambio que la app registró para ese móvil,
  incluidas las sesiones anteriores. El backup es el plan B.
- **DNS privado opcional.** Presets de AdGuard, AdGuard Family, Control D y Mullvad, además de una
  comprobación que no promete que los anuncios de YouTube estén bloqueados. Ver
  [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md).
- **Benchmark opcional antes/después.** RAM libre, procesos y número de paquetes, todo local.
  Aproximado, no causal; no se guarda ningún serial ni fingerprint.
- **Feedback opcional.** Un checklist relleno y editable que se puede enviar al maintainer después de
  un consentimiento explícito. Sin telemetría automática. Ver
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md).
- **Comprobación de actualizaciones.** Como máximo una vez cada seis horas, la app pregunta a GitHub
  por la última release. Si hay una versión nueva, un aviso ofrece **Actualizar ahora**: la app
  descarga el instalador, verifica su SHA-256, se cierra, lo instala y se reinicia. Nunca instala en
  silencio; tus ajustes y copias se conservan. El instalador no está firmado, así que Windows puede
  pedirte que confirmes el editor.

<p align="center">
  <img src="docs/images/app-connect.png" alt="Pantalla de conexión de CleanYourPhone con instrucciones para Wi-Fi y USB y el enlace a la guía de conexión" width="760">
</p>

## Instalar

Descarga `CleanYourPhone-Setup-0.2.3.exe` desde
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) o compílalo en
local.

SHA-256 del instalador publicado de `v0.2.3`:

```text
2830F4AC481465B719AD29AC4C8C11ECCC2789AE2F953297220EB27807C1BAB9
```

El instalador es por usuario, crea un acceso directo en el menú Inicio y no necesita permisos de
administrador. Se instala en `%LOCALAPPDATA%\Programs\CleanYourPhone`.

Windows SmartScreen puede mostrar **"Windows protegió tu PC"** porque la build no está firmada. Elige
**Más información → Ejecutar de todas formas** solo después de verificar la descarga y el SHA-256. No
desactives SmartScreen.

Si es la primera vez que usas ADB, sigue la
[guía de conexión](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md). Cubre la
pantalla oculta de Depuración inalámbrica, el puerto de emparejamiento frente al puerto de conexión,
los cables USB de datos, los drivers de Windows y el ajuste de sitio de escritorio del navegador.

Desinstalar borra los archivos y los accesos directos de la app. Deja a propósito el journal de
deshacer y los backups del móvil en `%USERPROFILE%\.cleanyourphone`, y los ajustes en
`%LOCALAPPDATA%\CleanYourPhone`.

ADB no está incluido ni redistribuido. La app busca una instalación de Platform-Tools existente o
descarga el archivo oficial de Google en el primer arranque. Ver
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Modelo de seguridad

La app es una GUI sobre la misma CLI; las protecciones no se mueven:

- **Desactivar, nunca desinstalar.** Solo `pm disable-user --user 0`; `pm enable` es la vuelta atrás.
- **Sin root, sin ROM cocinada, sin desbloquear el bootloader, sin Shizuku.**
- **Sin backup no hay cambios.** El botón de aplicar sigue desactivado sin un backup verificado.
- **Paquetes y roles protegidos se rechazan.** Telefonía, Play Services, WebView, permission
  controller, alertas de emergencia, el dialer actual, SMS, Home y el teclado no se pueden desactivar.
- **Un transporte por sesión.** Cambiar de Wi-Fi a USB a mitad de sesión se rechaza; empieza una
  sesión nueva.
- **Para ante lo desconocido.** Móviles gestionados, varios usuarios, Android < 8, TVs y móviles sin
  un perfil que coincida no se tocan.
- **Sin telemetría automática.** La app es local. Sus únicas llamadas de red son la descarga opcional
  de Platform-Tools de Google, la comprobación de actualizaciones y descarga del instalador desde
  GitHub, y el formulario de feedback después de que la persona pulse Enviar.

## Compilar

Requisitos: Windows 10/11 x64, Python 3.12+, Git e Inno Setup 6
(`choco install innosetup -y` o <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

El script:

1. clona el tag fijado de la CLI (`v0.3.4`);
2. congela la CLI como sidecar onedir;
3. prepara los 157 perfiles;
4. congela la app de PySide6;
5. hace un smoke test de los dos ejecutables;
6. compila el instalador por usuario.

Salidas:

- `dist/CleanYourPhone/CleanYourPhone.exe` (app portable onedir)
- `dist/CleanYourPhone-Setup-0.2.3.exe` (instalador)

Define `CLEANYOURPHONE_CLI` con el sidecar congelado y ejecuta
`python -m pytest tests/test_cli_contract.py` para incluir el test de contrato con el sidecar real.

## Desarrollo

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

La suite de la app cubre las protecciones de conexión, la fijación del serial, la confirmación del
perfil documentado, la aplicación de uno por lote, el bloqueo sin backup, la vuelta atrás, los
payloads de feedback, el consentimiento del feedback y los textos de la UI. El resultado publicado de
la suite `0.2.3` es **533 superados, 6 omitidos**.

## Mapa del repositorio

| Ruta | Qué es |
|---|---|
| `src/cleanyourphone_app/domain/` | Reglas puras: decisión de soporte, modelo de revisión, sesión, lotes, payload de feedback. |
| `src/cleanyourphone_app/services/` | Localizador de ADB, emparejamiento Wi-Fi, cliente de la CLI, descargas, cliente HTTP de feedback, logging, ajustes. |
| `src/cleanyourphone_app/ui/pages/` | Conectar, comprobar, backup, revisar, aplicar, terminar, setup, bienvenida, bloqueado. |
| `src/cleanyourphone_app/ui/dialogs/` | Diálogo opcional de feedback. |
| `scripts/build-cli-sidecar.ps1` | Compila el sidecar de la CLI fijado y prepara los perfiles. |
| `scripts/build-app.ps1` | Compila la app, le hace un smoke test y compila el instalador. |
| `packaging/installer.iss` | Instalador de Inno Setup por usuario. |
| `docs/superpowers/` | Diseño histórico y plan de implementación. |
| `tests/` | Suite de pytest; 533 superados, 6 omitidos en `0.2.3`. |

## Limitaciones

- Solo Windows 10/11 x64. Todavía no hay app de escritorio para macOS ni Linux.
- La build no está firmada.
- Solo admite los perfiles y builds exactos de arriba; cualquier otro móvil se manda a la skill.
- El modo `documented` está cubierto por la suite de la app, todavía no por un móvil documentado
  físico.
- ADB sigue necesitando Opciones de desarrollador y un ordenador autorizado.

## Enlaces

- **Skill y CLI:** <https://github.com/jparedesDS/cleanyourphone>
- **Web:** <https://cleanyourphone.org/>
- **Guía de conexión:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **Feedback y privacidad:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **Perfiles:** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **Seguridad:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## Licencia

MIT. Ver [LICENSE](LICENSE). Los avisos de terceros están en
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
