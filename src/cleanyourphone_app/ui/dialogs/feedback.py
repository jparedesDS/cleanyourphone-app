"""Optional feedback dialog: explicit consent, editable checklist, no telemetry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cleanyourphone_app.domain.feedback import (
    FEEDBACK_ENDPOINT,
    build_checklist,
    feedback_payload,
    validate_feedback,
)
from cleanyourphone_app.services.feedback import FeedbackError, send_feedback
from cleanyourphone_app.ui.workers import BackgroundCall
from cleanyourphone_app.version import __version__

if TYPE_CHECKING:
    from cleanyourphone_app.ui.app import AppContext


class FeedbackDialog(QDialog):
    """A local form that sends only after the person presses Send."""

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self._busy = False
        self._sent = False
        self._call = BackgroundCall(self)
        self._call.succeeded.connect(self._succeeded)
        self._call.failed.connect(self._failed)
        self._call.finished.connect(self._finished)
        self._build_ui()
        self.retranslate()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        self.setModal(True)
        self.setMinimumSize(620, 560)
        self.resize(680, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("feedback_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget(self.scroll)
        content.setObjectName("feedback_content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        self.title_label = QLabel(self)
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(self)
        self.body_label.setProperty("role", "body")
        self.body_label.setWordWrap(True)

        self.kind_label = QLabel(self)
        self.kind_combo = QComboBox(self)
        self.kind_combo.setObjectName("feedback_kind")
        self.kind_combo.addItem("", "feedback")
        self.kind_combo.addItem("", "bug")
        self.kind_combo.addItem("", "profile")

        self.message_label = QLabel(self)
        self.message_edit = QTextEdit(self)
        self.message_edit.setObjectName("feedback_message")
        self.message_edit.setFixedHeight(110)

        self.checklist_label = QLabel(self)
        self.checklist_edit = QTextEdit(self)
        self.checklist_edit.setObjectName("feedback_checklist")
        self.checklist_edit.setFixedHeight(170)

        self.checklist_help = QLabel(self)
        self.checklist_help.setProperty("role", "muted")
        self.checklist_help.setWordWrap(True)

        self.contact_label = QLabel(self)
        self.contact_edit = QLineEdit(self)
        self.contact_edit.setObjectName("feedback_contact")
        self.contact_edit.setMaxLength(200)

        self.consent_checkbox = QCheckBox(self)
        self.consent_checkbox.setObjectName("feedback_consent")

        self.status_label = QLabel(self)
        self.status_label.setObjectName("feedback_status")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        self.status_label.hide()

        self.send_button = QPushButton(self)
        self.send_button.setObjectName("feedback_send")
        self.send_button.setProperty("primary", True)
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.clicked.connect(self.send)

        self.close_button = QPushButton(self)
        self.close_button.setObjectName("feedback_close")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        buttons.addWidget(self.send_button)
        buttons.addWidget(self.close_button)
        buttons.addStretch(1)

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.kind_label)
        layout.addWidget(self.kind_combo)
        layout.addWidget(self.message_label)
        layout.addWidget(self.message_edit)
        layout.addWidget(self.checklist_label)
        layout.addWidget(self.checklist_edit)
        layout.addWidget(self.checklist_help)
        layout.addWidget(self.contact_label)
        layout.addWidget(self.contact_edit)

        footer = QWidget(self)
        footer.setObjectName("FeedbackFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(28, 8, 28, 18)
        footer_layout.setSpacing(8)
        footer_layout.addWidget(self.consent_checkbox)
        footer_layout.addWidget(self.status_label)
        footer_layout.addLayout(buttons)

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)
        outer.addWidget(footer)

        self._prefill_checklist()

    def _prefill_checklist(self) -> None:
        session = self.context.session
        probe = self.context.last_probe or session.probe
        checklist = build_checklist(
            probe,
            session.profile_id,
            session.selected_packages,
            session.verification,
        )
        self.checklist_edit.setPlainText(checklist)
        self.message_edit.setPlaceholderText("")

    # --------------------------------------------------------------- actions

    def send(self) -> None:
        if self._busy:
            return
        message = self.message_edit.toPlainText()
        checklist = self.checklist_edit.toPlainText()
        contact = self.contact_edit.text()
        key = validate_feedback(
            kind=str(self.kind_combo.currentData() or ""),
            message=message,
            checklist=checklist,
            contact=contact,
        )
        if key is not None:
            self._show_status(key, error=True)
            return
        if not self.consent_checkbox.isChecked():
            self._show_status("feedback.consent_required", error=True)
            return
        if not FEEDBACK_ENDPOINT.strip():
            self._show_status("feedback.not_configured", error=True)
            return

        payload = feedback_payload(
            kind=str(self.kind_combo.currentData() or ""),
            message=message,
            checklist=checklist,
            contact=contact,
            app_version=f"CleanYourPhone app {__version__}",
        )
        self._sent = False
        self._set_busy(True)
        self._show_status("feedback.sending")
        if not self._call.start(lambda: send_feedback(payload)):
            self._set_busy(False)
            self._show_status("feedback.failed", error=True)

    def _succeeded(self, result: object) -> None:
        self._sent = True
        self._show_status("feedback.sent")

    def _failed(self, error: object) -> None:
        key = error.key if isinstance(error, FeedbackError) else "feedback.failed"
        self._show_status(key, error=True)

    def _finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (
            self.kind_combo,
            self.message_edit,
            self.checklist_edit,
            self.contact_edit,
            self.consent_checkbox,
            self.send_button,
        ):
            widget.setEnabled(not busy)
        self.send_button.setText(
            self.tr("feedback.sending" if busy else "feedback.send")
        )

    def _show_status(self, key: str, *, error: bool = False) -> None:
        self.status_label.setText(self.tr(key))
        self.status_label.setProperty("role", "error" if error else "success")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.show()

    def closeEvent(self, event) -> None:
        self._call.shutdown(5000)
        super().closeEvent(event)

    # ------------------------------------------------------------ translation

    def tr(self, key: str, **kwargs: object) -> str:
        return self.context.translator.tr(key, **kwargs)

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr("feedback.title"))
        self.title_label.setText(self.tr("feedback.title"))
        self.body_label.setText(self.tr("feedback.body"))
        self.kind_label.setText(self.tr("feedback.kind"))
        self.kind_combo.setItemText(0, self.tr("feedback.kind_feedback"))
        self.kind_combo.setItemText(1, self.tr("feedback.kind_bug"))
        self.kind_combo.setItemText(2, self.tr("feedback.kind_profile"))
        self.message_label.setText(self.tr("feedback.message"))
        self.message_edit.setPlaceholderText(
            self.tr("feedback.message_placeholder")
        )
        self.checklist_label.setText(self.tr("feedback.checklist"))
        self.checklist_help.setText(self.tr("feedback.checklist_help"))
        self.contact_label.setText(self.tr("feedback.contact"))
        self.contact_edit.setPlaceholderText(
            self.tr("feedback.contact_placeholder")
        )
        self.consent_checkbox.setText(self.tr("feedback.consent"))
        self.send_button.setText(self.tr("feedback.send"))
        self.close_button.setText(self.tr("feedback.close"))

        self.title_label.setAccessibleName(self.title_label.text())
        self.body_label.setAccessibleName(self.body_label.text())
        self.kind_combo.setAccessibleName(self.kind_label.text())
        self.message_edit.setAccessibleName(self.message_label.text())
        self.checklist_edit.setAccessibleName(self.checklist_label.text())
        self.contact_edit.setAccessibleName(self.contact_label.text())
        self.consent_checkbox.setAccessibleName(self.consent_checkbox.text())
        self.send_button.setAccessibleName(self.send_button.text())


__all__ = ["FeedbackDialog"]
