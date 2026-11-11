<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — 你的手机，减去多余" width="100%">
  </a>
</p>

<p align="center">
  <b>可选的 Windows 应用</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill 与 CLI</a> ·
  <a href="https://cleanyourphone.org/">网站</a> ·
  <a href="https://cleanyourphone.org/#feedback">反馈</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.ja.md">日本語</a> ·
  <b>简体中文</b> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/jparedesDS/cleanyourphone-app/releases"><img src="https://img.shields.io/github/v/release/jparedesDS/cleanyourphone-app?color=a78bfa&labelColor=121316" alt="release"></a>
  <img src="https://img.shields.io/badge/Windows-10%2F11%20x64-a78bfa?labelColor=121316" alt="Windows 10/11 x64">
  <img src="https://img.shields.io/badge/license-MIT-a78bfa?labelColor=121316" alt="MIT">
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="无遥测">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="已在 OnePlus 6T 上测试">
</p>

# CleanYourPhone 应用

**CleanYourPhone Skill 的可选 Windows 应用。** 面向更喜欢点按钮而不是输入提示词的人，提供本地、可逆的精简流程：连接、检查、备份、逐个审阅应用包、分批执行、验证和撤销。Skill 仍是主要产品；这个应用是它能验证的手机的简单路径。

[下载早期 MVP](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) · [Skill 与 CLI](https://github.com/jparedesDS/cleanyourphone) · [连接指南](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) · [反馈](https://cleanyourphone.org/#feedback)

## 状态

`v0.2.2` 是早期 MVP，仅支持 Windows 10/11 x64，并且**未进行代码签名**。它已在一部 **OnePlus 6T（Android 11）** 上完成端到端测试：连接、检查、备份、审阅、停用一个应用包、验证、完成和撤销。

应用刻意不做猜测。只有能够匹配以下情况时才会继续：

| 手机 | 应用的行为 |
|---|---|
| 精确的 `device` 机型配置，且构建列在 `tested` 中 | 使用经过测试的应用包列表走引导流程。 |
| 匹配型号、固件系列和 Android 版本的 `documented` 机型配置 | 显示警告，要求明确确认，并且**每批只处理一个应用包**。 |
| 型号相同，但构建或 OTA 不同 | 停止并链接到 Skill。 |
| 没有匹配的机型配置、受管理手机、多用户、Android < 8 或 TV | 停止并链接到 Skill 或安全文档。 |

`documented` 机型配置来自固件转储。它是证据，不是真机测试；应用包可能因地区、运营商或更新而异。

<p align="center">
  <img src="docs/images/app-review.png" alt="CleanYourPhone 应用审阅界面，显示 documented 机型配置警告、一个已选应用和可撤销的备份路径" width="760">
</p>

## 它能做什么

- **Wi-Fi 或 USB。** 通过无线调试配对 Android 11+ 设备，或使用数据线。应用会找到手机、检查构建，并在整个会话中保持同一种连接方式。
- **精确的机型配置检查。** 显示型号、Android 版本、构建、电量、机型配置，以及该构建是否可自动执行。
- **强制备份。** 第一次更改前备份应用包列表、角色、设置和 `getprop`。
- **逐个审阅每个应用包。** `DISABLE`、`ASK`、`BLOCKED` 和 `SKIP`，并说明列入原因以及可能破坏什么。没有经过审阅的选择，就不会停用任何内容。
- **分批与验证。** `device` 机型配置每批五个应用包；`documented` 机型配置每批一个，并在每处理一个后检查手机。
- **撤销整份操作日志。** 一个操作即可恢复应用为该手机记录的所有更改，包括更早的会话。备份是兜底方案。
- **可选的私人 DNS。** 提供 AdGuard、AdGuard Family、Control D 和 Mullvad 预设，以及一项不会声称已拦截 YouTube 广告的检查。见 [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md)。
- **可选的前后基准测试。** 在本地统计可用 RAM、进程数和应用包数量。结果近似，不代表因果关系；不保存序列号或构建指纹。
- **可选反馈。** 经过明确同意后，可以把一份预填且可编辑的清单发送给维护者。没有自动遥测。见 [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md)。
- **更新检查。** 应用最多每六小时向 GitHub 查询一次最新版本。如果有更新的版本，横幅会打开发布页面。应用绝不会自行下载或安装更新，也不会发送账户、手机或使用数据。

<p align="center">
  <img src="docs/images/app-connect.png" alt="CleanYourPhone 连接界面，显示 Wi-Fi 和 USB 说明以及连接指南链接" width="760">
</p>

## 安装

从 [releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) 下载 `CleanYourPhone-Setup-0.2.2.exe`，或在本地构建。

已发布的 `v0.2.2` 安装包 SHA-256：

```text
E827AB24CB02E7C18F7577E6C00E263C1CCEC6683E7812E8F22222FC3AF216E3
```

安装程序按用户安装，会创建开始菜单快捷方式，不需要管理员权限。安装位置为 `%LOCALAPPDATA%\Programs\CleanYourPhone`。

由于该构建未签名，Windows SmartScreen 可能会显示 **“Windows 已保护你的电脑”**。只有在校验下载文件和 SHA-256 之后，才选择 **更多信息 → 仍要运行**。不要关闭 SmartScreen。

如果你是第一次使用 ADB，请按照[连接指南](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md)操作。它涵盖隐藏的无线调试界面、配对端口与连接端口的区别、USB 数据线、Windows 驱动以及浏览器的桌面版网站设置。

卸载会删除应用文件和快捷方式。它会特意保留 `%USERPROFILE%\.cleanyourphone` 中的撤销日志和手机备份，以及 `%LOCALAPPDATA%\CleanYourPhone` 中的设置。

ADB 不随应用捆绑或再分发。应用会查找已有的 Platform-Tools 安装，或首次运行时从 Google 下载官方压缩包。见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安全模型

该应用是同一套 CLI 之上的图形界面；防护栏不会改变：

- **只停用，不卸载。** 只用 `pm disable-user --user 0`；`pm enable` 就是撤销。
- **没有 root、自定义 ROM、bootloader 解锁或 Shizuku 的要求。**
- **没有备份，就不做更改。** 没有经过验证的备份时，执行按钮会保持禁用。
- **受保护的应用包和角色会被拒绝。** 电话功能、Google Play 服务、WebView、permission controller、紧急警报、当前拨号器、短信、桌面和键盘都不能被停用。
- **每个会话只用一种连接方式。** 会话中途在 Wi-Fi/USB 之间切换会被拒绝；请开始新会话。
- **遇到未知情况就停止。** 受管理设备、多用户、Android < 8、TV 以及没有匹配机型配置的手机都不会被更改。
- **没有自动遥测。** 应用是本地工具。它唯一的网络访问是：可选下载 Google Platform-Tools、GitHub 更新检查，以及在使用者按下“发送”后提交反馈表单。

## 构建

要求：Windows 10/11 x64、Python 3.12+、Git 和 Inno Setup 6（`choco install innosetup -y` 或 <https://jrsoftware.org/isdl.php>）。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

该脚本会：

1. 克隆固定版本的 CLI 标签（`v0.3.4`）；
2. 把 CLI 冻结为 onedir sidecar；
3. 暂存 157 个机型配置；
4. 冻结 PySide6 应用；
5. 对两个可执行文件做冒烟测试；
6. 编译按用户安装的安装程序。

输出：

- `dist/CleanYourPhone/CleanYourPhone.exe`（便携式 onedir 应用）
- `dist/CleanYourPhone-Setup-0.2.2.exe`（安装程序）

将 `CLEANYOURPHONE_CLI` 设为冻结后的 sidecar，并运行 `python -m pytest tests/test_cli_contract.py`，以包含真实 sidecar 的契约测试。

## 开发

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

应用测试套件覆盖连接防护、序列号绑定、`documented` 机型配置确认、每批只执行一个应用包、备份前置校验、撤销、反馈 payload、反馈同意和 UI 文案。已发布的 `0.2.2` 测试结果为 **520 通过，1 跳过**。

## 仓库结构

| 路径 | 说明 |
|---|---|
| `src/cleanyourphone_app/domain/` | 纯规则：支持判定、审阅模型、会话、批次、反馈 payload。 |
| `src/cleanyourphone_app/services/` | ADB 定位、Wi-Fi 配对、CLI 客户端、下载、反馈 HTTP 客户端、日志和设置。 |
| `src/cleanyourphone_app/ui/pages/` | 连接、检查、备份、审阅、执行、完成、设置、欢迎和受阻页。 |
| `src/cleanyourphone_app/ui/dialogs/` | 可选的反馈对话框。 |
| `scripts/build-cli-sidecar.ps1` | 构建固定版本的 CLI sidecar 并暂存机型配置。 |
| `scripts/build-app.ps1` | 构建应用、冒烟测试并编译安装程序。 |
| `packaging/installer.iss` | 按用户安装的 Inno Setup 安装程序。 |
| `docs/superpowers/` | 历史设计与实现计划。 |
| `tests/` | Pytest 测试套件；在 `0.2.2` 上 520 通过，1 跳过。 |

## 限制

- 仅支持 Windows 10/11 x64。目前还没有 macOS 或 Linux 桌面应用。
- 该构建未进行代码签名。
- 只支持上文列出的精确机型配置和构建；其他所有手机都会引导到 Skill。
- `documented` 模式已由应用测试套件覆盖，但尚未在真实的 `documented` 机型上验证。
- ADB 仍然需要开发者选项和一台已授权的电脑。

## 链接

- **Skill 与 CLI：** <https://github.com/jparedesDS/cleanyourphone>
- **网站：** <https://cleanyourphone.org/>
- **连接指南：** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **反馈与隐私：** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **机型配置：** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **安全：** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## 许可证

MIT。见 [LICENSE](LICENSE)。第三方声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
