"""PySide6 app shell, composition root and shared theme."""

from .app import AppContext, create_context, run
from .main_window import MainWindow

__all__ = ["AppContext", "MainWindow", "create_context", "run"]
