"""The stop screen for phones outside the tested CleanYourPhone scope.

A missing device profile points at the skill website. Safety blockers (managed
phone, TV, multi-user phone or an Android version that is too old) point at the
safety documentation instead: the skill follows the same rules and cannot
bypass them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cleanyourphone_app.domain.support import SKILL_URL
from cleanyourphone_app.ui.pages.base import Page

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext

SAFETY_DOCS_URL = (
    "https://github.com/jparedesDS/cleanyourphone/blob/main/docs/SAFETY.md"
)

REASON_KEYS: dict[str, str] = {
    "no_device_profile": "blocked.no_profile",
    "untested_build": "blocked.untested_build",
    "managed": "blocked.managed",
    "managed_unknown": "blocked.managed_unknown",
    "users_unknown": "blocked.users_unknown",
    "multi_user": "blocked.multi_user",
    "android_too_old": "blocked.old_android",
    "tv": "blocked.tv",
    "role_check": "blocked.role_check",
}


class BlockedPage(Page):
    """Explain why the app stopped and offer the only safe next steps."""

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
        *,
        reason: str | None = None,
        link: str | None = None,
    ) -> None:
        super().__init__(context, parent)
        self.reason = reason
        self.link = link
        self._build_ui()
        self.show_blocked(reason, link)

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 44)
        layout.setSpacing(14)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.what_happened_label = QLabel(self)
        self.what_happened_label.setProperty("role", "brand")
        self.what_happened_label.setWordWrap(True)

        self.reason_label = QLabel(self)
        self.reason_label.setProperty("role", "body")
        self.reason_label.setWordWrap(True)

        self.not_changed_label = QLabel(self)
        self.not_changed_label.setProperty("role", "brand")
        self.not_changed_label.setWordWrap(True)

        self.nothing_changed_label = QLabel(self)
        self.nothing_changed_label.setProperty("role", "body")
        self.nothing_changed_label.setWordWrap(True)

        self.what_to_do_label = QLabel(self)
        self.what_to_do_label.setProperty("role", "brand")
        self.what_to_do_label.setWordWrap(True)

        self.skill_button = QPushButton(self)
        self.skill_button.setObjectName("blocked_skill_button")
        self.skill_button.setProperty("primary", True)
        self.skill_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skill_button.clicked.connect(self._open_link)

        self.docs_button = QPushButton(self)
        self.docs_button.setObjectName("blocked_docs_button")
        self.docs_button.setProperty("primary", True)
        self.docs_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.docs_button.clicked.connect(self._open_link)

        self.back_button = QPushButton(self)
        self.back_button.setObjectName("blocked_back_button")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(lambda checked=False: self._go("welcome"))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        buttons.addWidget(self.skill_button)
        buttons.addWidget(self.docs_button)
        buttons.addWidget(self.back_button)
        buttons.addStretch(1)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addSpacing(6)
        layout.addWidget(self.what_happened_label)
        layout.addWidget(self.reason_label)
        layout.addWidget(self.not_changed_label)
        layout.addWidget(self.nothing_changed_label)
        layout.addWidget(self.what_to_do_label)
        layout.addLayout(buttons)
        layout.addStretch(1)

    # ---------------------------------------------------------------- actions

    def show_blocked(self, reason: str | None, link: str | None) -> None:
        """Fill the stop screen with the reason and its safe link."""
        self.reason = reason if isinstance(reason, str) and reason else None
        self.link = link if isinstance(link, str) and link.strip() else None
        self.retranslate()

    def _update_actions(self) -> None:
        is_skill = self.link == SKILL_URL
        self.skill_button.setVisible(is_skill)
        self.docs_button.setVisible(self.link is not None and not is_skill)
        has_reason = self.reason is not None
        for widget in (
            self.what_happened_label,
            self.reason_label,
            self.not_changed_label,
            self.nothing_changed_label,
            self.what_to_do_label,
        ):
            widget.setVisible(has_reason)

        self.skill_button.setAccessibleName(self.skill_button.text())
        self.docs_button.setAccessibleName(self.docs_button.text())
        self.back_button.setAccessibleName(self.back_button.text())

    def _open_link(self, checked: bool = False) -> None:
        if self.link is None:
            return
        QDesktopServices.openUrl(QUrl(self.link))

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        self.title_label.setText(self.tr("blocked.title"))
        self.body_label.setText(self.tr("blocked.body"))
        self.what_happened_label.setText(self.tr("blocked.what_happened"))
        self.not_changed_label.setText(self.tr("blocked.not_changed"))
        self.nothing_changed_label.setText(self.tr("blocked.nothing_changed"))
        self.what_to_do_label.setText(self.tr("blocked.what_to_do"))
        self.skill_button.setText(self.tr("blocked.skill"))
        self.docs_button.setText(self.tr("blocked.docs"))
        self.back_button.setText(self.tr("blocked.back"))

        key = REASON_KEYS.get(self.reason or "")
        self.reason_label.setText(self.tr(key) if key is not None else "")
        self._update_actions()

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.reason_label.setAccessibleName(self.reason_label.text())
        self.skill_button.setAccessibleName(self.skill_button.text())
        self.docs_button.setAccessibleName(self.docs_button.text())
        self.back_button.setAccessibleName(self.back_button.text())


__all__ = ["REASON_KEYS", "SAFETY_DOCS_URL", "BlockedPage"]
