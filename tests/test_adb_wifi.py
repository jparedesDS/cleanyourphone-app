import subprocess
import traceback
from pathlib import Path

import pytest

from cleanyourphone_app.services.adb import AdbInfo
from cleanyourphone_app.services.adb_wifi import (
    MdnsService,
    MdnsServices,
    WifiConnector,
    WifiError,
    parse_mdns_services,
)

PAIRING = MdnsService("192.168.1.42", 37123)
CONNECT = MdnsService("192.168.1.42", 37099)

MDNS_OUTPUT = (
    "List of discovered mdns services\n"
    "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:37123\n"
    "adb-ABC._adb-tls-connect._tcp.  _adb-tls-connect._tcp.  192.168.1.42:37099\n"
)

DEVICES_OUTPUT = (
    "List of devices attached\n"
    "adb-ABC._adb-tls-connect._tcp.\tdevice product:shiba model:Pixel_8 "
    "device:shiba transport_id:2\n"
)


def make_info(path: Path = Path("adb.exe")) -> AdbInfo:
    return AdbInfo(path=path, version=(37, 0, 1), version_text="Version 37.0.1")


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeRunner:
    """A subprocess.run stand-in that records argv and replays responses."""

    def __init__(self, *responses):
        self.calls = []
        self.kwargs = []
        self._responses = list(responses)

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        self.kwargs.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


# ---------------------------------------------------------------------------
# mDNS parsing
# ---------------------------------------------------------------------------


def test_parse_mdns_services():
    output = (
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:37123\n"
        "adb-ABC._adb-tls-connect._tcp.  _adb-tls-connect._tcp.  192.168.1.42:37099\n"
    )
    services = parse_mdns_services(output)
    assert services.pairing == MdnsService("192.168.1.42", 37123)
    assert services.connect == MdnsService("192.168.1.42", 37099)


def test_parse_mdns_services_with_only_a_pairing_service():
    services = parse_mdns_services(
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:37123\n"
    )
    assert services.pairing == PAIRING
    assert services.connect is None


def test_parse_mdns_services_with_only_a_connect_service():
    services = parse_mdns_services(
        "adb-ABC._adb-tls-connect._tcp.  _adb-tls-connect._tcp.  192.168.1.42:37099\n"
    )
    assert services.pairing is None
    assert services.connect == CONNECT


def test_parse_mdns_services_with_no_services():
    assert parse_mdns_services("") == MdnsServices()
    assert parse_mdns_services("List of discovered mdns services\n") == MdnsServices()


def test_parse_mdns_services_ignores_malformed_lines():
    output = (
        "List of discovered mdns services\n"
        "* daemon not running; starting now at tcp:5037\n"
        "adb: no mdns services found\n"
        "garbage\n"
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.\n"
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42\n"
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:notaport\n"
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:99999\n"
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  :37123\n"
        "adb-ABC._adb-tls-connect._tcp.  _adb-tls-connect._tcp.  192.168.1.42:37099\n"
    )
    services = parse_mdns_services(output)
    assert services.pairing is None
    assert services.connect == CONNECT


def test_parse_mdns_services_keeps_the_last_valid_service():
    output = (
        "adb-OLD._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.10:30000\n"
        "adb-ABC._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:37123\n"
        "adb-BAD._adb-tls-pairing._tcp.  _adb-tls-pairing._tcp.  192.168.1.42:bad\n"
    )
    services = parse_mdns_services(output)
    assert services.pairing == PAIRING


def test_parse_mdns_services_requires_text():
    with pytest.raises(ValueError):
        parse_mdns_services(None)


def test_mdns_service_stringifies_as_host_and_port():
    assert str(PAIRING) == "192.168.1.42:37123"


# ---------------------------------------------------------------------------
# Connector construction and discovery
# ---------------------------------------------------------------------------


def test_wifi_connector_rejects_a_raw_path_without_running_adb(tmp_path):
    fake = tmp_path / "adb.exe"
    fake.write_text("")
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        raise AssertionError("adb must not run for an unverified path")

    with pytest.raises(TypeError):
        WifiConnector(fake, runner=runner)
    assert calls == []


def test_wifi_connector_rejects_an_outdated_adb_info_without_running_adb():
    outdated = AdbInfo(
        path=Path("adb.exe"),
        version=(30, 0, 0),
        version_text="Version 30.0.0",
    )
    calls = []
    with pytest.raises(ValueError):
        WifiConnector(outdated, runner=lambda args, **kwargs: calls.append(args))
    assert calls == []


def test_discover_runs_mdns_services_and_parses_the_result():
    runner = FakeRunner(completed(stdout=MDNS_OUTPUT))
    info = make_info(Path("C:/tools/adb.exe"))
    connector = WifiConnector(info, runner=runner)

    services = connector.discover()

    assert services == MdnsServices(pairing=PAIRING, connect=CONNECT)
    assert runner.calls == [[str(info.path), "mdns", "services"]]


def test_discover_failure_raises_wifi_error_with_a_clear_next_step():
    runner = FakeRunner(completed(returncode=1, stderr="adb: mdns not supported\n"))
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.discover()

    message = str(excinfo.value).lower()
    assert "wireless debugging" in message
    assert "usb" in message


def test_discover_with_no_services_returns_an_empty_result():
    runner = FakeRunner(completed(stdout="List of discovered mdns services\n"))
    connector = WifiConnector(make_info(), runner=runner)

    assert connector.discover() == MdnsServices()


def test_connector_runs_adb_without_a_console_window():
    runner = FakeRunner(completed(stdout=MDNS_OUTPUT))
    connector = WifiConnector(make_info(), runner=runner)

    connector.discover()

    kwargs = runner.kwargs[0]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["timeout"] > 0
    assert kwargs["check"] is False
    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW


# ---------------------------------------------------------------------------
# Pairing and connecting
# ---------------------------------------------------------------------------


def test_pair_and_connect_runs_the_exact_commands_and_returns_the_serial():
    runner = FakeRunner(
        completed(stdout="Successfully paired to 192.168.1.42:37123\n"),
        completed(stdout="connected to 192.168.1.42:37099\n"),
        completed(stdout=DEVICES_OUTPUT),
    )
    info = make_info(Path("C:/tools/adb.exe"))
    connector = WifiConnector(info, runner=runner)

    serial = connector.pair_and_connect("123456", PAIRING, CONNECT)

    assert serial == "adb-ABC._adb-tls-connect._tcp."
    assert runner.calls == [
        [str(info.path), "pair", "192.168.1.42:37123", "123456"],
        [str(info.path), "connect", "192.168.1.42:37099"],
        [str(info.path), "devices", "-l"],
    ]


def test_pair_and_connect_returns_a_host_port_serial():
    devices = (
        "List of devices attached\n"
        "emulator-5554  device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64\n"
        "192.168.1.42:37099  device product:shiba model:Pixel_8 transport_id:3\n"
    )
    runner = FakeRunner(
        completed(),
        completed(stdout="connected to 192.168.1.42:37099\n"),
        completed(stdout=devices),
    )
    connector = WifiConnector(make_info(), runner=runner)

    assert connector.pair_and_connect("123456", PAIRING, CONNECT) == (
        "192.168.1.42:37099"
    )


def test_pair_and_connect_prefers_the_only_wifi_device():
    devices = (
        "List of devices attached\n"
        "R58M12345  device product:shiba model:Pixel_8 transport_id:1\n"
        "adb-ABC._adb-tls-connect._tcp.\tdevice product:shiba model:Pixel_8\n"
    )
    runner = FakeRunner(
        completed(),
        completed(stdout="connected to 192.168.1.42:37099\n"),
        completed(stdout=devices),
    )
    connector = WifiConnector(make_info(), runner=runner)

    assert connector.pair_and_connect("123456", PAIRING, CONNECT) == (
        "adb-ABC._adb-tls-connect._tcp."
    )


@pytest.mark.parametrize(
    "code",
    ["12345", "1234567", "12345a", "123 456", "", "１２３４５６"],
)
def test_pair_and_connect_rejects_codes_that_are_not_six_digits(code):
    runner = FakeRunner()
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(ValueError) as excinfo:
        connector.pair_and_connect(code, PAIRING, CONNECT)

    assert runner.calls == []
    if code:
        assert code not in str(excinfo.value)


def test_pair_and_connect_rejects_a_non_text_code():
    runner = FakeRunner()
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(ValueError):
        connector.pair_and_connect(123456, PAIRING, CONNECT)

    assert runner.calls == []


def test_a_failed_pair_raises_wifi_error_with_the_phone_side_retry_step():
    runner = FakeRunner(
        completed(
            returncode=1,
            stdout="Failed: Wrong password or connection was dropped.\n",
        )
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    message = str(excinfo.value).lower()
    assert "wireless debugging" in message
    assert "pairing code" in message
    assert "try again" in message
    assert "123456" not in message
    assert runner.calls == [
        [str(make_info().path), "pair", "192.168.1.42:37123", "123456"]
    ]


def test_pair_that_prints_a_failure_with_exit_code_zero_is_an_error():
    runner = FakeRunner(completed(stdout="Failed: Wrong password.\n"))
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    assert "123456" not in str(excinfo.value)
    assert len(runner.calls) == 1


def test_a_failed_pair_never_puts_the_code_in_the_exception():
    runner = FakeRunner(
        completed(
            returncode=1,
            stdout="Failed for code 123456\n",
            stderr="rejected code 123456\n",
        )
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    assert "123456" not in str(excinfo.value)
    assert "<pairing-code>" in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    formatted = "".join(traceback.format_exception_only(excinfo.value))
    assert "123456" not in formatted


def test_a_pair_launch_failure_never_puts_the_code_in_the_exception():
    runner = FakeRunner(OSError("could not start adb for 123456"))
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    assert "123456" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    formatted = "".join(traceback.format_exception_only(excinfo.value))
    assert "123456" not in formatted


def test_a_pair_timeout_never_puts_the_code_in_the_exception():
    runner = FakeRunner(
        subprocess.TimeoutExpired(["adb", "pair", "192.168.1.42:37123", "123456"], 60)
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    message = str(excinfo.value).lower()
    assert "timed out" in message
    assert "123456" not in message
    assert excinfo.value.__cause__ is None
    formatted = "".join(traceback.format_exception_only(excinfo.value))
    assert "123456" not in formatted


def test_a_failed_connect_raises_wifi_error_with_the_usb_fallback():
    runner = FakeRunner(
        completed(),
        completed(returncode=1, stderr="failed to connect: timeout\n"),
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    message = str(excinfo.value).lower()
    assert "same wi-fi" in message
    assert "usb" in message
    assert "123456" not in message


def test_connect_that_prints_a_failure_with_exit_code_zero_is_an_error():
    runner = FakeRunner(
        completed(),
        completed(
            stdout="failed to connect to '192.168.1.42:37099': Connection refused\n"
        ),
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError):
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    assert len(runner.calls) == 2


def test_connect_that_already_is_connected_is_accepted():
    runner = FakeRunner(
        completed(),
        completed(stdout="already connected to 192.168.1.42:37099\n"),
        completed(stdout=DEVICES_OUTPUT),
    )
    connector = WifiConnector(make_info(), runner=runner)

    assert connector.pair_and_connect("123456", PAIRING, CONNECT) == (
        "adb-ABC._adb-tls-connect._tcp."
    )


def test_no_connected_device_after_connect_raises_wifi_error():
    runner = FakeRunner(
        completed(),
        completed(stdout="connected to 192.168.1.42:37099\n"),
        completed(
            stdout="List of devices attached\n192.168.1.42:37099\tunauthorized\n"
        ),
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    message = str(excinfo.value).lower()
    assert "wireless debugging" in message
    assert "usb" in message


def test_ambiguous_devices_after_connect_raise_wifi_error():
    devices = (
        "List of devices attached\n"
        "R58M12345  device product:shiba model:Pixel_8 transport_id:1\n"
        "R58M67890  device product:shiba model:Pixel_7 transport_id:2\n"
    )
    runner = FakeRunner(
        completed(),
        completed(stdout="connected to 192.168.1.42:37099\n"),
        completed(stdout=devices),
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    message = str(excinfo.value).lower()
    assert "exactly one" in message
    assert "usb" in message


def test_a_failed_devices_call_raises_wifi_error():
    runner = FakeRunner(
        completed(),
        completed(stdout="connected to 192.168.1.42:37099\n"),
        completed(returncode=1, stderr="adb: device offline\n"),
    )
    connector = WifiConnector(make_info(), runner=runner)

    with pytest.raises(WifiError) as excinfo:
        connector.pair_and_connect("123456", PAIRING, CONNECT)

    assert "usb" in str(excinfo.value).lower()
