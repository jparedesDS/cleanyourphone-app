"""Stand-in for the frozen CleanYourPhone sidecar used by the CLI client tests.

The fake follows the real CLI's argv and JSON shapes closely enough to exercise
the client, and records every invocation (argv plus the environment keys the
client is expected to set) to ``$FAKE_CLI_LOG`` as one JSON object per line.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

PROBE = {
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

PLAN_ROWS = [
    {
        "action": "DISABLE",
        "package": "com.google.android.apps.wellbeing",
        "why": "unused",
        "breaks": "Digital Wellbeing",
        "section": "disable",
        "reason": "",
    },
    {
        "action": "ASK",
        "package": "com.google.android.apps.youtube.music",
        "why": "media app",
        "breaks": "YouTube Music",
        "section": "ask",
        "reason": "",
    },
]

VERIFY_CHECKS = [
    {"check": "Device", "status": "PASS", "detail": "Google Pixel 8 (shiba), Android 14"},
    {"check": "Home", "status": "PASS", "detail": "com.google.android.apps.nexuslauncher"},
]

DNS_PROVIDERS = {
    "adguard": {
        "host": "dns.adguard-dns.com",
        "description": "AdGuard DNS: ads and trackers",
    },
    "adguard-family": {
        "host": "family.adguard-dns.com",
        "description": "AdGuard Family: ads, trackers and adult sites",
    },
    "controld": {
        "host": "p2.freedns.controld.com",
        "description": "Control D free: ads and trackers",
    },
    "mullvad": {
        "host": "adblock.dns.mullvad.net",
        "description": "Mullvad DNS: ads and trackers",
    },
}

DNS_STATUS = {"mode": "hostname", "specifier": "dns.adguard-dns.com"}

DNS_CHECK = {
    "ad_domain": "doubleclick.net",
    "ad_ip": "0.0.0.0",
    "ad_state": "blocked",
    "ad_blocked": True,
    "control_domain": "wikipedia.org",
    "control_ip": "203.0.113.7",
    "control_state": "ok",
    "online": True,
}

BENCH_DATA = {
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

BENCH_ROWS = [
    {
        "metric": "ram_available_mb",
        "label": "RAM available (MB)",
        "before": 1000,
        "after": 1200,
        "delta": 200,
        "pct": 20.0,
    },
    {
        "metric": "packages_enabled",
        "label": "Packages enabled",
        "before": 210,
        "after": 200,
        "delta": -10,
        "pct": -4.8,
    },
]

BENCH_PATHS = [
    "C:/fake/bench/20260101_000000_after.json",
    "C:/fake/bench/20260101_000000_before.json",
]

ENV_KEYS = (
    "ADB",
    "CLEANYOURPHONE_PROFILES",
    "CLEANYOURPHONE_BACKUP",
    "CLEANYOURPHONE_STATE",
    "PYTHONIOENCODING",
)


def _record(argv: list[str]) -> None:
    log_path = os.environ.get("FAKE_CLI_LOG")
    if not log_path:
        return
    record = {
        "args": argv,
        "env": {key: os.environ.get(key) for key in ENV_KEYS},
    }
    with open(log_path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _exit_code(name: str) -> int:
    return int(os.environ.get(f"FAKE_CLI_{name}_EXIT", "0"))


def _json_text(command: str, default: Any) -> str:
    override = os.environ.get(f"FAKE_CLI_{command.upper()}_JSON")
    if override is not None:
        return override
    if os.environ.get("FAKE_CLI_INVALID_JSON") == "1":
        return "this is not json"
    return json.dumps(default, indent=2, ensure_ascii=False)


def _option(argv: list[str], name: str, default: str | None = None) -> str | None:
    try:
        index = argv.index(name)
    except ValueError:
        return default
    if index + 1 >= len(argv):
        return default
    return argv[index + 1]


def _dns(rest: list[str]) -> int:
    subcommand = rest[0] if rest else ""

    if subcommand == "providers":
        print(_json_text("dns_providers", DNS_PROVIDERS))
        return _exit_code("DNS_PROVIDERS")

    if subcommand == "status":
        print(_json_text("dns_status", DNS_STATUS))
        return _exit_code("DNS_STATUS")

    if subcommand == "check":
        print(_json_text("dns_check", DNS_CHECK))
        return _exit_code("DNS_CHECK")

    if subcommand == "set":
        provider = rest[1] if len(rest) > 1 else "(missing)"
        print(f"Private DNS set to {provider}. Undo: cleanyourphone dns restore")
        return _exit_code("DNS_SET")

    if subcommand == "off":
        print("Private DNS set to opportunistic (the Android default).")
        return _exit_code("DNS_OFF")

    print(f"error: unknown dns command {subcommand}", file=sys.stderr)
    return 2


def _bench(rest: list[str]) -> int:
    subcommand = rest[0] if rest else ""

    if subcommand == "snapshot":
        label = _option(rest, "--label", "snapshot") or "snapshot"
        payload = {
            "path": f"C:/fake/bench/20260101_000000_{label}.json",
            "data": BENCH_DATA,
        }
        print(_json_text("bench_snapshot", payload))
        return _exit_code("BENCH_SNAPSHOT")

    if subcommand == "compare":
        if len(rest) < 3:
            print("error: compare needs two snapshots", file=sys.stderr)
            return 2
        payload = {
            "path": "C:/fake/bench/compare-20260101_000000.md",
            "rows": BENCH_ROWS,
        }
        print(_json_text("bench_compare", payload))
        return _exit_code("BENCH_COMPARE")

    if subcommand == "list":
        print(_json_text("bench_list", BENCH_PATHS))
        return _exit_code("BENCH_LIST")

    print(f"error: unknown bench command {subcommand}", file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    _record(argv)

    delay = float(os.environ.get("FAKE_CLI_SLEEP", "0") or "0")
    if delay:
        time.sleep(delay)

    stderr_text = os.environ.get("FAKE_CLI_STDERR", "")
    if stderr_text:
        print(stderr_text, file=sys.stderr)

    if "--version" in argv:
        print("CleanYourPhone 0.3.2")
        return _exit_code("VERSION")

    args = [arg for arg in argv if arg != "--json"]
    if "--serial" in args:
        index = args.index("--serial")
        del args[index : index + 2]
    if not args:
        print("error: missing command", file=sys.stderr)
        return 2

    command, rest = args[0], args[1:]

    if command == "probe":
        print(_json_text("probe", PROBE))
        return _exit_code("PROBE")

    if command == "plan":
        profile_id = _option(rest, "--profile", "pixel-8")
        payload = {
            "profile": {"id": profile_id, "brand": "Google", "model": "Pixel 8"},
            "match": True,
            "verification": "device",
            "auto_apply": True,
            "rows": PLAN_ROWS,
        }
        print(_json_text("plan", payload))
        return _exit_code("PLAN")

    if command == "verify":
        print(_json_text("verify", VERIFY_CHECKS))
        return _exit_code("VERIFY")

    if command == "list":
        state = _option(rest, "--state", "all")
        if state == "disabled":
            packages = [
                package.strip()
                for package in os.environ.get(
                    "FAKE_CLI_DISABLED", "com.example.disabled,com.example.other"
                ).split(",")
                if package.strip()
            ]
        else:
            packages = []
        rows = [
            {"package": package, "flags": ["disabled"], "protected": False}
            for package in packages
        ]
        print(_json_text("list", rows))
        return _exit_code("LIST")

    if command == "dns":
        return _dns(rest)

    if command == "bench":
        return _bench(rest)

    if command == "backup":
        print("Backup written to C:/fake/backup/session")
        return _exit_code("BACKUP")

    if command == "disable":
        print("Done. " + ", ".join(rest) + " disabled.")
        return _exit_code("DISABLE")

    if command == "restore":
        if "--from-backup" in rest:
            print(f"Backup: {_option(rest, '--from-backup')}")
            if "--yes" in rest:
                print("Restore from backup complete.")
            else:
                print("Dry run. Review the list, then re-run with --yes.")
        elif "--dry-run" in rest:
            print("WOULD ENABLE com.example.disabled")
            print("Dry run. Nothing changed.")
        else:
            print("Restore complete.")
        return _exit_code("RESTORE")

    print(f"error: unknown command {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
