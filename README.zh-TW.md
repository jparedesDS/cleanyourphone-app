<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — 你的手機，減去多餘" width="100%">
  </a>
</p>

<p align="center">
  <b>選用的 Windows 應用程式</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill 與 CLI</a> ·
  <a href="https://cleanyourphone.org/">網站</a> ·
  <a href="https://cleanyourphone.org/#feedback">意見回饋</a>
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
  <b>繁體中文</b> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/jparedesDS/cleanyourphone-app/releases"><img src="https://img.shields.io/github/v/release/jparedesDS/cleanyourphone-app?color=a78bfa&labelColor=121316" alt="release"></a>
  <img src="https://img.shields.io/badge/Windows-10%2F11%20x64-a78bfa?labelColor=121316" alt="Windows 10/11 x64">
  <img src="https://img.shields.io/badge/license-MIT-a78bfa?labelColor=121316" alt="MIT">
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="沒有遙測">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="已在 OnePlus 6T 測試">
</p>

# CleanYourPhone 應用程式

**CleanYourPhone skill 的選用 Windows 應用程式。** 為偏好按鈕而非提示詞的人提供本機、可逆的
精簡流程：連接、檢查、備份、逐一檢視每個套件、分批套用、驗證與復原。skill 仍是主要產品；
對它能驗證的手機來說，這個應用程式是更簡單的途徑。

[下載 Early MVP](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) ·
[Skill 與 CLI](https://github.com/jparedesDS/cleanyourphone) ·
[連線指南](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) ·
[意見回饋](https://cleanyourphone.org/#feedback)

## 狀態

`v0.2.1` 是 Early MVP，僅支援 Windows 10/11 x64，而且**未經程式碼簽署**。已在
**OnePlus 6T（Android 11）** 上完成端對端測試：連接、檢查、備份、檢視、停用一個套件、
驗證、完成與復原。

應用程式刻意拒絕猜測。只有在能符合以下情況時才會繼續：

| 手機 | 應用程式的行為 |
|---|---|
| 確切的 `device` 設定檔，且 build 列於 `tested` | 以已測試的套件清單進行引導式流程。 |
| 符合機型、韌體系列與 Android 版本的 `documented` 設定檔 | 顯示警告、要求明確確認，並**每批只套用一個套件**。 |
| 相同機型，但 build 或 OTA 不同 | 停下來並連結到 skill。 |
| 沒有設定檔、受管理手機、多重使用者、Android < 8 或 TV | 停下來並連結到 skill 或安全文件。 |

`documented` 設定檔來自韌體 dump。它是證據，不是實機測試；套件可能因地區、電信業者或更新
而不同。

<p align="center">
  <img src="docs/images/app-review.png" alt="CleanYourPhone 應用程式的檢視畫面，顯示 documented 設定檔警告、一個已選取的應用程式，以及可隨時復原的備份路徑" width="760">
</p>

## 功能

- **Wi-Fi 或 USB。** 在 Android 11 以上透過無線偵錯配對，或使用資料傳輸線。應用程式會找到
  手機、檢查 build，並在整個工作階段維持同一種傳輸方式。
- **確切設定檔檢查。** 顯示機型、Android 版本、build、電量、設定檔，以及該 build 是否可
  自動套用。
- **強制備份。** 第一次變更前，備份套件清單、角色、設定與 `getprop`。
- **逐一檢視每個套件。** `DISABLE`、`ASK`、`BLOCKED` 與 `SKIP`，並說明為何列入以及可能壞掉
  什麼。沒有經過檢視的選取，就不會停用任何東西。
- **批次與驗證。** `device` 設定檔每批五個套件；`documented` 設定檔每批一個，且每個之後都
  檢查手機。
- **復原整份日誌。** 一個動作就能復原應用程式為該手機記錄的每一項變更，包括較早的工作
  階段。備份是備援方案。
- **選用 Private DNS。** AdGuard、AdGuard Family、Control D 與 Mullvad 預設，外加一項不會
  宣稱 YouTube 廣告已遭阻擋的檢查。請見
  [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md)。
- **選用的前後效能測試。** 本機的可用記憶體、處理程序與套件數。結果為約略值、不具因果
  關係；不會儲存序號或指紋。
- **選用意見回饋。** 經明確同意後，可將預先填入且可編輯的檢查清單送給維護者。沒有自動
  遙測。請見
  [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md)。

<p align="center">
  <img src="docs/images/app-connect.png" alt="CleanYourPhone 應用程式的連接畫面，顯示 Wi-Fi 與 USB 操作說明，以及連線指南連結" width="760">
</p>

## 安裝

從
[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) 下載
`CleanYourPhone-Setup-0.2.1.exe`，或在本機建置。

已發佈 `v0.2.1` 安裝程式的 SHA-256：

```text
B522B70B5F56B837EEE54F60D726C56F742667CF6B8B1BE52A913DD99C2D98E1
```

安裝程式以每位使用者為範圍，會建立開始功能表捷徑，且不需要系統管理員權限。它會安裝到
`%LOCALAPPDATA%\Programs\CleanYourPhone`。

Windows SmartScreen 可能會顯示 **「Windows 已保護您的電腦」**，因為這個 build 未簽署。只有
在驗證下載內容與 SHA-256 之後，才選擇 **更多資訊 → 仍要執行**。請勿停用 SmartScreen。

如果這是你第一次使用 ADB，請依照
[連線指南](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md)。內容涵蓋
隱藏的無線偵錯畫面、配對連接埠與連線連接埠的差異、USB 資料傳輸線、Windows 驅動程式，以及
瀏覽器的桌面版網站設定。

解除安裝會移除應用程式檔案與捷徑。它會刻意保留 `%USERPROFILE%\.cleanyourphone` 中的復原
日誌與手機備份，以及 `%LOCALAPPDATA%\CleanYourPhone` 中的設定。

ADB 未隨附或重新散布。應用程式會尋找現有的 Platform-Tools 安裝，或在首次執行時從 Google
下載官方壓縮檔。請見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安全模型

應用程式是同一套 CLI 的 GUI；防護措施不會改變：

- **只停用，不解除安裝。** 只用 `pm disable-user --user 0`；`pm enable` 是復原方式。
- **不需要 root、自訂 ROM、解鎖 bootloader，也不需要 Shizuku。**
- **沒有備份，就沒有變更。** 沒有通過驗證的備份，套用按鈕會保持停用。
- **受保護的套件與角色一律拒絕。** 電信、Play Services、WebView、permission controller、
  緊急警報、目前的撥號程式、簡訊、Home 與鍵盤都不能停用。
- **每個工作階段只用一種傳輸方式。** 工作階段中途切換 Wi-Fi／USB 會被拒絕；請開始新的工作
  階段。
- **遇到未知就停止。** 受管理裝置、多重使用者、Android < 8、TV，以及沒有相符設定檔的手機，
  都不會被變更。
- **沒有自動遙測。** 應用程式在本機執行。它唯一的網路呼叫，是選用的 Google Platform-Tools
  下載，以及使用者按下送出後的意見回饋表單。

## 建置

需求：Windows 10/11 x64、Python 3.12+、Git 與 Inno Setup 6
（`choco install innosetup -y` 或 <https://jrsoftware.org/isdl.php>）。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

指令碼會：

1. clone 固定的 CLI 標籤（`v0.3.3`）；
2. 將 CLI 凍結為 onedir sidecar；
3. 準備 156 個設定檔；
4. 凍結 PySide6 應用程式；
5. 對兩個執行檔進行 smoke test；
6. 編譯每位使用者的安裝程式。

輸出：

- `dist/CleanYourPhone/CleanYourPhone.exe`（可攜式 onedir 應用程式）
- `dist/CleanYourPhone-Setup-0.2.1.exe`（安裝程式）

將 `CLEANYOURPHONE_CLI` 設為凍結的 sidecar，並執行
`python -m pytest tests/test_cli_contract.py`，以納入真實 sidecar 的契約測試。

## 開發

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

應用程式的測試套件涵蓋連線防護、序號綁定、documented 設定檔確認、每批只套用一個、備份
把關、復原、意見回饋內容、意見回饋同意與 UI 文案。已發佈的 `0.2.1` 測試套件結果為
**520 通過、1 略過**。

## 儲存庫導覽

| 路徑 | 內容 |
|---|---|
| `src/cleanyourphone_app/domain/` | 純規則：支援判斷、檢視模型、工作階段、批次、意見回饋內容。 |
| `src/cleanyourphone_app/services/` | ADB 定位器、Wi-Fi 配對、CLI 用戶端、下載、意見回饋 HTTP 用戶端、記錄、設定。 |
| `src/cleanyourphone_app/ui/pages/` | 連接、檢查、備份、檢視、套用、完成、初始設定、歡迎、封鎖。 |
| `src/cleanyourphone_app/ui/dialogs/` | 選用的意見回饋對話方塊。 |
| `scripts/build-cli-sidecar.ps1` | 建置固定的 CLI sidecar 並準備設定檔。 |
| `scripts/build-app.ps1` | 建置應用程式、進行 smoke test 並編譯安裝程式。 |
| `packaging/installer.iss` | 每位使用者的 Inno Setup 安裝程式。 |
| `docs/superpowers/` | 歷史設計與實作計畫。 |
| `tests/` | Pytest 測試套件；`0.2.1` 上 520 通過、1 略過。 |

## 限制

- 僅支援 Windows 10/11 x64。目前尚無 macOS 或 Linux 桌面應用程式。
- 這個 build 未經程式碼簽署。
- 只支援上述確切的設定檔與 build；其他所有手機都會被導向 skill。
- `documented` 模式由應用程式測試套件涵蓋，尚未經過實體的 documented 裝置驗證。
- ADB 仍需要開發人員選項與已授權的電腦。

## 連結

- **Skill 與 CLI：** <https://github.com/jparedesDS/cleanyourphone>
- **網站：** <https://cleanyourphone.org/>
- **連線指南：** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **意見回饋與隱私：** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **設定檔：** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **安全性：** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## 授權

MIT。請見 [LICENSE](LICENSE)。第三方聲明在
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
