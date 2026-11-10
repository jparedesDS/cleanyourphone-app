from pathlib import Path

from PySide6.QtCore import Qt

from cleanyourphone_app.domain.session import SessionController
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.settings import Settings
from cleanyourphone_app.ui.app import AppContext, create_context
from cleanyourphone_app.ui.main_window import MainWindow

PALETTE = ("#121316", "#1B1C21", "#F3F1EC", "#A78BFA", "#A19E96")
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "cleanyourphone_app"


def test_main_window_starts_on_welcome(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)
    assert window.current_page_name == "welcome"


def test_window_loads_the_website_palette(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)
    for color in PALETTE:
        assert color in window.styleSheet()


def test_window_minimum_size_is_900_by_640(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)
    assert window.minimumWidth() == 900
    assert window.minimumHeight() == 640


def test_language_switch_is_always_visible(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)
    window.show()
    assert window.language_switch.isVisible()
    assert window.language_buttons["es"].isVisible()
    assert window.language_buttons["en"].isVisible()


def test_language_switch_changes_copy_and_saves_the_setting(qtbot):
    context = AppContext.fake()
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.language_buttons["es"], Qt.MouseButton.LeftButton)

    assert context.translator.language == "es"
    assert context.settings.language == "es"
    assert window.step_labels["welcome"].text() == "Bienvenida"
    assert window.windowTitle() == "CleanYourPhone"
    assert window.language_buttons["es"].isChecked()
    assert not window.language_buttons["en"].isChecked()


def test_english_language_switch_returns_to_english(qtbot):
    context = AppContext.fake()
    context.translator.set_language("es")
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.language_buttons["en"], Qt.MouseButton.LeftButton)

    assert context.translator.language == "en"
    assert context.settings.language == "en"
    assert window.step_labels["welcome"].text() == "Welcome"


def test_step_indicator_tracks_the_current_page(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)

    assert window.current_step == "welcome"
    assert window.step_labels["welcome"].property("current") is True

    window.show_page("review")

    assert window.current_page_name == "review"
    assert window.current_step == "review"
    assert window.step_labels["review"].property("current") is True
    assert window.step_labels["welcome"].property("current") is False


def test_session_state_names_alias_to_flow_pages(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)
    window.show_page("checking")
    assert window.current_page_name == "check"
    window.show_page("applying")
    assert window.current_page_name == "apply"


def test_stack_contains_every_flow_page(qtbot):
    window = MainWindow(AppContext.fake())
    qtbot.addWidget(window)
    for name in ("welcome", "connect", "check", "backup", "review", "apply", "done"):
        window.show_page(name)
        assert window.current_page_name == name


def test_app_context_fake_provides_services():
    context = AppContext.fake()
    assert isinstance(context.translator, Translator)
    assert isinstance(context.session, SessionController)
    assert context.cli is not None
    assert context.adb_locator is not None
    assert context.wifi is None
    assert context.settings is not None
    assert context.downloads is not None


def test_app_context_fake_accepts_overrides():
    session = SessionController()
    context = AppContext.fake(session=session)
    assert context.session is session


def test_create_context_uses_saved_language_and_adb_path():
    context = create_context(
        Settings.in_memory(language="es", adb_path="C:/tools/adb.exe")
    )
    assert context.translator.language == "es"
    assert context.adb_path == "C:/tools/adb.exe"
    assert context.settings.language == "es"


def test_theme_and_logo_resources_exist():
    theme = PACKAGE_ROOT / "ui" / "theme.qss"
    logo = PACKAGE_ROOT / "resources" / "logo.svg"
    assert theme.is_file()
    assert logo.is_file()
    logo_text = logo.read_text(encoding="utf-8")
    assert "#A78BFA" in logo_text
    assert "#121316" in logo_text


def test_window_title_uses_the_app_name_in_both_languages(qtbot):
    context = AppContext.fake()
    window = MainWindow(context)
    qtbot.addWidget(window)
    assert window.windowTitle() == "CleanYourPhone"
    window.set_language("es")
    assert window.windowTitle() == "CleanYourPhone"
