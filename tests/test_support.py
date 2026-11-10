from cleanyourphone_app.domain.models import ProbeData
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


def test_managed_phone_is_blocked():
    decision = decide_support(probe(managed=True, auto_apply_profiles=("pixel-8",)))
    assert decision.allowed is False
    assert decision.reason == "managed"
    assert decision.link is None


def test_unknown_managed_state_is_blocked():
    decision = decide_support(probe(managed=None))
    assert decision.allowed is False
    assert decision.reason == "managed_unknown"


def test_unknown_user_count_is_blocked():
    decision = decide_support(probe(users=None))
    assert decision.allowed is False
    assert decision.reason == "users_unknown"


def test_multiple_users_are_blocked():
    decision = decide_support(probe(users=2))
    assert decision.allowed is False
    assert decision.reason == "multi_user"


def test_android_older_than_sdk_26_is_blocked():
    decision = decide_support(probe(sdk=25))
    assert decision.allowed is False
    assert decision.reason == "android_too_old"


def test_android_tv_is_blocked():
    decision = decide_support(probe(is_tv=True))
    assert decision.allowed is False
    assert decision.reason == "tv"


def test_no_device_profile_links_to_the_skill_site():
    decision = decide_support(probe(auto_apply_profiles=()))
    assert decision.allowed is False
    assert decision.reason == "no_device_profile"
    assert decision.link == "https://jparedesds.github.io/cleanyourphone-web/"


def test_skill_url_is_the_public_site():
    assert SKILL_URL == "https://jparedesds.github.io/cleanyourphone-web/"


def test_documented_profile_is_allowed_for_manual_review():
    decision = decide_support(
        probe(auto_apply_profiles=(), documented_profiles=("pixel-8-documented",))
    )
    assert decision.allowed is True
    assert decision.reason == "documented"
    assert decision.profile_ids == ("pixel-8-documented",)
    assert decision.verification == "documented"
    assert decision.link is None


def test_one_exact_profile_is_allowed():
    decision = decide_support(probe(auto_apply_profiles=("pixel-8",)))
    assert decision.allowed is True
    assert decision.profile_ids == ("pixel-8",)
    assert decision.verification == "device"


def test_multiple_exact_profiles_are_allowed_for_selection():
    decision = decide_support(probe(auto_apply_profiles=("a", "b")))
    assert decision.allowed is True
    assert decision.profile_ids == ("a", "b")
    assert decision.verification == "device"


def test_sdk_26_is_new_enough():
    decision = decide_support(probe(sdk=26))
    assert decision.allowed is True


def test_tv_wins_over_other_blockers():
    decision = decide_support(
        probe(is_tv=True, managed=True, users=2, sdk=25, auto_apply_profiles=())
    )
    assert decision.reason == "tv"


def test_unknown_managed_state_wins_over_multi_user():
    decision = decide_support(
        probe(managed=None, users=2, sdk=25, auto_apply_profiles=())
    )
    assert decision.reason == "managed_unknown"


def test_old_android_wins_over_missing_profile():
    decision = decide_support(probe(sdk=25, auto_apply_profiles=()))
    assert decision.reason == "android_too_old"
    assert decision.link is None
