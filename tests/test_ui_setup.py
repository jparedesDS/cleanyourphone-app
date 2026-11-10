"""First-run ADB setup: consent, safe download and the manual picker."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import AdbInfo
from cleanyourphone_app.services.downloads import DownloadError
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.main_window import MainWindow
from cleanyourphone_app.ui.pages.setup import ANDROID_SDK_TERMS_URL, SetupPage


class FakeLocator:
    """A deterministic locator: ``find`` can stay empty while ``accept`` works."""

    def __init__(self, *, info=None, accepted=None, cache_dir=Path("C:/cache")):
        self.info = info
        self.accepted = dict(accepted or {})
        self.cache_dir = Path(cache_dir)
        self.find_calls = 0
        self.accept_calls = []

    def find(self):
        self.find_calls += 1
        return self.info

    def accept(self, path):
        candidate = Path(path)
        self.accept_calls.append(candidate)
        return self.accepted.get(candidate)


class FakeDownloader:
    """Records the destination and replays a result or a failure."""

    def __init__(self, *, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def download(self, destination):
        destination = Path(destination)
        self.calls.append(destination)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return Path(self.result)


class DeviceLister:
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.calls = []

    def __call__(self, info):
        self.calls.append(info)
        return list(self.entries)


def make_context(tmp_path, *, locator=None, downloader=None, lister=None, **overrides):
    locator = locator or FakeLocator(cache_dir=tmp_path)
    downloader = downloader or FakeDownloader(
        result=tmp_path / "platform-tools" / "adb.exe"
    )
    lister = lister or DeviceLister()
    values = {
        "translator": Translator("es"),
        "adb_locator": locator,
        "downloads": downloader,
        "device_lister": lister,
        "adb_path": None,
    }
    values.update(overrides)
    context = AppContext.fake(**values)
    return context, locator, downloader, lister


def make_info(path: Path) -> AdbInfo:
    return AdbInfo(path=path, version=(37, 0, 1), version_text="Version 37.0.1")


# ---------------------------------------------------------------------------
# Copy, consent and the manual option
# ---------------------------------------------------------------------------


def test_setup_page_shows_download_terms_consent_and_manual_option(qtbot, tmp_path):
    context, *_ = make_context(tmp_path)
    page = SetupPage(context)
    qtbot.addWidget(page)

    tr = context.translator.tr
    assert page.download_button.text() == "Descargar de Google"
    assert page.download_button.text() == tr("setup.download")
    assert page.consent_checkbox.text() == tr("setup.consent")
    assert page.have_adb_button.text() == "Ya tengo ADB"
    assert page.have_adb_button.text() == tr("setup.have_adb")
    assert ANDROID_SDK_TERMS_URL in page.terms_label.text()
    assert tr("setup.terms_link") in page.terms_label.text()
    assert page.terms_label.openExternalLinks() is True


def test_download_stays_disabled_until_consent(qtbot, tmp_path):
    context, _, downloader, _ = make_context(tmp_path)
    page = SetupPage(context)
    qtbot.addWidget(page)

    assert page.download_button.isEnabled() is False

    page.consent_checkbox.setChecked(True)
    assert page.download_button.isEnabled() is True

    page.consent_checkbox.setChecked(False)
    assert page.download_button.isEnabled() is False
    assert downloader.calls == []


# ---------------------------------------------------------------------------
# Download outcomes
# ---------------------------------------------------------------------------


def test_successful_download_stores_adb_and_moves_to_welcome(qtbot, tmp_path):
    adb_path = tmp_path / "platform-tools" / "adb.exe"
    downloader = FakeDownloader(result=adb_path)
    context, locator, downloader, _ = make_context(tmp_path, downloader=downloader)
    page = SetupPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)

    page.consent_checkbox.setChecked(True)
    page.download_button.click()

    assert downloader.calls == [tmp_path]
    assert locator.cache_dir == tmp_path
    assert context.adb_path == str(adb_path)
    assert context.settings.adb_path == str(adb_path)
    assert page.error_label.text() == ""
    assert page.next_page == "welcome"
    assert targets == ["welcome"]


def test_hash_failure_stays_on_setup_and_never_runs_adb(qtbot, tmp_path):
    downloader = FakeDownloader(
        error=DownloadError("Platform-Tools SHA-256 mismatch: expected a, got b")
    )
    context, locator, _, lister = make_context(tmp_path, downloader=downloader)
    page = SetupPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)

    page.consent_checkbox.setChecked(True)
    page.download_button.click()

    assert page.next_page is None
    assert targets == []
    assert page.error_label.text() == context.translator.tr("setup.hash_failed")
    assert page.error_label.isVisibleTo(page) is True
    assert lister.calls == []
    assert locator.accept_calls == []
    assert context.adb_path is None
    assert context.adb_info is None


def test_generic_download_failure_stays_on_setup(qtbot, tmp_path):
    downloader = FakeDownloader(error=DownloadError("could not download the archive"))
    context, locator, _, lister = make_context(tmp_path, downloader=downloader)
    page = SetupPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)

    page.consent_checkbox.setChecked(True)
    page.download_button.click()

    assert page.next_page is None
    assert targets == []
    assert page.error_label.text() == context.translator.tr("setup.download_failed")
    assert lister.calls == []
    assert locator.accept_calls == []
    assert context.adb_path is None


# ---------------------------------------------------------------------------
# Manual picker
# ---------------------------------------------------------------------------


def test_user_picked_valid_adb_moves_to_welcome(qtbot, tmp_path, monkeypatch):
    picked = tmp_path / "tools" / "adb.exe"
    picked.parent.mkdir()
    picked.write_bytes(b"")
    info = make_info(picked)
    locator = FakeLocator(accepted={picked: info}, cache_dir=tmp_path)
    context, _, _, _ = make_context(tmp_path, locator=locator)
    page = SetupPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(picked), "adb.exe (adb.exe)"),
    )

    page.have_adb_button.click()

    assert locator.accept_calls == [picked]
    assert context.adb_info is info
    assert context.adb_path == str(picked)
    assert context.settings.adb_path == str(picked)
    assert page.next_page == "welcome"
    assert targets == ["welcome"]


def test_user_picked_invalid_adb_stays_on_setup(qtbot, tmp_path, monkeypatch):
    picked = tmp_path / "tools" / "adb.exe"
    picked.parent.mkdir()
    picked.write_bytes(b"")
    locator = FakeLocator(accepted={}, cache_dir=tmp_path)
    context, _, _, _ = make_context(tmp_path, locator=locator)
    page = SetupPage(context)
    qtbot.addWidget(page)
    targets = []
    page.navigate.connect(targets.append)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(picked), "adb.exe (adb.exe)"),
    )

    page.have_adb_button.click()

    assert locator.accept_calls == [picked]
    assert page.next_page is None
    assert targets == []
    assert page.error_label.text() == context.translator.tr("setup.invalid_adb")
    assert context.adb_path is None


def test_cancelled_picker_changes_nothing(qtbot, tmp_path, monkeypatch):
    context, locator, _, _ = make_context(tmp_path)
    page = SetupPage(context)
    qtbot.addWidget(page)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", "")
    )

    page.have_adb_button.click()

    assert locator.accept_calls == []
    assert page.next_page is None
    assert context.adb_path is None


# ---------------------------------------------------------------------------
# Startup routing
# ---------------------------------------------------------------------------


def test_startup_shows_setup_when_adb_is_missing(qtbot, tmp_path):
    context, locator, _, _ = make_context(tmp_path)
    window = MainWindow(context)
    qtbot.addWidget(window)

    assert window.start_flow() == "setup"
    assert window.current_page_name == "setup"
    assert locator.find_calls == 1


def test_successful_download_from_the_window_continues_the_flow(qtbot, tmp_path):
    adb_path = tmp_path / "platform-tools" / "adb.exe"
    downloader = FakeDownloader(result=adb_path)
    locator = FakeLocator(
        accepted={adb_path: make_info(adb_path)}, cache_dir=tmp_path
    )
    context, _, _, _ = make_context(tmp_path, locator=locator, downloader=downloader)
    window = MainWindow(context)
    qtbot.addWidget(window)
    assert window.start_flow() == "setup"

    page = window.setup_page
    page.consent_checkbox.setChecked(True)
    page.download_button.click()

    assert window.current_page_name == "welcome"
    assert context.adb_info is not None
    assert context.adb_path == str(adb_path)


def test_startup_accepts_the_saved_adb_path(qtbot, tmp_path):
    saved = tmp_path / "tools" / "adb.exe"
    saved.parent.mkdir()
    saved.write_bytes(b"")
    info = make_info(saved)
    locator = FakeLocator(accepted={saved: info}, cache_dir=tmp_path)
    context, _, _, _ = make_context(
        tmp_path, locator=locator, adb_path=str(saved)
    )
    window = MainWindow(context)
    qtbot.addWidget(window)

    assert window.start_flow() == "welcome"
    assert window.current_page_name == "welcome"
    assert context.adb_info is info
    assert locator.find_calls == 0
