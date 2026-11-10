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
