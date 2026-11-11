"""Application composition root and process entry point."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.domain.session import SessionController
from cleanyourphone_app.i18n.packages import PackageCatalog, default_package_catalog
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.adb import (
    AdbInfo,
    AdbLocator,
    DeviceEntry,
    list_devices,
)
from cleanyourphone_app.services.adb_wifi import WifiConnector
from cleanyourphone_app.services.cli import CliClient
from cleanyourphone_app.services.downloads import PlatformToolsDownloader
from cleanyourphone_app.services.logging import (
    LOGGER_NAME,
    configure_logging,
    default_log_path,
)
from cleanyourphone_app.services.settings import Settings
from cleanyourphone_app.services.updates import (
    UpdateInfo,
    check_for_update,
)
from cleanyourphone_app.version import __version__

from .main_window import MainWindow

DeviceLister = Callable[[AdbInfo], list[DeviceEntry]]


def bundle_root() -> Path:
    """Return the directory that holds ``resources`` for this process.

    A frozen onedir build keeps resources next to ``CleanYourPhone.exe``. A
    source checkout has no bundled sidecar or profiles unless a build staged
    them under the repository root.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[3]


def bundled_profiles_dir() -> Path | None:
    candidate = bundle_root() / "resources" / "profiles"
    return candidate if candidate.is_dir() else None


def bundled_sidecar() -> Path | None:
    candidate = bundle_root() / "resources" / "cli" / "cleanyourphone.exe"
    return candidate if candidate.is_file() else None


def sidecar_command() -> tuple[str, ...]:
    """Use the bundled sidecar when present, otherwise the CLI on ``PATH``."""
    sidecar = bundled_sidecar()
    if sidecar is not None:
        return (str(sidecar),)
    return ("cleanyourphone",)


def runtime_environment(adb_path: str | None) -> dict[str, str]:
    """Build the environment every sidecar call inherits.

    Profiles are read from the install directory; backup and state always live
    under the user's home so an uninstall never deletes a phone backup.
    """
    home = Path.home() / ".cleanyourphone"
    env = {
        "CLEANYOURPHONE_BACKUP": str(home / "backup"),
        "CLEANYOURPHONE_STATE": str(home),
    }
    profiles = bundled_profiles_dir()
    if profiles is not None:
        env["CLEANYOURPHONE_PROFILES"] = str(profiles)
    if adb_path:
        env["ADB"] = adb_path
    return env


@dataclass
class AppContext:
    """The long-lived services every page receives from the shell."""

    translator: Translator
    package_catalog: PackageCatalog
    session: SessionController
    cli: CliClient
    adb_locator: AdbLocator
    wifi: WifiConnector | None
    settings: Settings
    downloads: PlatformToolsDownloader
    adb_path: str | None = None
    adb_info: AdbInfo | None = None
    device_lister: DeviceLister = list_devices
    update_checker: Callable[[str], UpdateInfo | None] = check_for_update
    last_probe: ProbeData | None = None

    def __post_init__(self) -> None:
        if not self.adb_path:
            self.adb_path = self.settings.adb_path

    def _remember_adb_path(self, path: str) -> None:
        self.adb_path = path
        if self.settings.adb_path == path:
            return
        self.settings.adb_path = path
        try:
            self.settings.save()
        except OSError:
            logging.getLogger(LOGGER_NAME).warning("could not save the ADB path setting")

    def set_adb_path(self, path: str | os.PathLike[str]) -> str:
        """Store a downloaded adb path; the next startup verifies it."""
        value = os.fspath(path)
        self.adb_info = None
        self._remember_adb_path(value)
        return value

    def use_adb(self, info: AdbInfo) -> AdbInfo:
        """Pin a verified ADB binary and persist its path."""
        if not isinstance(info, AdbInfo):
            raise TypeError(f"use_adb requires an AdbInfo, not {type(info).__name__}")
        self.adb_info = info
        self.cli.set_adb_path(info.path)
        self._remember_adb_path(str(info.path))
        return info

    def locate_adb(self) -> AdbInfo | None:
        """Return the verified ADB for this run, honoring the saved path."""
        if self.adb_info is not None:
            return self.adb_info

        saved = (self.adb_path or "").strip()
        if saved:
            info = self.adb_locator.accept(saved)
            if info is not None:
                return self.use_adb(info)

        info = self.adb_locator.find()
        if info is not None:
            return self.use_adb(info)
        return None

    @classmethod
    def fake(cls, **overrides: Any) -> AppContext:
        """Build deterministic services for UI tests; no process or network."""
        defaults: dict[str, Any] = {
            "translator": Translator("en"),
            "package_catalog": default_package_catalog(),
            "session": SessionController(),
            "cli": CliClient(("cleanyourphone",)),
            "adb_locator": AdbLocator(version_runner=lambda _path: None),
            "wifi": None,
            "settings": Settings.in_memory(),
            "downloads": PlatformToolsDownloader(),
            "adb_path": None,
            "adb_info": None,
            "device_lister": lambda _info: [],
            "update_checker": lambda _version: None,
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
    env = runtime_environment(loaded.adb_path)

    return AppContext(
        translator=Translator(language),
        package_catalog=default_package_catalog(),
        session=SessionController(),
        cli=CliClient(sidecar_command(), env=env),
        adb_locator=AdbLocator(),
        wifi=None,
        settings=loaded,
        downloads=PlatformToolsDownloader(),
        adb_path=loaded.adb_path,
        update_checker=check_for_update,
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
    window.start_flow()
    window.show()
    return int(app.exec())


__all__ = ["AppContext", "create_context", "run"]
