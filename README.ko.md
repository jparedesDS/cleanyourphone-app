<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — 불필요한 것을 뺀, 당신의 폰" width="100%">
  </a>
</p>

<p align="center">
  <b>선택 사항인 Windows 앱</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">스킬과 CLI</a> ·
  <a href="https://cleanyourphone.org/">웹사이트</a> ·
  <a href="https://cleanyourphone.org/#feedback">피드백</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <b>한국어</b>
</p>

<p align="center">
  <a href="https://github.com/jparedesDS/cleanyourphone-app/releases"><img src="https://img.shields.io/github/v/release/jparedesDS/cleanyourphone-app?color=a78bfa&labelColor=121316" alt="릴리스"></a>
  <img src="https://img.shields.io/badge/Windows-10%2F11%20x64-a78bfa?labelColor=121316" alt="Windows 10/11 x64">
  <img src="https://img.shields.io/badge/license-MIT-a78bfa?labelColor=121316" alt="MIT">
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="텔레메트리 없음">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="OnePlus 6T에서 테스트됨">
</p>

# CleanYourPhone 앱

**CleanYourPhone 스킬을 위한 선택 사항인 Windows 앱입니다.** 프롬프트보다 버튼이 편한 사람을
위한 로컬·되돌릴 수 있는 디블로트 흐름입니다. 연결, 확인, 백업, 모든 패키지 검토, 배치 적용,
검증, 되돌리기까지. 스킬은 여전히 주요 제품이며, 이 앱은 앱이 검증할 수 있는 폰을 위한 간단한
경로입니다.

[Early MVP 다운로드](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[스킬과 CLI](https://github.com/jparedesDS/cleanyourphone) ·
[연결 가이드](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[피드백](https://cleanyourphone.org/#feedback)

## 상태

`v0.2.2`은 Early MVP이며 Windows 10/11 x64 전용이고 **코드 서명이 없습니다**.
**OnePlus 6T(Android 11)**에서 처음부터 끝까지 테스트했습니다: 연결, 확인, 백업, 검토, 패키지
하나 비활성화, 검증, 완료, 되돌리기.

앱은 의도적으로 추측을 거부합니다. 다음에 맞을 때만 계속합니다:

| 폰 | 앱이 하는 일 |
|---|---|
| `tested`에 나열된 빌드의 정확한 `device` 프로필 | 테스트된 패키지 목록으로 안내형 흐름을 진행합니다. |
| 모델, 펌웨어 제품군, Android 버전이 일치하는 `documented` 프로필 | 경고를 표시하고 명시적 확인을 요구하며 **배치당 패키지 하나**만 적용합니다. |
| 같은 모델이지만 다른 빌드 또는 OTA | 멈추고 스킬로 연결합니다. |
| 프로필 없음, 관리되는 폰, 여러 사용자, Android < 8 또는 TV | 멈추고 스킬 또는 안전 문서로 연결합니다. |

`documented` 프로필은 펌웨어 덤프에서 나옵니다. 실제 기기 테스트가 아니라 증거이며, 패키지는
지역, 통신사, 업데이트에 따라 달라질 수 있습니다.

<p align="center">
  <img src="docs/images/app-review.png" alt="documented 프로필 경고, 선택된 앱 하나, 되돌리기 준비된 백업 경로가 보이는 CleanYourPhone 앱 검토 화면" width="760">
</p>

## 하는 일

- **Wi-Fi 또는 USB.** Android 11 이상에서는 무선 디버깅으로 페어링하거나 데이터 케이블을 사용하세요.
  앱이 폰을 찾고 빌드를 확인하며 세션 동안 하나의 전송 방식을 유지합니다.
- **정확한 프로필 확인.** 모델, Android 버전, 빌드, 배터리, 프로필, 빌드 자동 적용 가능 여부를
  보여 줍니다.
- **필수 백업.** 첫 변경 전에 패키지 목록, 역할, 설정, `getprop`을 백업합니다.
- **모든 패키지 검토.** `DISABLE`, `ASK`, `BLOCKED`, `SKIP`과 함께 목록에 오른 이유와 깨질 수
  있는 것을 표시합니다. 검토된 선택 없이는 아무것도 비활성화되지 않습니다.
- **배치와 검증.** `device` 프로필은 배치당 5개 패키지, `documented` 프로필은 배치당 하나이며
  각 패키지 후에 폰 상태를 확인합니다.
- **저널 전체 되돌리기.** 한 번의 작업으로 해당 폰에 대해 앱이 기록한 모든 변경을 복원하며, 이전
  세션도 포함합니다. 백업은 대체 수단입니다.
- **선택형 비공개 DNS.** AdGuard, AdGuard Family, Control D, Mullvad 프리셋과 YouTube 광고가
  차단된다고 주장하지 않는 확인 기능. [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md)를
  참고하세요.
- **선택형 전/후 벤치마크.** 로컬 사용 가능 RAM, 프로세스, 패키지 수. 근사치이며 인과 관계가
  아니고 시리얼이나 fingerprint를 저장하지 않습니다.
- **선택형 피드백.** 미리 채워진 편집 가능한 체크리스트를 명시적 동의 후 메인테이너에게 보낼 수
  있습니다. 자동 텔레메트리는 없습니다.
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md)를
  참고하세요.
- **업데이트 확인.** 앱은 최대 6시간에 한 번 GitHub에서 최신 릴리스를 확인합니다. 새 버전이 있으면
  배너가 릴리스 페이지를 엽니다. 앱은 스스로 업데이트를 다운로드하거나 설치하지 않으며, 계정, 폰,
  사용 데이터를 전송하지 않습니다.

<p align="center">
  <img src="docs/images/app-connect.png" alt="Wi-Fi 및 USB 안내와 연결 가이드 링크가 있는 CleanYourPhone 연결 화면" width="760">
</p>

## 설치

`CleanYourPhone-Setup-0.2.2.exe`를
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest)에서
다운로드하거나 로컬에서 빌드하세요.

공개된 `v0.2.2` 설치 프로그램의 SHA-256:

```text
E827AB24CB02E7C18F7577E6C00E263C1CCEC6683E7812E8F22222FC3AF216E3
```

설치 프로그램은 사용자 단위로 설치하고 시작 메뉴 바로 가기를 만들며 관리자 권한이 필요 없습니다.
`%LOCALAPPDATA%\Programs\CleanYourPhone`에 설치됩니다.

빌드가 서명되지 않아 Windows SmartScreen이 **"Windows에서 PC를 보호했습니다"**를 표시할 수
있습니다. 다운로드와 SHA-256을 확인한 뒤에만 **추가 정보 → 실행**을 선택하세요. SmartScreen을
끄지 마세요.

ADB를 처음 사용한다면 [연결 가이드](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md)를
따르세요. 숨겨진 무선 디버깅 화면, 페어링 포트와 연결 포트의 차이, USB 데이터 케이블, Windows
드라이버, 브라우저의 데스크톱 사이트 설정을 다룹니다.

제거하면 앱 파일과 바로 가기가 삭제됩니다. 되돌리기 저널과 폰 백업은
`%USERPROFILE%\.cleanyourphone`에, 설정은 `%LOCALAPPDATA%\CleanYourPhone`에 의도적으로 남겨
둡니다.

ADB는 포함하거나 재배포하지 않습니다. 앱은 기존 Platform-Tools 설치를 찾거나 첫 실행 시 Google의
공식 아카이브를 다운로드합니다. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 참고하세요.

## 안전 모델

앱은 같은 CLI를 감싼 GUI이며, 안전장치는 그대로입니다:

- **비활성화만, 삭제는 없음.** `pm disable-user --user 0`만 사용하고, 되돌리기는 `pm enable`입니다.
- **root, 커스텀 ROM, 부트로더 잠금 해제, Shizuku가 없습니다.**
- **백업 없이는 변경 없음.** 검증된 백업이 없으면 적용 버튼이 비활성 상태로 유지됩니다.
- **보호 패키지와 역할은 거부됩니다.** 통신, Play Services, WebView, 권한 컨트롤러, 긴급 경보,
  현재 다이얼러, SMS, Home, 키보드는 비활성화할 수 없습니다.
- **세션당 하나의 전송 방식.** 세션 중간에 Wi-Fi/USB를 바꾸는 것은 거부됩니다. 새 세션을
  시작하세요.
- **모르면 멈춤.** 관리되는 기기, 여러 사용자, Android < 8, TV, 일치하는 프로필이 없는 폰은
  변경하지 않습니다.
- **자동 텔레메트리 없음.** 앱은 로컬입니다. 유일한 네트워크 호출은 선택형 Google
  Platform-Tools 다운로드, GitHub 업데이트 확인, 사용자가 전송을 누른 뒤의 피드백 양식입니다.

## 빌드

요구 사항: Windows 10/11 x64, Python 3.12+, Git, Inno Setup 6
(`choco install innosetup -y` 또는 <https://jrsoftware.org/isdl.php>).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

스크립트가 하는 일:

1. 고정된 CLI 태그(`v0.3.4`)를 클론합니다.
2. CLI를 onedir sidecar로 동결합니다.
3. 157개 프로필을 준비합니다.
4. PySide6 앱을 동결합니다.
5. 두 실행 파일을 스모크 테스트합니다.
6. 사용자별 설치 프로그램을 컴파일합니다.

출력물:

- `dist/CleanYourPhone/CleanYourPhone.exe` (포터블 onedir 앱)
- `dist/CleanYourPhone-Setup-0.2.2.exe` (설치 프로그램)

`CLEANYOURPHONE_CLI`를 동결된 sidecar로 설정하고
`python -m pytest tests/test_cli_contract.py`를 실행하면 실제 sidecar 계약 테스트가 포함됩니다.

## 개발

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

앱 테스트 스위트는 연결 가드, 시리얼 고정, `documented` 프로필 확인, 배치당 하나 적용, 백업
게이팅, 되돌리기, 피드백 페이로드, 피드백 동의, UI 문구를 다룹니다. 공개된 `0.2.2` 테스트 결과는
**520개 통과, 1개 건너뜀**입니다.

## 저장소 구조

| 경로 | 설명 |
|---|---|
| `src/cleanyourphone_app/domain/` | 순수 규칙: 지원 결정, 검토 모델, 세션, 배치, 피드백 페이로드. |
| `src/cleanyourphone_app/services/` | ADB 탐색, Wi-Fi 페어링, CLI 클라이언트, 다운로드, 피드백 HTTP 클라이언트, 로깅, 설정. |
| `src/cleanyourphone_app/ui/pages/` | 연결, 확인, 백업, 검토, 적용, 완료, 설정, 환영, 차단. |
| `src/cleanyourphone_app/ui/dialogs/` | 선택형 피드백 대화상자. |
| `scripts/build-cli-sidecar.ps1` | 고정된 CLI sidecar를 빌드하고 프로필을 준비합니다. |
| `scripts/build-app.ps1` | 앱을 빌드하고 스모크 테스트한 뒤 설치 프로그램을 컴파일합니다. |
| `packaging/installer.iss` | 사용자별 Inno Setup 설치 프로그램. |
| `docs/superpowers/` | 과거 설계 및 구현 계획. |
| `tests/` | Pytest 스위트. `0.2.2`에서 520개 통과, 1개 건너뜀. |

## 제한 사항

- Windows 10/11 x64 전용입니다. 아직 macOS나 Linux 데스크톱 앱은 없습니다.
- 빌드가 코드 서명되지 않았습니다.
- 위에 나온 정확한 프로필과 빌드만 지원하며, 그 외 모든 폰은 스킬로 안내합니다.
- `documented` 모드는 앱 테스트 스위트로 검증되었지만, 아직 실제 기기에서 이 모드로 검증되지는
  않았습니다.
- ADB는 여전히 개발자 옵션과 승인된 컴퓨터가 필요합니다.

## 링크

- **스킬과 CLI:** <https://github.com/jparedesDS/cleanyourphone>
- **웹사이트:** <https://cleanyourphone.org/>
- **연결 가이드:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **피드백과 개인정보:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **프로필:** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **안전:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## 라이선스

MIT. [LICENSE](LICENSE)를 참고하세요. 서드파티 고지는
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 있습니다.
