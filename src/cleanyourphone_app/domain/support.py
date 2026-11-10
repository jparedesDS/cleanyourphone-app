"""The supported-device decision, kept in one place so every screen agrees."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProbeData

SKILL_URL = "https://jparedesds.github.io/cleanyourphone-web/"
CONNECT_GUIDE_URL = (
    "https://github.com/jparedesDS/cleanyourphone/blob/main/docs/CONNECT.md"
)

MIN_SDK = 26


@dataclass(frozen=True)
class SupportedDecision:
    allowed: bool
    reason: str
    profile_ids: tuple[str, ...] = ()
    link: str | None = None
    verification: str = "device"


def decide_support(probe: ProbeData) -> SupportedDecision:
    """Return whether the app may change packages on this phone.

    ``reason`` is a stable token for the UI: ``tv``, ``managed_unknown``,
    ``managed``, ``users_unknown``, ``multi_user``, ``android_too_old``,
    ``documented`` or ``no_device_profile``. Only ``no_device_profile`` links to
    the skill site; the other blockers are safety rules the skill cannot bypass
    either.

    A documented profile is allowed into the manual review, never auto-apply.
    The UI must show its warning and require an explicit acknowledgement.
    """
    if probe.is_tv:
        return SupportedDecision(allowed=False, reason="tv")
    if probe.managed is None:
        return SupportedDecision(allowed=False, reason="managed_unknown")
    if probe.managed:
        return SupportedDecision(allowed=False, reason="managed")
    if probe.users is None:
        return SupportedDecision(allowed=False, reason="users_unknown")
    if probe.users != 1:
        return SupportedDecision(allowed=False, reason="multi_user")
    if probe.sdk < MIN_SDK:
        return SupportedDecision(allowed=False, reason="android_too_old")
    if probe.auto_apply_profiles:
        return SupportedDecision(
            allowed=True,
            reason="supported",
            profile_ids=tuple(probe.auto_apply_profiles),
            verification="device",
        )
    if probe.documented_profiles:
        return SupportedDecision(
            allowed=True,
            reason="documented",
            profile_ids=tuple(probe.documented_profiles),
            verification="documented",
        )
    return SupportedDecision(
        allowed=False,
        reason="no_device_profile",
        link=SKILL_URL,
    )
