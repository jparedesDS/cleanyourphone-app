"""Immutable models for the JSON returned by the CleanYourPhone CLI.

The CLI is treated as a typed external process. ``from_dict`` is deliberately
strict about the fields the app makes decisions with, so a malformed or
unexpected sidecar response fails closed instead of producing plausible data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_MISSING = object()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _text(
    payload: Mapping[str, Any],
    key: str,
    label: str,
    *,
    required: bool = False,
) -> str:
    value = payload.get(key, _MISSING)
    if value is _MISSING or value is None:
        if required:
            raise ValueError(f"{label} must be a non-empty string")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if required and not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _required_bool(payload: Mapping[str, Any], key: str, label: str) -> bool:
    if key not in payload:
        raise ValueError(f"{label} is required")
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _optional_bool(payload: Mapping[str, Any], key: str, label: str) -> bool | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true, false or null")
    return value


def _sdk(payload: Mapping[str, Any]) -> int:
    if "sdk" not in payload:
        return 0
    value = payload["sdk"]
    if value is None or value == "":
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("probe.sdk must be an integer")
    if value < 0:
        raise ValueError("probe.sdk must not be negative")
    return value


def _optional_int(payload: Mapping[str, Any], key: str, label: str) -> int | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer or null")
    if value < 0:
        raise ValueError(f"{label} must not be negative")
    return value


def _profile_ids(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list of profile ids")
    profile_ids: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        profile_ids.append(item)
    return tuple(profile_ids)


def _battery(value: Any) -> dict:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("probe.battery must be a JSON object")
    return dict(value)


@dataclass(frozen=True)
class ProbeData:
    brand: str
    model: str
    device: str
    android: str
    sdk: int
    build: str
    fingerprint: str
    managed: bool | None
    users: int | None
    is_tv: bool
    battery: dict
    profiles: tuple[str, ...] = ()
    documented_profiles: tuple[str, ...] = ()
    auto_apply_profiles: tuple[str, ...] = ()
    reference_profiles: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ProbeData:
        """Build a probe from the CLI payload, ignoring fields the app does not use."""
        payload = _mapping(payload, "probe")
        return cls(
            brand=_text(payload, "brand", "probe.brand"),
            model=_text(payload, "model", "probe.model"),
            device=_text(payload, "device", "probe.device"),
            android=_text(payload, "android", "probe.android"),
            sdk=_sdk(payload),
            build=_text(payload, "build", "probe.build"),
            fingerprint=_text(payload, "fingerprint", "probe.fingerprint"),
            managed=_optional_bool(payload, "managed", "probe.managed"),
            users=_optional_int(payload, "users", "probe.users"),
            is_tv=_required_bool(payload, "is_tv", "probe.is_tv"),
            battery=_battery(payload.get("battery")),
            profiles=_profile_ids(payload.get("profiles"), "probe.profiles"),
            documented_profiles=_profile_ids(
                payload.get("documented_profiles"), "probe.documented_profiles"
            ),
            auto_apply_profiles=_profile_ids(
                payload.get("auto_apply_profiles"), "probe.auto_apply_profiles"
            ),
            reference_profiles=_profile_ids(
                payload.get("reference_profiles"), "probe.reference_profiles"
            ),
        )


@dataclass(frozen=True)
class PlanRow:
    action: str
    package: str
    why: str = ""
    breaks: str = ""
    reason: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PlanRow:
        payload = _mapping(payload, "plan row")
        return cls(
            action=_text(payload, "action", "plan row action", required=True),
            package=_text(payload, "package", "plan row package", required=True),
            why=_text(payload, "why", "plan row why"),
            breaks=_text(payload, "breaks", "plan row breaks"),
            reason=_text(payload, "reason", "plan row reason"),
        )


@dataclass(frozen=True)
class PlanData:
    profile_id: str
    match: bool
    verification: str
    auto_apply: bool
    rows: tuple[PlanRow, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PlanData:
        payload = _mapping(payload, "plan")
        profile = _mapping(payload.get("profile"), "plan.profile")
        profile_id = _text(profile, "id", "plan.profile.id", required=True)

        rows_value = payload.get("rows")
        if rows_value is None:
            rows_value = []
        if not isinstance(rows_value, (list, tuple)):
            raise ValueError("plan.rows must be a list")

        return cls(
            profile_id=profile_id,
            match=_required_bool(payload, "match", "plan.match"),
            verification=_text(payload, "verification", "plan.verification"),
            auto_apply=_required_bool(payload, "auto_apply", "plan.auto_apply"),
            rows=tuple(PlanRow.from_dict(row) for row in rows_value),
        )
