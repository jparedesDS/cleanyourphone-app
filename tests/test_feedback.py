"""Feedback payload, checklist and opt-in HTTP client."""

import json
import urllib.error
from unittest import mock

import pytest

from cleanyourphone_app.domain.feedback import (
    FeedbackPayload,
    build_checklist,
    feedback_payload,
    validate_feedback,
)
from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.services.feedback import FeedbackError, send_feedback


def probe(**overrides) -> ProbeData:
    fields = {
        "brand": "OnePlus",
        "model": "ONEPLUS A6013",
        "device": "OnePlus6T",
        "android": "11",
        "sdk": 30,
        "build": "ONEPLUS A6013_41_211125",
        "fingerprint": (
            "OnePlus/OnePlus6T/OnePlus6T:11/RKQ1.201217.002/2111252327:"
            "user/release-keys"
        ),
        "managed": False,
        "users": 1,
        "is_tv": False,
        "battery": {"level": 80},
        "profiles": ("oneplus-a6013",),
        "auto_apply_profiles": ("oneplus-a6013",),
    }
    fields.update(overrides)
    return ProbeData(**fields)


def test_checklist_has_build_and_profile_but_no_device_identifiers():
    text = build_checklist(
        probe(),
        "oneplus-a6013",
        ("com.oneplus.wallpaper",),
        "device",
    )

    assert "OnePlus ONEPLUS A6013" in text
    assert "Android: 11 (SDK 30)" in text
    assert "Build: ONEPLUS A6013_41_211125" in text
    assert "Fingerprint: OnePlus/OnePlus6T" in text
    assert "Profile: oneplus-a6013" in text
    assert "com.oneplus.wallpaper" in text
    assert "serial" not in text.lower()
    assert "192.168" not in text


def test_checklist_without_a_phone_is_a_template():
    text = build_checklist(None)
    assert "Phone: (not connected)" in text
    assert "Build:" in text


def test_validation_requires_a_message_or_checklist():
    assert (
        validate_feedback(
            kind="feedback", message="", checklist="", contact=""
        )
        == "feedback.empty"
    )


def test_validation_rejects_unknown_kind_and_long_fields():
    assert (
        validate_feedback(
            kind="other", message="hello", checklist="", contact=""
        )
        == "feedback.invalid_kind"
    )
    assert (
        validate_feedback(
            kind="feedback", message="x" * 4001, checklist="", contact=""
        )
        == "feedback.message_too_long"
    )
    assert (
        validate_feedback(
            kind="feedback", message="", checklist="x" * 6001, contact=""
        )
        == "feedback.checklist_too_long"
    )
    assert (
        validate_feedback(
            kind="feedback",
            message="hello",
            checklist="",
            contact="x" * 201,
        )
        == "feedback.contact_too_long"
    )


def test_payload_is_sent_as_json_to_the_worker():
    response = mock.MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b'{"ok":true}'
    payload = feedback_payload(
        kind="feedback",
        message="Please improve the review copy",
        checklist="Phone: Test",
        contact="tester",
        app_version="CleanYourPhone app test",
    )
    with mock.patch(
        "cleanyourphone_app.services.feedback.urllib.request.urlopen",
        return_value=response,
    ) as urlopen:
        send_feedback(payload, endpoint="https://feedback.test")

    request = urlopen.call_args.args[0]
    assert request.full_url == "https://feedback.test"
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8"))["message"].startswith(
        "Please improve"
    )
    assert json.loads(request.data.decode("utf-8"))["website"] == ""


def test_empty_endpoint_is_not_configured():
    with pytest.raises(FeedbackError) as error:
        send_feedback(
            FeedbackPayload(kind="feedback", message="hello", checklist=""),
            endpoint="",
        )
    assert error.value.key == "feedback.not_configured"


def test_http_429_becomes_rate_limited():
    error = urllib.error.HTTPError(
        "https://feedback.test", 429, "too many", hdrs=None, fp=None
    )
    with mock.patch(
        "cleanyourphone_app.services.feedback.urllib.request.urlopen",
        side_effect=error,
    ):
        with pytest.raises(FeedbackError) as raised:
            send_feedback(
                FeedbackPayload(
                    kind="feedback", message="hello", checklist=""
                ),
                endpoint="https://feedback.test",
            )
    assert raised.value.key == "feedback.rate_limited"
