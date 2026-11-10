"""The feedback dialog sends only after consent and never at startup."""

from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.i18n.translator import Translator
from cleanyourphone_app.services.feedback import FeedbackError
from cleanyourphone_app.ui.app import AppContext
from cleanyourphone_app.ui.dialogs import feedback as feedback_dialog
from cleanyourphone_app.ui.dialogs.feedback import FeedbackDialog
from cleanyourphone_app.ui.main_window import MainWindow


def probe() -> ProbeData:
    return ProbeData(
        brand="OnePlus",
        model="ONEPLUS A6013",
        device="OnePlus6T",
        android="11",
        sdk=30,
        build="ONEPLUS A6013_41_211125",
        fingerprint=(
            "OnePlus/OnePlus6T/OnePlus6T:11/RKQ1.201217.002/2111252327:"
            "user/release-keys"
        ),
        managed=False,
        users=1,
        is_tv=False,
        battery={"level": 80},
        profiles=("oneplus-a6013",),
        auto_apply_profiles=("oneplus-a6013",),
    )


def make_context() -> AppContext:
    context = AppContext.fake(translator=Translator("en"))
    context.last_probe = probe()
    return context


def test_dialog_prefills_a_checklist_and_requires_consent(qtbot):
    dialog = FeedbackDialog(make_context())
    qtbot.addWidget(dialog)

    assert "ONEPLUS A6013" in dialog.checklist_edit.toPlainText()
    assert dialog.send_button.text() == "Send"

    dialog.message_edit.setPlainText("Please improve this screen")
    dialog.send_button.click()

    assert dialog.status_label.text() == "Tick the consent box before sending."
    assert dialog._busy is False


def test_dialog_requires_a_message_or_checklist(qtbot):
    dialog = FeedbackDialog(make_context())
    qtbot.addWidget(dialog)
    dialog.checklist_edit.clear()
    dialog.consent_checkbox.setChecked(True)

    dialog.send_button.click()

    assert dialog.status_label.text() == "Write a message or a checklist."
    assert dialog._busy is False


def test_dialog_sends_the_payload_after_consent(qtbot, monkeypatch):
    sent = []

    def fake_send(payload):
        sent.append(payload)

    monkeypatch.setattr(feedback_dialog, "send_feedback", fake_send)
    dialog = FeedbackDialog(make_context())
    qtbot.addWidget(dialog)
    dialog.message_edit.setPlainText("The review page could explain more")
    dialog.consent_checkbox.setChecked(True)
    dialog.send_button.click()

    qtbot.waitUntil(lambda: dialog._busy is False, timeout=3000)
    assert len(sent) == 1
    assert sent[0].message.startswith("The review page")
    assert "ONEPLUS A6013" in sent[0].checklist
    assert "CleanYourPhone app" in sent[0].app_version
    assert dialog.status_label.text() == "Sent. Thanks for helping."


def test_dialog_shows_a_rate_limit_error(qtbot, monkeypatch):
    def fail(_payload):
        raise FeedbackError("feedback.rate_limited")

    monkeypatch.setattr(feedback_dialog, "send_feedback", fail)
    dialog = FeedbackDialog(make_context())
    qtbot.addWidget(dialog)
    dialog.message_edit.setPlainText("Test")
    dialog.consent_checkbox.setChecked(True)
    dialog.send_button.click()

    qtbot.waitUntil(lambda: dialog._busy is False, timeout=3000)
    assert dialog.status_label.text() == (
        "Please wait a few minutes before sending again."
    )


def test_header_has_a_feedback_button(qtbot):
    window = MainWindow(AppContext.fake(translator=Translator("en")))
    qtbot.addWidget(window)
    assert window.feedback_button.text() == "Feedback"
    assert window.feedback_button.isEnabled() is True
