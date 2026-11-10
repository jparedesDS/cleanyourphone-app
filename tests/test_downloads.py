import hashlib
import io
import zipfile

import pytest

from cleanyourphone_app.services.downloads import (
    PLATFORM_TOOLS_SHA256,
    PLATFORM_TOOLS_URL,
    PLATFORM_TOOLS_VERSION,
    DownloadCancelled,
    DownloadError,
    PlatformToolsDownloader,
)


def make_zip(*members: tuple[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in members:
            archive.writestr(name, payload)
    return buffer.getvalue()


def downloader_for(payload: bytes, **overrides) -> PlatformToolsDownloader:
    values = {
        "url": "https://example.invalid/tools.zip",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "opener": lambda _: io.BytesIO(payload),
    }
    values.update(overrides)
    return PlatformToolsDownloader(**values)


def test_hash_mismatch_leaves_no_adb(tmp_path):
    downloader = PlatformToolsDownloader(
        url="https://example.invalid/tools.zip",
        sha256="0" * 64,
        opener=lambda _: io.BytesIO(b"not the zip"),
    )
    with pytest.raises(DownloadError):
        downloader.download(tmp_path)
    assert not (tmp_path / "platform-tools" / "adb.exe").exists()


def test_cancel_before_the_fetch_leaves_nothing(tmp_path):
    opened = []

    def opener(url):
        opened.append(url)
        return io.BytesIO(b"archive")

    downloader = PlatformToolsDownloader(
        url="https://example.invalid/tools.zip",
        sha256="0" * 64,
        opener=opener,
    )

    with pytest.raises(DownloadCancelled):
        downloader.download(tmp_path, cancel=lambda: True)

    assert opened == []
    assert not (tmp_path / "platform-tools").exists()


def test_cancel_during_the_fetch_leaves_nothing(tmp_path):
    class CountedResponse:
        def __init__(self):
            self.reads = 0

        def read(self, size):
            self.reads += 1
            return b"archive" if self.reads == 1 else b""

        def close(self):
            pass

    response = CountedResponse()
    downloader = PlatformToolsDownloader(
        url="https://example.invalid/tools.zip",
        sha256="0" * 64,
        opener=lambda _: response,
    )

    with pytest.raises(DownloadCancelled):
        downloader.download(tmp_path, cancel=lambda: response.reads >= 1)

    assert response.reads == 1
    assert not (tmp_path / "platform-tools").exists()


def test_extracts_only_platform_tools(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("platform-tools/adb.exe", b"adb")
        archive.writestr("platform-tools/AdbWinApi.dll", b"dll")
        archive.writestr("stray.txt", b"no")
    payload = buffer.getvalue()
    downloader = PlatformToolsDownloader(
        url="https://example.invalid/tools.zip",
        sha256=hashlib.sha256(payload).hexdigest(),
        opener=lambda _: io.BytesIO(payload),
    )
    result = downloader.download(tmp_path)
    assert result.name == "adb.exe"
    assert (tmp_path / "platform-tools" / "adb.exe").is_file()
    assert not (tmp_path / "platform-tools" / "stray.txt").exists()


def test_network_error_leaves_no_adb(tmp_path):
    downloader = PlatformToolsDownloader(
        url="https://example.invalid/tools.zip",
        sha256="0" * 64,
        opener=lambda _: (_ for _ in ()).throw(OSError("offline")),
    )
    with pytest.raises(DownloadError):
        downloader.download(tmp_path)
    assert not (tmp_path / "platform-tools" / "adb.exe").exists()


def test_platform_tools_constants_are_pinned():
    assert PLATFORM_TOOLS_VERSION == "37.0.1"
    assert (
        PLATFORM_TOOLS_URL
        == "https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip"
    )
    assert (
        PLATFORM_TOOLS_SHA256
        == "45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99"
    )


def test_bad_zip_leaves_no_adb(tmp_path):
    payload = b"this is not a zip archive"
    downloader = downloader_for(payload)
    with pytest.raises(DownloadError):
        downloader.download(tmp_path)
    assert not (tmp_path / "platform-tools").exists()


def test_archive_without_adb_leaves_nothing(tmp_path):
    payload = make_zip(("platform-tools/README.txt", b"readme"))
    downloader = downloader_for(payload)
    with pytest.raises(DownloadError):
        downloader.download(tmp_path)
    assert not (tmp_path / "platform-tools").exists()


def test_path_traversal_member_is_rejected(tmp_path):
    payload = make_zip(
        ("platform-tools/adb.exe", b"adb"),
        ("platform-tools/../evil.txt", b"evil"),
    )
    downloader = downloader_for(payload)
    with pytest.raises(DownloadError):
        downloader.download(tmp_path)
    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "platform-tools" / "adb.exe").exists()


def test_failed_download_removes_a_previously_cached_adb(tmp_path):
    cached = tmp_path / "platform-tools" / "adb.exe"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"old adb")
    downloader = downloader_for(b"payload", sha256="0" * 64)
    with pytest.raises(DownloadError):
        downloader.download(tmp_path)
    assert not cached.exists()


def test_success_replaces_the_previous_platform_tools_tree(tmp_path):
    old_file = tmp_path / "platform-tools" / "old.dll"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    payload = make_zip(("platform-tools/adb.exe", b"adb"))
    downloader = downloader_for(payload)
    result = downloader.download(tmp_path)
    assert result == tmp_path / "platform-tools" / "adb.exe"
    assert result.is_file()
    assert not old_file.exists()
