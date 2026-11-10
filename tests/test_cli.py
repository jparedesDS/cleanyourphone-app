import json
import sys
from pathlib import Path

import pytest

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
    assert client.version() == "CleanYourPhone 0.2.2"
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


def test_missing_executable_raises_cli_error(tmp_path):
    client = CliClient([str(tmp_path / "does-not-exist.exe")])
    with pytest.raises(CliError):
        client.run(["probe"])


def test_empty_command_is_rejected():
    with pytest.raises(ValueError):
        CliClient([])
