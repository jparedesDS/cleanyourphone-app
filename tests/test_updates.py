import io
import json

import pytest

from cleanyourphone_app.services.updates import (
    RELEASES_PAGE,
    UpdateCheckError,
    check_for_update,
    is_newer,
    parse_version,
)


def opener(payload: object):
    def _open(_request):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    return _open


def test_parse_version_accepts_a_leading_v():
    assert parse_version("v0.2.2") == (0, 2, 2)
    assert parse_version("0.2.10") == (0, 2, 10)
    assert parse_version("not-a-version") == ()


def test_newer_version_is_detected_numerically():
    assert is_newer("0.2.10", "0.2.9")
    assert is_newer("0.3.0", "0.2.9")
    assert not is_newer("0.2.2", "0.2.2")
    assert not is_newer("0.2.1", "0.2.2")
    assert not is_newer("garbage", "0.2.2")


def test_check_returns_none_when_the_latest_release_is_current():
    payload = {"tag_name": "v0.2.2", "body": "notes"}
    assert check_for_update("0.2.2", opener=opener(payload)) is None
    assert check_for_update("0.2.3", opener=opener(payload)) is None


def test_check_returns_release_information_for_a_newer_version():
    payload = {
        "tag_name": "v0.2.3",
        "body": "A newer build",
        "published_at": "2026-11-11T19:00:00Z",
    }
    info = check_for_update("0.2.2", opener=opener(payload))
    assert info is not None
    assert info.version == "0.2.3"
    assert info.tag == "v0.2.3"
    assert info.notes == "A newer build"
    assert info.url == RELEASES_PAGE


def test_check_rejects_a_malformed_release():
    with pytest.raises(UpdateCheckError):
        check_for_update(
            "0.2.2",
            opener=lambda _request: io.BytesIO(b"{not json"),
        )
    with pytest.raises(UpdateCheckError):
        check_for_update(
            "0.2.2",
            opener=lambda _request: io.BytesIO(b"[]"),
        )


def test_check_reports_a_network_failure():
    def failing(_request):
        raise OSError("offline")

    with pytest.raises(UpdateCheckError):
        check_for_update("0.2.2", opener=failing)
