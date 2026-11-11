<p align="center">
  <a href="https://cleanyourphone.org/">
    <img src="assets/banner.png" alt="CleanYourPhone — あなたのスマホを、余計なものなしで" width="100%">
  </a>
</p>

<p align="center">
  <b>オプションの Windows アプリ</b> ·
  <a href="https://github.com/jparedesDS/cleanyourphone">Skill と CLI</a> ·
  <a href="https://cleanyourphone.org/">ウェブサイト</a> ·
  <a href="https://cleanyourphone.org/#feedback">フィードバック</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.it.md">Italiano</a> ·
  <b>日本語</b> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/jparedesDS/cleanyourphone-app/releases"><img src="https://img.shields.io/github/v/release/jparedesDS/cleanyourphone-app?color=a78bfa&labelColor=121316" alt="release"></a>
  <img src="https://img.shields.io/badge/Windows-10%2F11%20x64-a78bfa?labelColor=121316" alt="Windows 10/11 x64">
  <img src="https://img.shields.io/badge/license-MIT-a78bfa?labelColor=121316" alt="MIT">
  <img src="https://img.shields.io/badge/telemetry-none-a78bfa?labelColor=121316" alt="テレメトリーなし">
  <img src="https://img.shields.io/badge/tested-OnePlus%206T-a78bfa?labelColor=121316" alt="OnePlus 6T でテスト済み">
</p>

# CleanYourPhone アプリ

**CleanYourPhone skill で使う、オプションの Windows アプリ。** プロンプトよりボタンが好きな人のための、ローカルで元に戻せるデブロートフローです。接続、確認、バックアップ、すべてのパッケージのレビュー、バッチ適用、検証、元に戻す。skill が主力プロダクトであり、このアプリは検証できるスマホのための簡単な道です。

[Early MVP をダウンロード](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) · [Skill と CLI](https://github.com/jparedesDS/cleanyourphone) · [接続ガイド](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md) · [フィードバック](https://cleanyourphone.org/#feedback)

## 状態

`v0.2.1` は Early MVP で、Windows 10/11 x64 専用、**コード署名なし**です。**OnePlus 6T（Android 11）**で最初から最後までテストしました。接続、確認、バックアップ、レビュー、1 パッケージの無効化、検証、完了、元に戻す、まで。

アプリは意図的に推測を拒みます。次のように一致したときだけ先へ進みます:

| スマホ | アプリの動作 |
|---|---|
| `tested` に載っているビルドを持つ完全一致の `device` プロファイル | テスト済みパッケージ一覧によるガイド付きフロー。 |
| モデル、ファームウェアファミリー、Android バージョンが一致する `documented` プロファイル | 警告を表示し、明示的な確認を求め、**1 バッチ 1 パッケージ**で適用します。 |
| 同じモデルだが別のビルドまたは OTA | 停止して skill へリンクします。 |
| プロファイルなし、管理されたスマホ、複数ユーザー、Android 8 未満、TV | 停止して skill または安全ドキュメントへリンクします。 |

`documented` プロファイルはファームウェアダンプから作られます。これは証拠であり、実機テストではありません。パッケージは地域、キャリア、アップデートによって異なることがあります。

<p align="center">
  <img src="docs/images/app-review.png" alt="CleanYourPhone アプリのレビュー画面。documented プロファイルの警告、選択されたアプリ 1 つ、元に戻せるバックアップパスを表示" width="760">
</p>

## できること

- **Wi-Fi でも USB でも。** Android 11 以降はワイヤレスデバッグでペア設定するか、データケーブルを使います。アプリがスマホを見つけ、ビルドを確認し、セッション中は 1 つのトランスポートを維持します。
- **正確なプロファイル確認。** モデル、Android バージョン、ビルド、バッテリー、プロファイル、そのビルドが自動適用可能かを表示します。
- **必須のバックアップ。** 最初の変更前に、パッケージ一覧、ロール、設定、`getprop` を取得します。
- **すべてのパッケージをレビュー。** `DISABLE`、`ASK`、`BLOCKED`、`SKIP` と、なぜ一覧にあるのか、何が壊れうるかを表示します。レビュー済みの選択なしに何も無効化しません。
- **バッチと検証。** `device` プロファイルは 1 バッチ 5 パッケージ、`documented` プロファイルは 1 バッチ 1 パッケージで、それぞれの後にスマホを確認します。
- **ジャーナル全体を元に戻す。** 1 回の操作で、そのスマホについてアプリが記録したすべての変更（過去のセッションを含む）を復元します。バックアップはフォールバックです。
- **オプションのプライベート DNS。** AdGuard、AdGuard Family、Control D、Mullvad のプリセットに加え、YouTube の広告がブロックされたとは主張しない確認。詳細は [docs/ADS.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/ADS.md)。
- **オプションの前後ベンチマーク。** ローカルの空き RAM、プロセス数、パッケージ数。概算で因果関係はなく、シリアルもフィンガープリントも保存しません。
- **オプションのフィードバック。** 入力済みで編集可能なチェックリストを、明示的な同意後にメンテナーへ送れます。自動テレメトリーはありません。詳細は [docs/FEEDBACK.md](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md)。

<p align="center">
  <img src="docs/images/app-connect.png" alt="CleanYourPhone の接続画面。Wi-Fi と USB の手順、接続ガイドへのリンクを表示" width="760">
</p>

## インストール

[releases/latest](https://github.com/jparedesDS/cleanyourphone-app/releases/latest) から `CleanYourPhone-Setup-0.2.1.exe` をダウンロードするか、ローカルでビルドします。

公開されている `v0.2.1` インストーラーの SHA-256:

```text
B522B70B5F56B837EEE54F60D726C56F742667CF6B8B1BE52A913DD99C2D98E1
```

インストーラーはユーザー単位で、スタートメニューのショートカットを作成し、管理者権限を必要としません。`%LOCALAPPDATA%\Programs\CleanYourPhone` にインストールされます。

ビルドが署名されていないため、Windows SmartScreen が **「Windows によって PC が保護されました」** と表示することがあります。ダウンロードと SHA-256 を確認したあとだけ **詳細情報 → 実行** を選んでください。SmartScreen を無効にしないでください。

ADB を初めて使う場合は、[接続ガイド](https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md)に従ってください。非表示のワイヤレスデバッグ画面、ペア設定ポートと接続ポートの違い、USB データケーブル、Windows ドライバー、ブラウザーのデスクトップサイト設定を扱っています。

アンインストールすると、アプリのファイルとショートカットが削除されます。元に戻すためのジャーナルとスマホのバックアップは意図的に `%USERPROFILE%\.cleanyourphone` に、設定は `%LOCALAPPDATA%\CleanYourPhone` に残します。

ADB は同梱も再配布もされません。アプリは既存の Platform-Tools インストールを見つけるか、初回起動時に Google の公式アーカイブをダウンロードします。[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照。

## 安全モデル

アプリは同じ CLI の GUI であり、ガードレールは変わりません:

- **無効化のみ、アンインストールはしない。** `pm disable-user --user 0` だけ。`pm enable` が元に戻す操作です。
- **root なし、カスタム ROM なし、ブートローダー解除なし、Shizuku なし。**
- **バックアップがなければ変更しない。** 検証済みのバックアップがないと、適用ボタンは無効のままです。
- **保護パッケージとロールは拒否。** 電話、Play Services、WebView、permission controller、緊急アラート、現在のダイヤラー、SMS、Home、キーボードは無効化できません。
- **セッションごとに 1 つのトランスポート。** セッションの途中で Wi-Fi/USB を切り替えることは拒否されます。新しいセッションを開始してください。
- **不明なら停止。** 管理された端末、複数ユーザー、Android 8 未満、TV、一致するプロファイルのないスマホは変更しません。
- **自動テレメトリーなし。** アプリはローカルです。ネットワーク呼び出しは、オプションの Google Platform-Tools ダウンロードと、本人が送信を押した後のフィードバックフォームだけです。

## ビルド

要件: Windows 10/11 x64、Python 3.12+、Git、Inno Setup 6（`choco install innosetup -y` または <https://jrsoftware.org/isdl.php>）。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

スクリプトの内容:

1. 固定された CLI タグ（`v0.3.3`）をクローンします。
2. CLI を onedir サイドカーとしてフリーズします。
3. 156 個のプロファイルを配置します。
4. PySide6 アプリをフリーズします。
5. 両方の実行ファイルをスモークテストします。
6. ユーザー単位のインストーラーをコンパイルします。

出力:

- `dist/CleanYourPhone/CleanYourPhone.exe`（ポータブル onedir アプリ）
- `dist/CleanYourPhone-Setup-0.2.1.exe`（インストーラー）

`CLEANYOURPHONE_CLI` にフリーズしたサイドカーを設定し、`python -m pytest tests/test_cli_contract.py` を実行すると、実際のサイドカーとのコントラクトテストが含まれます。

## 開発

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

アプリのスイートは、接続ガード、シリアル固定、documented プロファイルの確認、1 バッチ 1 パッケージ適用、バックアップなしのブロック、元に戻す操作、フィードバックのペイロード、フィードバックの同意、UI 文言をカバーします。公開されている `0.2.1` のスイート結果は **520 件パス、1 件スキップ**です。

## リポジトリ構成

| パス | 内容 |
|---|---|
| `src/cleanyourphone_app/domain/` | 純粋なルール: サポート判定、レビューモデル、セッション、バッチ、フィードバックのペイロード。 |
| `src/cleanyourphone_app/services/` | ADB の検出、Wi-Fi ペア設定、CLI クライアント、ダウンロード、フィードバック HTTP クライアント、ログ、設定。 |
| `src/cleanyourphone_app/ui/pages/` | 接続、確認、バックアップ、レビュー、適用、完了、セットアップ、ようこそ、ブロック。 |
| `src/cleanyourphone_app/ui/dialogs/` | オプションのフィードバックダイアログ。 |
| `scripts/build-cli-sidecar.ps1` | 固定された CLI サイドカーをビルドし、プロファイルを配置する。 |
| `scripts/build-app.ps1` | アプリをビルドし、スモークテストし、インストーラーをコンパイルする。 |
| `packaging/installer.iss` | ユーザー単位の Inno Setup インストーラー。 |
| `docs/superpowers/` | 過去の設計と実装計画。 |
| `tests/` | pytest スイート。`0.2.1` では 520 件パス、1 件スキップ。 |

## 制限事項

- Windows 10/11 x64 のみ。macOS や Linux 向けのデスクトップアプリはまだありません。
- ビルドはコード署名されていません。
- 上記の完全一致のプロファイルとビルドのみをサポートします。それ以外のスマホはすべて skill へ案内されます。
- `documented` モードはアプリのスイートでカバーされていますが、documented プロファイルを持つ実機ではまだ検証されていません。
- ADB には引き続き開発者向けオプションと、許可されたパソコンが必要です。

## リンク

- **Skill と CLI:** <https://github.com/jparedesDS/cleanyourphone>
- **ウェブサイト:** <https://cleanyourphone.org/>
- **接続ガイド:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md>
- **フィードバックとプライバシー:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/FEEDBACK.md>
- **プロファイル:** <https://github.com/jparedesDS/cleanyourphone/tree/main/profiles>
- **安全性:** <https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md>

## ライセンス

MIT。[LICENSE](LICENSE) を参照。サードパーティの通知は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) にあります。
