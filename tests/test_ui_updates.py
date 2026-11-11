import time

from cleanyourphone_app.services.settings import Settings
from cleanyourphone_app.services.updates import UpdateCheckError, UpdateInfo
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.main_window import MainWindow


def context_with_checker(checker):
    settings = Settings.in_memory()
    settings.last_update_check = int(time.time())
    return AppContext.fake(settings=settings, update_checker=checker)


def test_update_banner_shows_and_can_be_dismissed(qtbot):
    info = UpdateInfo(version="0.2.2", tag="v0.2.2")
    window = MainWindow(context_with_checker(lambda _version: info))
    qtbot.addWidget(window)
    window.show()

    window.update_button.click()

    qtbot.waitUntil(lambda: window.update_banner.isVisible(), timeout=3000)
    assert "0.2.2" in window.update_banner_label.text()
    assert window.update_open_button.text() == "Open GitHub"

    window.update_later_button.click()
    assert not window.update_banner.isVisible()


def test_banner_offers_update_now_when_the_installer_is_verified(qtbot):
    info = UpdateInfo(
        version="0.2.3",
        tag="v0.2.3",
        installer_url=(
            "https://github.com/jparedesDS/cleanyourphone-app/releases/download/"
            "v0.2.3/CleanYourPhone-Setup-0.2.3.exe"
        ),
        sha256="a" * 64,
    )
    window = MainWindow(context_with_checker(lambda _version: info))
    qtbot.addWidget(window)
    window.show()

    window.update_button.click()

    qtbot.waitUntil(lambda: window.update_banner.isVisible(), timeout=3000)
    assert window.update_open_button.text() == "Update now"


def test_manual_check_reports_when_there_is_no_update(qtbot):
    window = MainWindow(context_with_checker(lambda _version: None))
    qtbot.addWidget(window)
    window.show()

    window.update_button.click()

    qtbot.waitUntil(
        lambda: "up to date" in window.statusBar().currentMessage().lower(),
        timeout=3000,
    )


def test_manual_check_reports_a_network_failure(qtbot):
    def failing(_version):
        raise UpdateCheckError("offline")

    window = MainWindow(context_with_checker(failing))
    qtbot.addWidget(window)
    window.show()

    window.update_button.click()

    qtbot.waitUntil(
        lambda: "could not check" in window.statusBar().currentMessage().lower(),
        timeout=3000,
    )


def test_banner_is_retranslated_with_the_language(qtbot):
    info = UpdateInfo(version="0.2.2", tag="v0.2.2")
    window = MainWindow(context_with_checker(lambda _version: info))
    qtbot.addWidget(window)
    window.show()

    window.update_button.click()
    qtbot.waitUntil(lambda: window.update_banner.isVisible(), timeout=3000)

    window.set_language("es")

    assert "0.2.2" in window.update_banner_label.text()
    assert "disponible" in window.update_banner_label.text()
    assert window.update_open_button.text() == "Abrir GitHub"
