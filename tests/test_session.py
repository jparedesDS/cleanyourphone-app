from pathlib import Path

import pytest

from cleanyourphone_app.domain.models import ProbeData
from cleanyourphone_app.domain.session import (
    InvalidTransition,
    SessionController,
    SessionState,
    Transport,
    TransportLocked,
)
from cleanyourphone_app.domain.support import SKILL_URL, decide_support


def probe(**overrides) -> ProbeData:
    fields = {
        "brand": "Google",
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
        "profiles": ("pixel-8",),
        "auto_apply_profiles": ("pixel-8",),
    }
    fields.update(overrides)
    return ProbeData(**fields)


def test_cannot_switch_transport_mid_session():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    with pytest.raises(TransportLocked):
        s.set_transport(Transport.WIFI)


def test_can_apply_only_after_backup_and_selection():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    assert s.can_apply() is False
    s.backup_done(Path("C:/backup/one"))
    assert s.can_apply() is False
    s.set_selection(["com.google.android.apps.wellbeing"])
    assert s.can_apply() is True


def test_can_undo_with_a_backup_and_serial():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    assert s.can_undo() is False
    s.backup_done(Path("C:/backup/one"))
    assert s.can_undo() is True


def test_new_session_starts_on_welcome():
    s = SessionController()

    assert s.state is SessionState.WELCOME
    assert s.serial is None
    assert s.transport is None
    assert s.probe is None
    assert s.profile_id is None
    assert s.backup_path is None
    assert s.selected_packages == ()
    assert s.completed_batches == 0
    assert s.can_apply() is False
    assert s.can_undo() is False


def test_start_moves_to_connecting():
    s = SessionController()

    s.start()

    assert s.state is SessionState.CONNECTING


def test_cannot_start_twice():
    s = SessionController()
    s.start()

    with pytest.raises(InvalidTransition):
        s.start()


def test_transport_can_be_picked_before_connecting():
    s = SessionController()
    s.start()

    s.set_transport(Transport.WIFI)
    s.connected("wifi-1", Transport.WIFI, probe(), profile_id="pixel-8")

    assert s.transport is Transport.WIFI
    assert s.state is SessionState.CHECKING


def test_transport_can_change_before_a_device_connects():
    s = SessionController()
    s.start()
    s.set_transport(Transport.WIFI)

    s.set_transport(Transport.USB)
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")

    assert s.transport is Transport.USB


def test_same_transport_is_not_a_switch():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")

    s.set_transport(Transport.USB)

    assert s.transport is Transport.USB


def test_connected_stores_the_exact_serial_and_probe():
    phone = probe()

    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, phone, profile_id="pixel-8")

    assert s.serial == "usb-1"
    assert s.transport is Transport.USB
    assert s.probe is phone
    assert s.profile_id == "pixel-8"


def test_blocked_stores_the_reason_and_link():
    decision = decide_support(probe(auto_apply_profiles=()))

    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.blocked(decision)

    assert s.state is SessionState.BLOCKED
    assert s.blocked_reason == "no_device_profile"
    assert s.blocked_link == SKILL_URL
    assert s.can_apply() is False
    assert s.can_undo() is False


def test_blocked_rejects_an_allowed_decision():
    s = SessionController()
    s.start()

    with pytest.raises(ValueError):
        s.blocked(decide_support(probe(auto_apply_profiles=("pixel-8",))))


def test_checked_stores_the_profile_and_moves_to_backup():
    phone = probe()

    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, phone)
    s.checked(phone, "pixel-8")

    assert s.state is SessionState.BACKUP
    assert s.profile_id == "pixel-8"
    assert s.probe is phone


def test_selection_is_unique_and_keeps_order():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))

    s.set_selection(["b.pkg", "a.pkg", "b.pkg"])

    assert s.selected_packages == ("b.pkg", "a.pkg")


def test_blank_package_is_rejected():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))

    with pytest.raises(ValueError):
        s.set_selection(["ok.pkg", "  "])


def test_selection_before_backup_is_rejected():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")

    with pytest.raises(InvalidTransition):
        s.set_selection(["com.google.android.apps.wellbeing"])


def test_can_apply_needs_a_profile_id():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe())
    s.backup_done(Path("C:/backup/one"))
    s.set_selection(["com.google.android.apps.wellbeing"])

    assert s.state is SessionState.REVIEW
    assert s.can_apply() is False


def test_can_apply_needs_a_non_empty_selection():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))
    s.set_selection([])

    assert s.can_apply() is False


def test_start_apply_requires_a_complete_review():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))
    s.set_selection(["com.google.android.apps.wellbeing"])

    with pytest.raises(InvalidTransition):
        s.batch_done()

    s.start_apply()

    assert s.state is SessionState.APPLYING


def test_batch_done_increments_progress():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))
    s.set_selection(["a.pkg", "b.pkg"])
    s.start_apply()

    s.batch_done()
    s.batch_done()

    assert s.completed_batches == 2
    assert s.state is SessionState.APPLYING


def test_finish_reaches_done():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))
    s.set_selection(["com.google.android.apps.wellbeing"])
    s.start_apply()
    s.batch_done()

    s.finish()

    assert s.state is SessionState.DONE


def test_finish_before_applying_is_rejected():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))
    s.set_selection(["com.google.android.apps.wellbeing"])

    with pytest.raises(InvalidTransition):
        s.finish()


def test_fail_records_the_error():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")

    s.fail("backup failed")

    assert s.state is SessionState.ERROR
    assert s.error_message == "backup failed"
    assert s.can_apply() is False


def test_can_undo_survives_a_failed_apply():
    s = SessionController()
    s.start()
    s.connected("usb-1", Transport.USB, probe(), profile_id="pixel-8")
    s.backup_done(Path("C:/backup/one"))
    s.set_selection(["com.google.android.apps.wellbeing"])
    s.start_apply()
    s.fail("batch failed")

    assert s.state is SessionState.ERROR
    assert s.can_undo() is True


def test_states_cover_the_guided_flow():
    assert [state.value for state in SessionState] == [
        "welcome",
        "connecting",
        "checking",
        "blocked",
        "backup",
        "review",
        "applying",
        "done",
        "error",
    ]
