<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — votre téléphone, sans le superflu" width="100%">
  </a>
</p>

<p align="center">
  <b>App Windows facultative</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill et CLI</a> ·
  <a href="https://cleanyourphone.org/">Site</a> ·
  <a href="https://cleanyourphone.org/#feedback">Feedback</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <b>Français</b> ·
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
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="Sans télémétrie">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="Testé sur OnePlus 6T">
</p>

# App de CleanYourPhone

**L’app Windows facultative pour la skill CleanYourPhone.** Un parcours de débloatage local et
réversible pour ceux qui préfèrent les boutons aux prompts : connecter, vérifier, sauvegarder, relire
chaque paquet, appliquer par lots, vérifier et annuler. La skill reste le produit principal ; cette
app est le chemin simple pour les téléphones qu’elle peut vérifier.

[Télécharger l’Early MVP](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[Skill et CLI](https://github.com/jparedesDS/cleanyourphone) ·
[Guide de connexion](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[Feedback](https://cleanyourphone.org/#feedback)

## État

`v0.2.2` est un Early MVP, Windows 10/11 x64 uniquement, et **non signé**. La version a été testée de
bout en bout sur un **OnePlus 6T (Android 11)** : connexion, vérification, sauvegarde, relecture,
désactivation d’un paquet, vérification, fin et annulation.

L’app refuse délibérément de deviner. Elle ne continue que si elle peut correspondre :

| Téléphone | Ce que fait l’app |
|---|---|
| Profil `device` exact avec une build listée dans `tested` | Parcours guidé avec la liste de paquets testée. |
| Profil `documented` correspondant au modèle, à la famille de firmware et à la version d’Android | Affiche un avertissement, exige une confirmation explicite et applique **un paquet par lot**. |
| Même modèle mais build ou OTA différente | S’arrête et renvoie vers la skill. |
| Aucun profil, téléphone géré, plusieurs utilisateurs, Android < 8 ou TV | S’arrête et renvoie vers la skill ou la doc de sécurité. |

Un profil `documented` vient d’un dump de firmware. C’est une preuve documentaire, pas un test sur
appareil réel ; les paquets peuvent varier selon la région, l’opérateur ou la mise à jour.

<p align="center">
  <img src="docs/images/app-review.png" alt="Écran de relecture de l’app CleanYourPhone avec un avertissement de profil documented, une app sélectionnée et le chemin de sauvegarde prêt pour l’annulation" width="760">
</p>

## Ce qu’elle fait

- **Wi-Fi ou USB.** Associez Android 11+ via le Débogage sans fil, ou utilisez un câble de données.
  L’app trouve le téléphone, vérifie la build et garde un seul transport pour la session.
- **Vérification exacte du profil.** Affiche le modèle, la version d’Android, la build, la batterie,
  le profil et si la build peut être appliquée automatiquement.
- **Sauvegarde obligatoire.** Liste des paquets, rôles, réglages et `getprop` avant le premier
  changement.
- **Relecture de chaque paquet.** `DISABLE`, `ASK`, `BLOCKED` et `SKIP`, avec la raison de sa présence
  et ce qui peut casser. Rien n’est désactivé sans une sélection relue.
- **Lots et vérification.** Cinq paquets par lot pour un profil `device` ; un par lot pour un profil
  `documented`, avec un contrôle du téléphone après chacun.
- **Annulation de tout le journal.** Une action restaure chaque changement enregistré par l’app pour
  ce téléphone, y compris les sessions plus anciennes. La sauvegarde est le recours.
- **DNS privé facultatif.** Préréglages AdGuard, AdGuard Family, Control D et Mullvad, plus une
  vérification qui ne prétend pas bloquer les pubs YouTube. Voir
  [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md).
- **Benchmark avant/après facultatif.** RAM libre, processus et nombre de paquets, en local.
  Approximatif, sans lien de causalité ; aucun numéro de série ni empreinte n’est stocké.
- **Retours facultatifs.** Une liste de vérification préremplie et modifiable peut être envoyée au
  mainteneur après consentement explicite. Aucune télémétrie automatique. Voir
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md).
- **Vérification des mises à jour.** Au plus une fois toutes les six heures, l’app demande à GitHub la
  dernière version publiée. Si une version plus récente existe, une bannière ouvre la page de
  publication. L’app ne télécharge ni n’installe jamais une mise à jour d’elle-même et n’envoie aucune
  donnée de compte, de téléphone ou d’usage.

<p align="center">
  <img src="docs/images/app-connect.png" alt="Écran de connexion de l’app CleanYourPhone avec les instructions Wi-Fi et USB et le lien vers le guide de connexion" width="760">
</p>

## Installation

Téléchargez `CleanYourPhone-Setup-0.2.2.exe` depuis
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest), ou compilez-le
localement.

SHA-256 de l’installateur publié `v0.2.2` :

```text
E827AB24CB02E7C18F7577E6C00E263C1CCEC6683E7812E8F22222FC3AF216E3
```

L’installateur est propre à chaque utilisateur, crée un raccourci dans le menu Démarrer et ne nécessite
pas de droits administrateur. Il s’installe dans `%LOCALAPPDATA%\Programs\CleanYourPhone`.

Windows SmartScreen peut afficher **« Windows a protégé votre PC »** parce que la build n’est pas
signée. Choisissez **Informations complémentaires → Exécuter quand même** uniquement après avoir
vérifié le téléchargement et le SHA-256. Ne désactivez pas SmartScreen.

Si c’est votre première fois avec ADB, suivez le
[guide de connexion](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md). Il
couvre l’écran caché du Débogage sans fil, le port d’association versus le port de connexion, les
câbles USB de données, les pilotes Windows et le réglage « version pour ordinateur » du navigateur.

La désinstallation supprime les fichiers de l’app et les raccourcis. Elle laisse volontairement le
journal d’annulation et les sauvegardes du téléphone dans `%USERPROFILE%\.cleanyourphone`, et les
réglages dans `%LOCALAPPDATA%\CleanYourPhone`.

ADB n’est pas embarqué ni redistribué. L’app trouve une installation Platform-Tools existante ou
télécharge l’archive officielle de Google au premier lancement. Voir
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Modèle de sécurité

L’app est une GUI au-dessus du même CLI ; les garde-fous ne bougent pas :

- **Désactiver, jamais désinstaller.** Uniquement `pm disable-user --user 0` ; `pm enable` est
  l’annulation.
- **Pas de root, pas de ROM personnalisée, pas de déverrouillage du bootloader, pas de Shizuku.**
- **Pas de sauvegarde, pas de changement.** Le bouton Appliquer reste désactivé sans sauvegarde
  vérifiée.
- **Paquets protégés et rôles refusés.** La téléphonie, Play Services, WebView, le permission
  controller, les alertes d’urgence, le dialer, l’app SMS, l’app Home et le clavier actuels ne peuvent
  pas être désactivés.
- **Un seul transport par session.** Changer de Wi-Fi/USB en cours de session est refusé ; démarrez
  une nouvelle session.
- **Arrêt sur l’inconnu.** Les appareils gérés, les utilisateurs multiples, Android < 8, les TV et les
  téléphones sans profil correspondant ne sont pas modifiés.
- **Aucune télémétrie automatique.** L’app est locale. Ses seuls appels réseau sont le téléchargement
  facultatif de Google Platform-Tools, la vérification des mises à jour sur GitHub et le formulaire de
  retour après un clic sur Envoyer.

## Compilation

Prérequis : Windows 10/11 x64, Python 3.12+, Git et Inno Setup 6
(`choco install innosetup -y` ou <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

Le script :

1. clone le tag CLI épinglé (`v0.3.4`) ;
2. fige le CLI en sidecar onedir ;
3. prépare les 157 profils ;
4. fige l’app PySide6 ;
5. fait un smoke test des deux exécutables ;
6. compile l’installateur par utilisateur.

Sorties :

- `dist/CleanYourPhone/CleanYourPhone.exe` (app onedir portable)
- `dist/CleanYourPhone-Setup-0.2.2.exe` (installateur)

Définissez `CLEANYOURPHONE_CLI` sur le sidecar figé et exécutez
`python -m pytest tests/test_cli_contract.py` pour inclure le test de contrat avec le vrai sidecar.

## Développement

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

La suite de l’app couvre les garde-fous de connexion, l’épinglage du numéro de série, la confirmation
des profils `documented`, l’application d’un paquet par lot, le blocage en l’absence de sauvegarde,
l’annulation, les payloads de retour, le consentement au retour et les textes de l’UI. Le résultat
publié pour `0.2.2` est **520 tests réussis, 1 ignoré**.

## Carte du dépôt

| Chemin | Ce que c’est |
|---|---|
| `src/cleanyourphone_app/domain/` | Règles pures : décision de prise en charge, modèle de relecture, session, lots, payload de retour. |
| `src/cleanyourphone_app/services/` | Localisateur ADB, association Wi-Fi, client CLI, téléchargements, client HTTP de retour, journaux, réglages. |
| `src/cleanyourphone_app/ui/pages/` | Connexion, vérification, sauvegarde, relecture, application, fin, configuration, accueil, blocage. |
| `src/cleanyourphone_app/ui/dialogs/` | Boîte de dialogue de retour facultatif. |
| `scripts/build-cli-sidecar.ps1` | Construit le sidecar CLI épinglé et prépare les profils. |
| `scripts/build-app.ps1` | Construit l’app, fait le smoke test et compile l’installateur. |
| `packaging/installer.iss` | Installateur Inno Setup par utilisateur. |
| `docs/superpowers/` | Conception historique et plan d’implémentation. |
| `tests/` | Suite Pytest ; 520 tests réussis, 1 ignoré sur `0.2.2`. |

## Limites

- Windows 10/11 x64 uniquement. Il n’y a pas encore d’app de bureau macOS ou Linux.
- La build n’est pas signée.
- Elle ne prend en charge que les profils et builds exacts ci-dessus ; tout autre téléphone est
  renvoyé vers la skill.
- Le mode `documented` est couvert par la suite de l’app, pas encore par un appareil physique avec un
  profil `documented`.
- ADB exige toujours les Options pour les développeurs et un ordinateur autorisé.

## Liens

- **Skill et CLI :** <https://github.com/jparedesDS/cleanyourphone>
- **Site :** <https://cleanyourphone.org/>
- **Guide de connexion :** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **Retours et confidentialité :** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **Profils :** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **Sécurité :** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## Licence

MIT. Voir [LICENSE](LICENSE). Les mentions tierces sont dans
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
