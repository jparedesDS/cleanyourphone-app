"""Application composition root and process entry point."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from cleanyourphone_app.domain.session import SessionController
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import AdbLocator
from cleanyourphone_app.services.adb_wifi import WifiConnector
from cleanyourphone_app.services.cli import CliClient
from cleanyourphone_app.services.downloads import PlatformToolsDownloader
from cleanyourphone_app.services.logging import (
    LOGGER_NAME,
    configure_logging,
    default_log_path,
)
from cleanyourphone_app.services.settings import Settings
from cleanyourphone_app.version import __version__

from .main_window import MainWindow


@dataclass
class AppContext:
    """The long-lived services every page receives from the shell."""

    translator: Translator
    session: SessionController
    cli: CliClient
    adb_locator: AdbLocator
    wifi: WifiConnector | None
    settings: Settings
    downloads: PlatformToolsDownloader
    adb_path: str | None = None

    def __post_init__(self) -> None:
        if not self.adb_path:
            self.adb_path = self.settings.adb_path

    @classmethod
    def fake(cls, **overrides: Any) -> AppContext:
        """Build deterministic services for UI tests; no process or network."""
        defaults: dict[str, Any] = {
            "translator": Translator("en"),
            "session": SessionController(),
            "cli": CliClient(("cleanyourphone",)),
            "adb_locator": AdbLocator(version_runner=lambda _path: None),
            "wifi": None,
            "settings": Settings.in_memory(),
            "downloads": PlatformToolsDownloader(),
            "adb_path": None,
        }
        valid = {field.name for field in fields(cls)}
        unknown = set(overrides) - valid
        if unknown:
            names = ", ".join(sorted(unknown))
            raise TypeError(f"unknown AppContext field(s): {names}")
        defaults.update(overrides)
        return cls(**defaults)


def create_context(settings: Settings | None = None) -> AppContext:
    """Wire the real services for a normal launch."""
    loaded = settings if settings is not None else Settings.load()
    system_language = Translator.for_system_language(QLocale.system().name())
    language = loaded.language or system_language.language
    env = {"ADB": loaded.adb_path} if loaded.adb_path else None

    return AppContext(
        translator=Translator(language),
        session=SessionController(),
        cli=CliClient(("cleanyourphone",), env=env),
        adb_locator=AdbLocator(),
        wifi=None,
        settings=loaded,
        downloads=PlatformToolsDownloader(),
        adb_path=loaded.adb_path,
    )


def run(argv: Sequence[str] | None = None) -> int:
    """Start the Qt event loop and return its exit code."""
    arguments = [sys.argv[0], *list(sys.argv[1:] if argv is None else argv)]
    app = QApplication.instance()
    if app is None:
        app = QApplication(arguments)
    app.setApplicationName("CleanYourPhone")
    app.setApplicationDisplayName("CleanYourPhone")
    app.setOrganizationName("CleanYourPhone")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")

    configure_logging(default_log_path())
    logging.getLogger(LOGGER_NAME).info("CleanYourPhone app %s starting", __version__)

    window = MainWindow(create_context())
    window.show()
    return int(app.exec())


__all__ = ["AppContext", "create_context", "run"]
