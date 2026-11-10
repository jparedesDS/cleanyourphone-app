"""BackupStore finds the backup the CLI just wrote for this exact phone."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from cleanyourphone_app.services.backup import BackupStore

SERIAL = "usb-1"
FINGERPRINT = "google/shiba/shiba:14/AP1A.240505.004/11228896:user/release-keys"


def write_backup(
    root: Path,
    name: str,
    *,
    serial: object = SERIAL,
    fingerprint: object = FINGERPRINT,
    timestamp: object = "20260101_120000",
    probe: object | None = None,
) -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "timestamp": timestamp,
        "serial": serial,
        "probe": {"fingerprint": fingerprint} if probe is None else probe,
    }
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


def test_latest_returns_the_newest_matching_backup(tmp_path):
    root = tmp_path / ".cleanyourphone" / "backup"
    write_backup(root, "old", timestamp="20260101_120000")
    newest = write_backup(root, "new", timestamp="20260102_120000")

    assert BackupStore.latest(SERIAL, FINGERPRINT, root) == newest


def test_latest_returns_none_when_only_a_serial_mismatch_exists(tmp_path):
    root = tmp_path / "backup"
    write_backup(root, "other-phone", serial="usb-2")

    assert BackupStore.latest(SERIAL, FINGERPRINT, root) is None


def test_latest_returns_none_when_only_a_fingerprint_mismatch_exists(tmp_path):
    root = tmp_path / "backup"
    write_backup(root, "other-build", fingerprint="google/shiba/shiba:13/OLD")

    assert BackupStore.latest(SERIAL, FINGERPRINT, root) is None


def test_latest_skips_a_damaged_meta_file(tmp_path):
    root = tmp_path / "backup"
    damaged = root / "damaged"
    damaged.mkdir(parents=True)
    (damaged / "meta.json").write_text("{not json", encoding="utf-8")
    matching = write_backup(root, "matching")

    assert BackupStore.latest(SERIAL, FINGERPRINT, root) == matching


def test_latest_skips_meta_files_without_a_probe_object(tmp_path):
    root = tmp_path / "backup"
    write_backup(root, "bad-probe", probe="not-an-object")
    matching = write_backup(root, "matching")

    assert BackupStore.latest(SERIAL, FINGERPRINT, root) == matching


def test_latest_returns_none_when_the_root_does_not_exist(tmp_path):
    assert BackupStore.latest(SERIAL, FINGERPRINT, tmp_path / "missing") is None


def test_matching_returns_only_identity_matches_oldest_first(tmp_path):
    root = tmp_path / "backup"
    older = write_backup(root, "older", timestamp="20260101_120000")
    write_backup(root, "other-phone", serial="usb-2")
    newer = write_backup(root, "newer", timestamp="20260102_120000")

    assert BackupStore.matching(SERIAL, FINGERPRINT, root) == (older, newer)


def test_is_fresh_rejects_a_preexisting_folder_until_it_is_rewritten(tmp_path):
    root = tmp_path / "backup"
    folder = write_backup(root, "20260102_120000")
    old = time.time() - 300
    os.utime(folder / "meta.json", (old, old))
    os.utime(folder, (old, old))
    since = time.time() - 60

    assert BackupStore.is_fresh(folder, since) is False

    os.utime(folder / "meta.json", None)

    assert BackupStore.is_fresh(folder, since) is True


def test_latest_falls_back_to_folder_mtime_without_a_timestamp(tmp_path):
    root = tmp_path / "backup"
    older = write_backup(root, "older", timestamp=None)
    newer = write_backup(root, "newer", timestamp=None)
    now = time.time()
    os.utime(older / "meta.json", (now - 300, now - 300))
    os.utime(older, (now - 300, now - 300))
    os.utime(newer / "meta.json", (now - 60, now - 60))
    os.utime(newer, (now - 60, now - 60))

    assert BackupStore.latest(SERIAL, FINGERPRINT, root) == newer


@pytest.mark.parametrize(
    ("serial", "fingerprint"),
    [("", FINGERPRINT), (SERIAL, ""), ("   ", FINGERPRINT), (SERIAL, "   ")],
)
def test_latest_rejects_an_empty_identity(tmp_path, serial, fingerprint):
    with pytest.raises(ValueError):
        BackupStore.latest(serial, fingerprint, tmp_path)


def test_latest_rejects_a_non_path_root(tmp_path):
    with pytest.raises(TypeError):
        BackupStore.latest(SERIAL, FINGERPRINT, str(tmp_path))
