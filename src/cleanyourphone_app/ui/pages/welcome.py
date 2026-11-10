"""The welcome choice: Wi-Fi first for Android 11+, USB as the fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cleanyourphone_app.ui.pages.base import Page

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext


class WelcomePage(Page):
    """Ask how the phone is attached and hand the choice to the window."""

    transport_selected = Signal(str)

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._build_ui()
        self.retranslate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 44)
        layout.setSpacing(18)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.hint_label = QLabel(self)
        self.hint_label.setProperty("role", "muted")
        self.hint_label.setWordWrap(True)

        self.wifi_button = QPushButton(self)
        self.wifi_button.setObjectName("wifi_button")
        self.wifi_button.setProperty("primary", True)
        self.wifi_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wifi_button.clicked.connect(
            lambda checked=False: self.transport_selected.emit("wifi")
        )

        self.usb_button = QPushButton(self)
        self.usb_button.setObjectName("usb_button")
        self.usb_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.usb_button.clicked.connect(
            lambda checked=False: self.transport_selected.emit("usb")
        )

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(12)
        buttons.addWidget(self.wifi_button)
        buttons.addWidget(self.usb_button)
        buttons.addStretch(1)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.hint_label)
        layout.addSpacing(10)
        layout.addLayout(buttons)
        layout.addStretch(1)

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("welcome.title"))
        self.body_label.setText(self.tr("welcome.body"))
        self.hint_label.setText(self.tr("welcome.hint"))
        self.wifi_button.setText(self.tr("welcome.wifi"))
        self.usb_button.setText(self.tr("welcome.usb"))

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.wifi_button.setAccessibleName(self.wifi_button.text())
        self.usb_button.setAccessibleName(self.usb_button.text())


__all__ = ["WelcomePage"]
