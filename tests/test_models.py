import pytest

from cleanyourphone_app.domain.models import PlanData, PlanRow, ProbeData


def test_probe_from_dict_reads_the_cli_shape():
    probe = ProbeData.from_dict(
        {
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
            "documented_profiles": ["pixel-8-documented"],
            "auto_apply_profiles": ["pixel-8"],
            "reference_profiles": ["generic"],
        }
    )
    assert probe.brand == "Google"
    assert probe.model == "Pixel 8"
    assert probe.sdk == 34
    assert probe.managed is False
    assert probe.users == 1
    assert probe.battery == {"level": 80}
    assert probe.profiles == ("pixel-8",)
    assert probe.documented_profiles == ("pixel-8-documented",)
    assert probe.auto_apply_profiles == ("pixel-8",)
    assert probe.reference_profiles == ("generic",)


def test_probe_from_dict_treats_missing_profile_lists_as_empty():
    probe = ProbeData.from_dict(
        {
            "brand": "Google",
            "model": "Pixel 8",
            "device": "shiba",
            "android": "14",
            "sdk": 34,
            "build": "AP1A.240505.004",
            "fingerprint": "fp",
            "managed": None,
            "users": None,
            "is_tv": False,
            "battery": {},
        }
    )
    assert probe.profiles == ()
    assert probe.auto_apply_profiles == ()
    assert probe.managed is None
    assert probe.users is None


def test_plan_from_dict_reads_profile_and_rows():
    plan = PlanData.from_dict(
        {
            "profile": {"id": "pixel-8", "brand": "Google"},
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
    )
    assert plan.profile_id == "pixel-8"
    assert plan.match is True
    assert plan.verification == "device"
    assert plan.auto_apply is True
    assert plan.rows == (
        PlanRow(
            action="DISABLE",
            package="com.google.android.apps.wellbeing",
            why="unused",
            breaks="Digital Wellbeing",
            reason="",
        ),
    )


def test_plan_row_defaults_missing_text_fields():
    row = PlanRow.from_dict({"action": "KEEP", "package": "com.example.keep"})
    assert row.why == ""
    assert row.breaks == ""
    assert row.reason == ""


def probe_payload(**overrides):
    payload = {
        "brand": "Google",
        "model": "Pixel 8",
        "device": "shiba",
        "android": "14",
        "sdk": 34,
        "build": "AP1A.240505.004",
        "fingerprint": "fp",
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
        "profile": {"id": "pixel-8"},
        "match": True,
        "verification": "device",
        "auto_apply": True,
        "rows": [],
    }
    payload.update(overrides)
    return payload


def test_probe_rejects_a_scalar_string_where_a_profile_list_is_expected():
    with pytest.raises(ValueError, match="profiles"):
        ProbeData.from_dict(probe_payload(profiles="pixel-8"))


def test_probe_rejects_non_string_profile_ids():
    with pytest.raises(ValueError, match="profiles"):
        ProbeData.from_dict(probe_payload(profiles=["pixel-8", 3]))


def test_probe_rejects_empty_profile_ids():
    with pytest.raises(ValueError, match="profiles"):
        ProbeData.from_dict(probe_payload(auto_apply_profiles=[""]))


def test_probe_never_turns_null_text_into_the_string_none():
    probe = ProbeData.from_dict(probe_payload(brand=None, build=None))
    assert probe.brand == ""
    assert probe.build == ""


def test_probe_normalizes_empty_managed_to_unknown():
    assert ProbeData.from_dict(probe_payload(managed="")).managed is None


def test_probe_keeps_null_managed_unknown():
    assert ProbeData.from_dict(probe_payload(managed=None)).managed is None


@pytest.mark.parametrize("managed", ["false", "no", 0, 1])
def test_probe_rejects_a_non_boolean_managed_value(managed):
    with pytest.raises(ValueError, match="managed"):
        ProbeData.from_dict(probe_payload(managed=managed))


def test_probe_requires_is_tv():
    payload = probe_payload()
    payload.pop("is_tv")
    with pytest.raises(ValueError, match="is_tv"):
        ProbeData.from_dict(payload)


@pytest.mark.parametrize("is_tv", ["false", "true", 0, 1, None])
def test_probe_requires_a_boolean_is_tv(is_tv):
    with pytest.raises(ValueError, match="is_tv"):
        ProbeData.from_dict(probe_payload(is_tv=is_tv))


@pytest.mark.parametrize("sdk", ["34", 34.0, True, -1])
def test_probe_requires_an_integer_sdk(sdk):
    with pytest.raises(ValueError, match="sdk"):
        ProbeData.from_dict(probe_payload(sdk=sdk))


def test_probe_defaults_a_missing_sdk_to_zero():
    payload = probe_payload()
    payload.pop("sdk")
    assert ProbeData.from_dict(payload).sdk == 0
    assert ProbeData.from_dict(probe_payload(sdk=None)).sdk == 0
    assert ProbeData.from_dict(probe_payload(sdk="")).sdk == 0


@pytest.mark.parametrize("users", ["1", 1.0, True, -1])
def test_probe_requires_an_integer_user_count(users):
    with pytest.raises(ValueError, match="users"):
        ProbeData.from_dict(probe_payload(users=users))


def test_probe_accepts_unknown_users():
    assert ProbeData.from_dict(probe_payload(users=None)).users is None
    assert ProbeData.from_dict(probe_payload(users="")).users is None


def test_probe_rejects_a_non_object_battery():
    with pytest.raises(ValueError, match="battery"):
        ProbeData.from_dict(probe_payload(battery=[]))
    assert ProbeData.from_dict(probe_payload(battery=None)).battery == {}


def test_plan_requires_a_boolean_match():
    with pytest.raises(ValueError, match="match"):
        PlanData.from_dict(plan_payload(match="yes"))


def test_plan_requires_match_to_be_present():
    payload = plan_payload()
    payload.pop("match")
    with pytest.raises(ValueError, match="match"):
        PlanData.from_dict(payload)


def test_plan_requires_a_non_empty_profile_id():
    with pytest.raises(ValueError, match="profile"):
        PlanData.from_dict(plan_payload(profile={"id": ""}))


def test_plan_rejects_a_missing_profile_id():
    with pytest.raises(ValueError, match="profile"):
        PlanData.from_dict(plan_payload(profile={}))


def test_plan_rejects_a_non_object_profile():
    with pytest.raises(ValueError, match="profile"):
        PlanData.from_dict(plan_payload(profile="pixel-8"))


def test_plan_requires_boolean_auto_apply():
    with pytest.raises(ValueError, match="auto_apply"):
        PlanData.from_dict(plan_payload(auto_apply="yes"))


def test_plan_rejects_rows_that_are_not_a_list():
    with pytest.raises(ValueError, match="rows"):
        PlanData.from_dict(plan_payload(rows={}))


def test_plan_row_requires_an_action_and_package():
    with pytest.raises(ValueError, match="action"):
        PlanRow.from_dict({"action": "", "package": "pkg"})
    with pytest.raises(ValueError, match="package"):
        PlanRow.from_dict({"action": "DISABLE", "package": ""})


def test_plan_row_never_turns_null_text_into_the_string_none():
    row = PlanRow.from_dict(
        {"action": "DISABLE", "package": "pkg", "why": None, "breaks": None}
    )
    assert row.why == ""
    assert row.breaks == ""
