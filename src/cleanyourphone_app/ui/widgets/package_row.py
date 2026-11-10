"""One package row in the review list.

The row owns only presentation. The page owns the :class:`ReviewModel`, so a
checkbox change is reported through ``toggled`` and the page decides what the
selection means. Non-selectable rows (blocked, skipped, missing, kept) hide the
checkbox and show the reason instead.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.models import PlanRow
from cleanyourphone_app.i18n.packages import PackageCatalog

_DEFAULT_LABELS: dict[str, str] = {
    "review.why": "Why",
    "review.breaks": "What can break",
    "review.disable": "Disable",
    "review.leave_as_is": "Leave it as it is",
    "review.blocked": "Not changed",
}

ENGLISH_DETAILS_NOTE = "Detalles en inglés"


def _default_tr(key: str) -> str:
    return _DEFAULT_LABELS.get(key, key)


class PackageRow(QFrame):
    """Checkable detail row for one plan package."""

    toggled = Signal(str, bool)

    def __init__(
        self,
        row: PlanRow,
        catalog: PackageCatalog | None = None,
        *,
        checked: bool = False,
        selectable: bool = True,
        friendly_name: str | None = None,
        tr: Callable[[str], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(row, PlanRow):
            raise TypeError("row must be a PlanRow")
        if not isinstance(selectable, bool):
            raise TypeError("selectable must be a boolean")
        super().__init__(parent)
        self.row = row
        self.catalog = catalog
        self._selectable = selectable
        self._friendly_name = friendly_name
        self._tr = tr or _default_tr

        self.setObjectName("PackageRow")
        self.setProperty("selectable", selectable)
        self.setFrameShape(QFrame.Shape.NoFrame)
        if selectable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(12)

        self.checkbox = QCheckBox(self)
        self.checkbox.setObjectName("package_row_checkbox")
        self.checkbox.setChecked(checked)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.toggled.connect(self._checkbox_toggled)
        outer.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(10)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("package_row_name")
        self.name_label.setProperty("role", "brand")
        self.name_label.setWordWrap(True)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("package_row_status")
        self.status_label.setProperty("role", "muted")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )

        heading.addWidget(self.name_label, 1)
        heading.addWidget(self.status_label, 0)
        body.addLayout(heading)

        self.package_label = QLabel(self)
        self.package_label.setObjectName("package_row_id")
        self.package_label.setProperty("role", "package-id")
        self.package_label.setWordWrap(True)

        self.why_label = QLabel(self)
        self.why_label.setObjectName("package_row_why")
        self.why_label.setProperty("role", "body")
        self.why_label.setWordWrap(True)

        self.breaks_label = QLabel(self)
        self.breaks_label.setObjectName("package_row_breaks")
        self.breaks_label.setProperty("role", "body")
        self.breaks_label.setWordWrap(True)

        self.english_note_label = QLabel(self)
        self.english_note_label.setObjectName("package_row_english_note")
        self.english_note_label.setProperty("role", "muted")
        self.english_note_label.setWordWrap(True)

        self.reason_label = QLabel(self)
        self.reason_label.setObjectName("package_row_reason")
        self.reason_label.setProperty("role", "muted")
        self.reason_label.setWordWrap(True)

        body.addWidget(self.package_label)
        body.addWidget(self.why_label)
        body.addWidget(self.breaks_label)
        body.addWidget(self.english_note_label)
        body.addWidget(self.reason_label)
        outer.addLayout(body, 1)

        for label in (
            self.name_label,
            self.status_label,
            self.package_label,
            self.why_label,
            self.breaks_label,
            self.english_note_label,
            self.reason_label,
        ):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        if not selectable:
            self.checkbox.hide()
            self.checkbox.setEnabled(False)

        self.retranslate()

    # --------------------------------------------------------------- behavior

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool) -> None:
        if not self._selectable:
            return
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(bool(checked))
        self.checkbox.blockSignals(False)
        self._update_status()

    def toggle(self) -> None:
        if self._selectable:
            self.checkbox.toggle()

    def _checkbox_toggled(self, checked: bool) -> None:
        self._update_status()
        self.toggled.emit(self.row.package, checked)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self._selectable
            and event.button() == Qt.MouseButton.LeftButton
            and not self.checkbox.geometry().contains(event.position().toPoint())
        ):
            self.checkbox.toggle()
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------ translation

    def retranslate(self) -> None:
        tr = self._tr
        display_name = self._friendly_name or self.row.package
        self.name_label.setText(display_name)
        self.name_label.setVisible(bool(display_name.strip()))
        self.package_label.setText(self.row.package)
        self.package_label.setVisible(bool(self._friendly_name))

        why_text, why_translated = self._detail("why", self.row.why)
        breaks_text, breaks_translated = self._detail("breaks", self.row.breaks)
        used_english = (
            bool(self.row.why.strip()) and not why_translated
        ) or (bool(self.row.breaks.strip()) and not breaks_translated)

        if why_text.strip():
            self.why_label.setText(f"{tr('review.why')}: {why_text}")
            self.why_label.show()
        else:
            self.why_label.clear()
            self.why_label.hide()

        if breaks_text.strip():
            self.breaks_label.setText(f"{tr('review.breaks')}: {breaks_text}")
            self.breaks_label.show()
        else:
            self.breaks_label.clear()
            self.breaks_label.hide()

        if used_english:
            self.english_note_label.setText(ENGLISH_DETAILS_NOTE)
            self.english_note_label.show()
        else:
            self.english_note_label.clear()
            self.english_note_label.hide()

        if not self._selectable and self.row.reason.strip():
            self.reason_label.setText(self.row.reason)
            self.reason_label.show()
        else:
            self.reason_label.clear()
            self.reason_label.hide()

        self._update_status()
        self._update_accessible_names(display_name)

    def _detail(self, field: str, english: str) -> tuple[str, bool]:
        if self.catalog is None:
            return english, False
        return self.catalog.lookup(self.row.package, field, english)

    def _update_status(self) -> None:
        if not self._selectable:
            text = self._tr("review.blocked")
        elif self.checkbox.isChecked():
            text = self._tr("review.disable")
        else:
            text = self._tr("review.leave_as_is")
        self.status_label.setText(text)

    def _update_accessible_names(self, display_name: str) -> None:
        if display_name == self.row.package:
            description = self.row.package
        else:
            description = f"{display_name} ({self.row.package})"
        self.setAccessibleName(description)
        self.checkbox.setAccessibleName(description)
        self.status_label.setAccessibleName(self.status_label.text())


__all__ = ["PackageRow"]
