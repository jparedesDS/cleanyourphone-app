"""Shared behavior for the flow pages.

Every page receives the same :class:`AppContext`, exposes ``retranslate()`` so
the language switch can refresh it in place, and reports the next page through
the ``navigate`` signal. ``MainWindow.register_page`` connects that signal, so a
page never needs a reference to the window itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext


class Page(QWidget):
    """Base class for a feature page in the main stack."""

    navigate = Signal(str)

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.next_page: str | None = None

    def tr(self, key: str, **kwargs: object) -> str:
        return self.context.translator.tr(key, **kwargs)

    def retranslate(self) -> None:
        """Refresh every translated string; subclasses override this."""

    def _go(self, page: str) -> None:
        self.next_page = page
        self.navigate.emit(page)


__all__ = ["Page"]
