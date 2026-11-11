import hashlib
import io
import json

import pytest

from cleanyourphone_app.services.updates import (
    RELEASES_PAGE,
    UpdateCancelled,
    UpdateCheckError,
    UpdateInfo,
    UpdateInstallError,
    check_for_update,
    download_update,
    is_newer,
    launch_update_helper,
    parse_version,
)

INSTALLER = b"verified installer bytes"
SHA256 = hashlib.sha256(INSTALLER).hexdigest()
DOWNLOAD_URL = (
    "https://github.com/jparedesDS/cleanyourphone-app/releases/download/"
    "v0.2.3/CleanYourPhone-Setup-0.2.3.exe"
)


def opener(payload: object):
    def _open(_request):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    return _open


def binary(data: bytes):
    def _open(_url):
        return io.BytesIO(data)

    return _open


def release_payload(*, with_sha: bool = True) -> dict:
    body = "A newer build"
    if with_sha:
        body += f"\n\nSHA-256: {SHA256.upper()}"
    return {
        "tag_name": "v0.2.3",
        "body": body,
        "published_at": "2026-11-11T19:00:00Z",
        "assets": [
            {
                "name": "CleanYourPhone-Setup-0.2.3.exe",
                "browser_download_url": DOWNLOAD_URL,
                "size": len(INSTALLER),
            }
        ],
    }


def install_info() -> UpdateInfo:
    return UpdateInfo(
        version="0.2.3",
        tag="v0.2.3",
        installer_url=DOWNLOAD_URL,
        sha256=SHA256,
        size=len(INSTALLER),
    )


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
    info = check_for_update("0.2.2", opener=opener(release_payload()))
    assert info is not None
    assert info.version == "0.2.3"
    assert info.tag == "v0.2.3"
    assert info.notes.startswith("A newer build")
    assert info.url == RELEASES_PAGE


def test_check_offers_a_verified_installer():
    info = check_for_update("0.2.2", opener=opener(release_payload()))
    assert info is not None
    assert info.can_install
    assert info.installer_url == DOWNLOAD_URL
    assert info.sha256 == SHA256
    assert info.size == len(INSTALLER)


def test_check_does_not_offer_install_without_a_checksum():
    info = check_for_update(
        "0.2.2", opener=opener(release_payload(with_sha=False))
    )
    assert info is not None
    assert not info.can_install
    assert info.installer_url is None


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


def test_download_update_verifies_the_installer(tmp_path):
    path = download_update(install_info(), tmp_path, opener=binary(INSTALLER))
    assert path == tmp_path / "CleanYourPhone-Setup-0.2.3.exe"
    assert path.read_bytes() == INSTALLER
    assert not path.with_suffix(".exe.part").exists()


def test_download_update_rejects_a_bad_hash(tmp_path):
    info = UpdateInfo(
        version="0.2.3",
        tag="v0.2.3",
        installer_url=DOWNLOAD_URL,
        sha256="0" * 64,
        size=len(INSTALLER),
    )
    with pytest.raises(UpdateInstallError):
        download_update(info, tmp_path, opener=binary(INSTALLER))
    assert not (tmp_path / "CleanYourPhone-Setup-0.2.3.exe").exists()
    assert not (tmp_path / "CleanYourPhone-Setup-0.2.3.exe.part").exists()


def test_download_update_can_be_cancelled(tmp_path):
    with pytest.raises(UpdateCancelled):
        download_update(
            install_info(),
            tmp_path,
            opener=binary(INSTALLER),
            cancel=lambda: True,
        )
    assert not (tmp_path / "CleanYourPhone-Setup-0.2.3.exe").exists()


def test_update_helper_waits_and_runs_the_installer_silently(tmp_path):
    installer = tmp_path / "CleanYourPhone-Setup-0.2.3.exe"
    installer.write_bytes(b"installer")
    app = tmp_path / "CleanYourPhone.exe"
    app.write_bytes(b"app")
    calls = []

    def starter(args, **kwargs):
        calls.append((args, kwargs))

    helper = launch_update_helper(
        installer,
        app,
        pid=4321,
        directory=tmp_path,
        starter=starter,
    )

    assert helper.is_file()
    script = helper.read_text(encoding="utf-8")
    assert "PID eq 4321" in script
    assert "/VERYSILENT" in script
    assert str(installer) in script
    assert str(app) in script
    assert calls
    assert calls[0][0][:2] == ["cmd.exe", "/c"]
