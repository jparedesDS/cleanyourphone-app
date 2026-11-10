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


def main(argv: list[str]) -> int:
    _record(argv)

    delay = float(os.environ.get("FAKE_CLI_SLEEP", "0") or "0")
    if delay:
        time.sleep(delay)

    stderr_text = os.environ.get("FAKE_CLI_STDERR", "")
    if stderr_text:
        print(stderr_text, file=sys.stderr)

    if "--version" in argv:
        print("CleanYourPhone 0.2.2")
        return _exit_code("VERSION")

    args = [arg for arg in argv if arg != "--json"]
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
