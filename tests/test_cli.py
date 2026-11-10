import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cleanyourphone_app.services import cli as cli_module
from cleanyourphone_app.services.cli import (
    CliClient,
    CliError,
    CliProtocolError,
    CliResult,
)

FAKE_CLI = Path(__file__).parent / "fakes" / "fake_cli.py"


class FakeCliLog:
    """Read the JSON-lines log written by the fake sidecar."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def last_record(self) -> dict:
        entries = self.entries()
        assert entries, "the fake CLI was not invoked"
        return entries[-1]

    def last_args(self) -> list[str]:
        return self.last_record()["args"]

    def last_env(self) -> dict:
        return self.last_record()["env"]


@pytest.fixture
def fake_log(tmp_path: Path) -> FakeCliLog:
    return FakeCliLog(tmp_path / "fake-cli.log")


@pytest.fixture
def base_env(fake_log: FakeCliLog, tmp_path: Path) -> dict[str, str]:
    return {
        "FAKE_CLI_LOG": str(fake_log.path),
        "ADB": str(tmp_path / "platform-tools" / "adb.exe"),
        "CLEANYOURPHONE_PROFILES": str(tmp_path / "profiles"),
    }


def make_client(base_env: dict[str, str], **overrides: str) -> CliClient:
    return CliClient(
        [sys.executable, str(FAKE_CLI)],
        env={**base_env, **overrides},
    )


@pytest.fixture
def client(base_env: dict[str, str]) -> CliClient:
    return make_client(base_env)


def test_serial_is_prepended_to_device_commands(client, fake_log):
    client.set_serial("192.0.2.10:5555")
    client.probe()
    assert fake_log.last_args() == [
        "--serial",
        "192.0.2.10:5555",
        "--json",
        "probe",
    ]


def test_serial_can_be_cleared_and_is_validated(client):
    client.set_serial("192.0.2.10:5555")
    assert client.serial == "192.0.2.10:5555"
    client.set_serial(None)
    assert client.serial is None
    with pytest.raises(ValueError):
        client.set_serial("  ")
    with pytest.raises(ValueError):
        client.set_serial("two words")


def probe_payload(**overrides):
    payload = {
        "serial": "not-stored",
        "brand": "Google",
        "manufacturer": "Google",
        "model": "Pixel 8",
        "device": "shiba",
        "android": "14",
        "sdk": 34,
        "build": "AP1A.240505.004",
        "fingerprint": "google/shiba/shiba:14/AP1A.240505.004/11228896:user/release-keys",
        "managed": False,
        "users": 1,
        "is_tv": False,
        "battery": {"level": 80},
        "profiles": ["pixel-8"],
        "documented_profiles": [],
        "auto_apply_profiles": ["pixel-8"],
        "reference_profiles": [],
    }
    payload.update(overrides)
    return payload


def plan_payload(**overrides):
    payload = {
        "profile": {"id": "pixel-8", "brand": "Google", "model": "Pixel 8"},
        "match": True,
        "verification": "device",
        "auto_apply": True,
        "rows": [
            {
                "action": "DISABLE",
                "package": "com.google.android.apps.wellbeing",
                "why": "unused",
                "breaks": "Digital Wellbeing",
                "section": "disable",
                "reason": "",
            }
        ],
    }
    payload.update(overrides)
    return payload


def dns_check_payload(**overrides):
    payload = {
        "ad_domain": "doubleclick.net",
        "ad_ip": "0.0.0.0",
        "ad_state": "blocked",
        "ad_blocked": True,
        "control_domain": "wikipedia.org",
        "control_ip": "203.0.113.7",
        "control_state": "ok",
        "online": True,
    }
    payload.update(overrides)
    return payload


def bench_data_payload(**overrides):
    payload = {
        "timestamp": "2026-11-10 10:00:00",
        "model": "Google Pixel 8",
        "android": "14",
        "build": "AP1A.240505.004",
        "ram_available_mb": 2048,
        "swap_used_mb": 512,
        "processes": 320,
        "packages_installed": 210,
        "packages_enabled": 200,
        "packages_disabled": 10,
        "packages_system": 150,
        "packages_user": 60,
        "animation_window": 1.0,
        "animation_transition": 1.0,
        "animation_duration": 1.0,
        "peak_refresh_rate": 120.0,
        "private_dns_mode": "hostname",
        "private_dns_specifier": "dns.adguard-dns.com",
        "battery_saver": False,
    }
    payload.update(overrides)
    return payload


def test_probe_uses_the_top_level_json_flag(client, fake_log):
    probe = client.probe()
    assert probe.model == "Pixel 8"
    assert fake_log.last_args() == ["--json", "probe"]


def test_probe_reads_the_typed_fields(client):
    probe = client.probe()
    assert probe.brand == "Google"
    assert probe.sdk == 34
    assert probe.managed is False
    assert probe.users == 1
    assert probe.is_tv is False
    assert probe.profiles == ("pixel-8",)
    assert probe.auto_apply_profiles == ("pixel-8",)


def test_plan_parses_rows(client, fake_log):
    plan = client.plan("pixel-8")
    assert plan.rows[0].action == "DISABLE"
    assert plan.rows[0].package == "com.google.android.apps.wellbeing"
    assert fake_log.last_args() == ["--json", "plan", "--profile", "pixel-8"]


def test_disable_refuses_more_than_five_packages(client, fake_log):
    with pytest.raises(ValueError):
        client.disable(["a", "b", "c", "d", "e", "f"])
    assert fake_log.entries() == []


def test_disable_passes_the_packages_to_the_cli(client, fake_log):
    result = client.disable(["a", "b"])
    assert result.returncode == 0
    assert fake_log.last_args() == ["disable", "a", "b"]


def test_disable_rejects_a_non_string_package(base_env, fake_log):
    client = make_client(base_env)
    with pytest.raises(ValueError):
        client.disable([None])
    assert fake_log.entries() == []


def test_non_zero_disable_returns_a_result_without_raising(base_env):
    client = make_client(base_env, FAKE_CLI_DISABLE_EXIT="1")
    result = client.disable(["a"])
    assert isinstance(result, CliResult)
    assert result.returncode == 1
    assert result.ok is False


def test_list_disabled_returns_package_ids(client, fake_log):
    assert client.list_disabled() == {"com.example.disabled", "com.example.other"}
    assert fake_log.last_args() == ["--json", "list", "--state", "disabled"]


def test_list_disabled_accepts_a_custom_disabled_set(base_env):
    client = make_client(base_env, FAKE_CLI_DISABLED="com.example.one,com.example.two")
    assert client.list_disabled() == {"com.example.one", "com.example.two"}


def test_verify_uses_the_top_level_json_flag_and_returns_checks(client, fake_log):
    verify = client.verify()
    assert fake_log.last_args() == ["--json", "verify"]
    assert verify["checks"][0]["check"] == "Device"
    assert verify["checks"][1]["status"] == "PASS"


def test_verify_rejects_an_empty_check_list(base_env):
    client = make_client(base_env, FAKE_CLI_VERIFY_JSON="[]")
    with pytest.raises(CliProtocolError, match="no checks"):
        client.verify()


def test_verify_returns_checks_when_the_sidecar_reports_a_failure(base_env):
    payload = json.dumps(
        [{"check": "Home", "status": "FAIL", "detail": "no enabled Home app"}]
    )
    client = make_client(
        base_env,
        FAKE_CLI_VERIFY_EXIT="1",
        FAKE_CLI_VERIFY_JSON=payload,
    )
    verify = client.verify()
    assert verify == {
        "checks": [
            {"check": "Home", "status": "FAIL", "detail": "no enabled Home app"}
        ]
    }


def test_verify_rejects_an_exit_code_above_one(base_env):
    client = make_client(base_env, FAKE_CLI_VERIFY_EXIT="2")
    with pytest.raises(CliProtocolError, match="exited with 2"):
        client.verify()


def test_dns_set_uses_the_preset_argument(client, fake_log):
    result = client.dns_set("adguard")
    assert isinstance(result, CliResult)
    assert result.returncode == 0
    assert fake_log.last_args() == ["dns", "set", "adguard"]


def test_dns_set_rejects_an_empty_provider(client, fake_log):
    with pytest.raises(ValueError):
        client.dns_set("   ")
    assert fake_log.entries() == []


def test_dns_off_returns_the_cli_result(client, fake_log):
    result = client.dns_off()
    assert isinstance(result, CliResult)
    assert result.returncode == 0
    assert fake_log.last_args() == ["dns", "off"]


def test_dns_providers_parses_the_presets(client, fake_log):
    providers = client.dns_providers()
    assert fake_log.last_args() == ["--json", "dns", "providers"]
    assert providers["adguard"]["host"] == "dns.adguard-dns.com"
    assert providers["adguard"]["description"]


def test_dns_providers_rejects_a_malformed_preset(base_env):
    payload = json.dumps({"adguard": "dns.adguard-dns.com"})
    client = make_client(base_env, FAKE_CLI_DNS_PROVIDERS_JSON=payload)
    with pytest.raises(CliProtocolError, match="dns providers"):
        client.dns_providers()


def test_dns_status_parses_mode_and_specifier(client, fake_log):
    status = client.dns_status()
    assert fake_log.last_args() == ["--json", "dns", "status"]
    assert status == {"mode": "hostname", "specifier": "dns.adguard-dns.com"}


def test_dns_status_rejects_a_missing_mode(base_env):
    payload = json.dumps({"specifier": "dns.adguard-dns.com"})
    client = make_client(base_env, FAKE_CLI_DNS_STATUS_JSON=payload)
    with pytest.raises(CliProtocolError, match="mode"):
        client.dns_status()


def test_dns_check_parses_json(client, fake_log):
    result = client.dns_check()
    assert fake_log.last_args() == ["--json", "dns", "check"]
    assert result["ad_blocked"] is True
    assert result["ad_state"] == "blocked"
    assert result["control_state"] == "ok"
    assert result["online"] is True


def test_dns_check_accepts_exit_one_when_ads_are_not_blocked(base_env):
    payload = json.dumps(
        dns_check_payload(ad_ip="142.250.184.14", ad_state="ok", ad_blocked=False)
    )
    client = make_client(
        base_env,
        FAKE_CLI_DNS_CHECK_EXIT="1",
        FAKE_CLI_DNS_CHECK_JSON=payload,
    )
    result = client.dns_check()
    assert result["ad_blocked"] is False
    assert result["online"] is True


def test_dns_check_rejects_an_exit_code_above_one(base_env):
    client = make_client(base_env, FAKE_CLI_DNS_CHECK_EXIT="2")
    with pytest.raises(CliProtocolError, match="exited with 2"):
        client.dns_check()


def test_dns_check_rejects_a_malformed_payload(base_env):
    payload = json.dumps(dns_check_payload(ad_blocked="yes"))
    client = make_client(base_env, FAKE_CLI_DNS_CHECK_JSON=payload)
    with pytest.raises(CliProtocolError, match="ad_blocked"):
        client.dns_check()


def test_dns_check_keeps_an_explicit_null_blocked_state(base_env):
    payload = json.dumps(
        dns_check_payload(ad_ip="", ad_state="unknown", ad_blocked=None)
    )
    client = make_client(
        base_env,
        FAKE_CLI_DNS_CHECK_EXIT="1",
        FAKE_CLI_DNS_CHECK_JSON=payload,
    )
    result = client.dns_check()
    assert result["ad_blocked"] is None
    assert result["online"] is True


def test_dns_check_rejects_a_missing_blocked_key(base_env):
    incomplete = dns_check_payload()
    incomplete.pop("ad_blocked")
    client = make_client(
        base_env,
        FAKE_CLI_DNS_CHECK_JSON=json.dumps(incomplete),
    )
    with pytest.raises(CliProtocolError, match="ad_blocked"):
        client.dns_check()


def test_bench_snapshot_returns_path_and_data(client, fake_log):
    result = client.bench_snapshot("before")
    assert fake_log.last_args() == [
        "--json",
        "bench",
        "snapshot",
        "--label",
        "before",
    ]
    assert result["path"].endswith(".json")
    assert result["data"]["ram_available_mb"] == 2048


def test_bench_snapshot_rejects_a_missing_data_object(base_env):
    payload = json.dumps({"path": "C:/fake/bench/before.json"})
    client = make_client(base_env, FAKE_CLI_BENCH_SNAPSHOT_JSON=payload)
    with pytest.raises(CliProtocolError, match="data"):
        client.bench_snapshot("before")


def test_bench_snapshot_rejects_an_incomplete_snapshot(base_env):
    data = bench_data_payload()
    data.pop("packages_enabled")
    payload = json.dumps({"path": "C:/fake/bench/before.json", "data": data})
    client = make_client(base_env, FAKE_CLI_BENCH_SNAPSHOT_JSON=payload)
    with pytest.raises(CliProtocolError, match="packages_enabled"):
        client.bench_snapshot("before")


def test_bench_snapshot_rejects_an_empty_label(client, fake_log):
    with pytest.raises(ValueError):
        client.bench_snapshot("   ")
    assert fake_log.entries() == []


def test_bench_compare_returns_path_and_rows(client, fake_log, tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"

    result = client.bench_compare(before, after)

    assert fake_log.last_args() == [
        "--json",
        "bench",
        "compare",
        str(before),
        str(after),
    ]
    assert result["path"].endswith(".md")
    assert result["rows"][0]["metric"] == "ram_available_mb"
    assert result["rows"][0]["delta"] == 200


def test_bench_compare_rejects_rows_that_are_not_a_list(base_env):
    payload = json.dumps({"path": "C:/fake/bench/compare.md", "rows": {}})
    client = make_client(base_env, FAKE_CLI_BENCH_COMPARE_JSON=payload)
    with pytest.raises(CliProtocolError, match="rows"):
        client.bench_compare("before.json", "after.json")


def test_bench_list_returns_the_saved_paths(client, fake_log):
    paths = client.bench_list()
    assert fake_log.last_args() == ["--json", "bench", "list"]
    assert paths[0].endswith("_after.json")


def test_bench_list_rejects_a_non_string_entry(base_env):
    payload = json.dumps(["C:/fake/bench/before.json", 3])
    client = make_client(base_env, FAKE_CLI_BENCH_LIST_JSON=payload)
    with pytest.raises(CliProtocolError, match="bench list"):
        client.bench_list()


def test_backup_returns_the_cli_result(client, fake_log):
    result = client.backup()
    assert result.returncode == 0
    assert "Backup written" in result.stdout
    assert fake_log.last_args() == ["backup"]


def test_restore_dry_run(client, fake_log):
    result = client.restore_dry_run()
    assert result.returncode == 0
    assert fake_log.last_args() == ["restore", "--dry-run"]


def test_restore(client, fake_log):
    result = client.restore()
    assert result.returncode == 0
    assert fake_log.last_args() == ["restore"]


def test_restore_from_backup_uses_yes(client, fake_log):
    client.restore_from_backup(Path("C:/backup/session"))
    assert fake_log.last_args()[-1] == "--yes"
    assert fake_log.last_args() == [
        "restore",
        "--from-backup",
        str(Path("C:/backup/session")),
        "--yes",
    ]


def test_restore_from_backup_omits_yes_when_not_confirmed(client, fake_log):
    client.restore_from_backup(Path("C:/backup/session"), yes=False)
    assert fake_log.last_args() == [
        "restore",
        "--from-backup",
        str(Path("C:/backup/session")),
    ]


def test_version_returns_the_sidecar_banner(client, fake_log):
    assert client.version() == "CleanYourPhone 0.3.2"
    assert fake_log.last_args() == ["--version"]


def test_invalid_json_raises_cli_protocol_error(base_env):
    client = make_client(base_env, FAKE_CLI_INVALID_JSON="1")
    with pytest.raises(CliProtocolError) as error:
        client.probe()
    message = str(error.value)
    assert "--json probe" in message
    assert "invalid JSON" in message
    assert "stderr" in message


def test_non_zero_probe_raises_cli_protocol_error_with_the_stderr_tail(base_env):
    client = make_client(
        base_env,
        FAKE_CLI_PROBE_EXIT="2",
        FAKE_CLI_STDERR="adb: no devices/emulators found",
    )
    with pytest.raises(CliProtocolError) as error:
        client.probe()
    message = str(error.value)
    assert "--json probe" in message
    assert "exited with 2" in message
    assert "adb: no devices/emulators found" in message


def test_invalid_probe_shape_raises_cli_protocol_error(base_env):
    payload = json.dumps(probe_payload(profiles="pixel-8"))
    client = make_client(base_env, FAKE_CLI_PROBE_JSON=payload)
    with pytest.raises(CliProtocolError) as error:
        client.probe()
    message = str(error.value)
    assert "--json probe" in message
    assert "profiles" in message


def test_invalid_plan_shape_raises_cli_protocol_error(base_env):
    payload = json.dumps(plan_payload(match="yes"))
    client = make_client(base_env, FAKE_CLI_PLAN_JSON=payload)
    with pytest.raises(CliProtocolError) as error:
        client.plan("pixel-8")
    message = str(error.value)
    assert "--json plan" in message
    assert "match" in message


def test_null_managed_stays_unknown(base_env):
    payload = json.dumps(probe_payload(managed=None))
    client = make_client(base_env, FAKE_CLI_PROBE_JSON=payload)
    assert client.probe().managed is None


def test_empty_managed_becomes_unknown(base_env):
    payload = json.dumps(probe_payload(managed=""))
    client = make_client(base_env, FAKE_CLI_PROBE_JSON=payload)
    assert client.probe().managed is None


def test_environment_points_backup_and_state_at_home(client, fake_log, tmp_path):
    client.probe()
    env = fake_log.last_env()
    home = Path.home() / ".cleanyourphone"
    assert env["CLEANYOURPHONE_BACKUP"] == str(home / "backup")
    assert env["CLEANYOURPHONE_STATE"] == str(home)
    assert env["CLEANYOURPHONE_PROFILES"] == str(tmp_path / "profiles")
    assert env["ADB"] == str(tmp_path / "platform-tools" / "adb.exe")
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_set_adb_path_changes_the_next_probe_environment(client, fake_log, tmp_path):
    verified = tmp_path / "downloaded-platform-tools" / "adb.exe"
    verified.parent.mkdir()
    verified.write_bytes(b"")

    client.set_adb_path(verified)
    client.probe()

    assert fake_log.last_env()["ADB"] == str(verified)


def test_set_adb_path_accepts_a_path_object(client, fake_log, tmp_path):
    verified = tmp_path / "other" / "adb.exe"
    verified.parent.mkdir()
    verified.write_bytes(b"")

    client.set_adb_path(Path(verified))
    client.probe()

    assert fake_log.last_env()["ADB"] == str(verified)


def test_set_adb_path_rejects_an_empty_value(client):
    with pytest.raises(ValueError):
        client.set_adb_path("   ")


def test_missing_executable_raises_cli_error(tmp_path):
    client = CliClient([str(tmp_path / "does-not-exist.exe")])
    with pytest.raises(CliError):
        client.run(["probe"])


def test_sidecar_subprocess_uses_create_no_window(monkeypatch):
    calls: list[tuple[tuple, dict]] = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)
    client = CliClient(["cleanyourphone"])

    result = client.run(["probe"])

    assert result.ok
    assert len(calls) == 1
    expected = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    assert calls[0][1]["creationflags"] == expected


def test_empty_command_is_rejected():
    with pytest.raises(ValueError):
        CliClient([])
