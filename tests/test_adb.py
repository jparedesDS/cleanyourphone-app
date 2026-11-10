from pathlib import Path

import pytest

from cleanyourphone_app.services.adb import (
    MIN_ADB_VERSION,
    AdbError,
    AdbLocator,
    DeviceEntry,
    list_devices,
    parse_adb_version,
)

DEVICES_OUTPUT = """List of devices attached
R58M12345              device usb:1-1 product:shiba model:Pixel_8 device:shiba transport_id:1
adb-ABC123-xyz._adb-tls-connect._tcp.   device product:shiba model:Pixel_8 device:shiba transport_id:2
192.168.1.20:5555      offline transport_id:3
emulator-5554          device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64xa transport_id:4
* daemon not running; starting now at tcp:5037
"""


def make_adb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_parse_adb_version():
    output = "Android Debug Bridge version 1.0.41\nVersion 37.0.1-15733141\n"
    assert parse_adb_version(output) == (37, 0, 1)


def test_old_adb_is_not_suitable(tmp_path):
    fake = tmp_path / "adb.exe"
    fake.write_text("")
    locator = AdbLocator(version_runner=lambda _: (30, 0, 0))
    assert locator.accept(fake) is None


def test_env_adb_wins(tmp_path, monkeypatch):
    fake = tmp_path / "adb.exe"
    fake.write_text("")
    monkeypatch.setenv("ADB", str(fake))
    locator = AdbLocator(version_runner=lambda _: (37, 0, 1))
    assert locator.find().path == fake


def test_minimum_version_is_accepted(tmp_path):
    fake = make_adb(tmp_path / "adb.exe")
    locator = AdbLocator(version_runner=lambda _: MIN_ADB_VERSION)
    info = locator.accept(fake)
    assert info is not None
    assert info.path == fake
    assert info.version == MIN_ADB_VERSION


def test_missing_file_is_not_accepted_and_is_not_run(tmp_path):
    calls = []
    locator = AdbLocator(version_runner=lambda path: calls.append(path) or (37, 0, 1))
    assert locator.accept(tmp_path / "missing" / "adb.exe") is None
    assert calls == []


def test_version_runner_failure_is_not_accepted(tmp_path):
    fake = make_adb(tmp_path / "adb.exe")

    def broken(_):
        raise OSError("adb exploded")

    locator = AdbLocator(version_runner=broken)
    assert locator.accept(fake) is None


def test_parse_adb_version_rejects_output_without_a_version():
    with pytest.raises(ValueError):
        parse_adb_version("adb: no devices/emulators found")


def test_path_adb_is_found(tmp_path, monkeypatch):
    fake = make_adb(tmp_path / "adb.exe")
    monkeypatch.delenv("ADB", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    locator = AdbLocator(
        version_runner=lambda _: (37, 0, 1),
        cache_dir=tmp_path / "cache",
        local_app_data=tmp_path / "local",
    )
    assert locator.find().path == fake


def test_sdk_adb_is_found_after_path(tmp_path, monkeypatch):
    sdk_adb = make_adb(
        tmp_path / "local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    )
    monkeypatch.delenv("ADB", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    locator = AdbLocator(
        version_runner=lambda _: (37, 0, 1),
        cache_dir=tmp_path / "cache",
        local_app_data=tmp_path / "local",
    )
    assert locator.find().path == sdk_adb


def test_cache_adb_is_the_last_fallback(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cached_adb = make_adb(cache / "platform-tools" / "adb.exe")
    monkeypatch.delenv("ADB", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    locator = AdbLocator(
        version_runner=lambda _: (37, 0, 1),
        cache_dir=cache,
        local_app_data=tmp_path / "local",
    )
    assert locator.find().path == cached_adb


def test_old_env_adb_falls_through_to_path(tmp_path, monkeypatch):
    old_adb = make_adb(tmp_path / "old" / "adb.exe")
    good_adb = make_adb(tmp_path / "bin" / "adb.exe")
    monkeypatch.setenv("ADB", str(old_adb))
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    versions = {old_adb: (30, 0, 0), good_adb: (37, 0, 1)}
    locator = AdbLocator(
        version_runner=lambda path: versions[Path(path)],
        cache_dir=tmp_path / "cache",
        local_app_data=tmp_path / "local",
    )
    assert locator.find().path == good_adb


def test_nothing_found_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("ADB", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    locator = AdbLocator(
        version_runner=lambda _: (37, 0, 1),
        cache_dir=tmp_path / "cache",
        local_app_data=tmp_path / "local",
    )
    assert locator.find() is None


def test_cache_dir_defaults_under_local_app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    locator = AdbLocator(version_runner=lambda _: (37, 0, 1))
    assert locator.cache_dir == tmp_path / "local" / "CleanYourPhone"


def test_list_devices_parses_serial_state_model_and_transport():
    devices = list_devices(Path("adb.exe"), runner=lambda _: DEVICES_OUTPUT)
    assert [device.serial for device in devices] == [
        "R58M12345",
        "adb-ABC123-xyz._adb-tls-connect._tcp.",
        "192.168.1.20:5555",
        "emulator-5554",
    ]
    assert devices[0] == DeviceEntry(
        serial="R58M12345",
        state="device",
        model="Pixel_8",
        transport="usb",
    )
    assert devices[1].transport == "wifi"
    assert devices[2].state == "offline"
    assert devices[2].model == ""
    assert devices[2].transport == "wifi"
    assert devices[3].transport == "usb"


def test_list_devices_passes_the_adb_path_to_the_runner():
    seen = []

    def runner(path):
        seen.append(path)
        return "List of devices attached\n"

    assert list_devices(Path("C:/tools/adb.exe"), runner=runner) == []
    assert seen == [Path("C:/tools/adb.exe")]


def test_list_devices_ignores_daemon_and_error_lines():
    output = (
        "List of devices attached\n"
        "* daemon not running; starting now at tcp:5037\n"
        "adb: no devices/emulators found\n"
    )
    assert list_devices(Path("adb.exe"), runner=lambda _: output) == []


def test_list_devices_wraps_runner_failures():
    def offline(_):
        raise OSError("offline")

    with pytest.raises(AdbError):
        list_devices(Path("adb.exe"), runner=offline)
