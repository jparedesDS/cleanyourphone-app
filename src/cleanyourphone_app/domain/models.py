"""Immutable models for the JSON returned by the CleanYourPhone CLI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _string_tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in value or ())


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


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
        return cls(
            brand=str(payload.get("brand", "")),
            model=str(payload.get("model", "")),
            device=str(payload.get("device", "")),
            android=str(payload.get("android", "")),
            sdk=int(payload.get("sdk") or 0),
            build=str(payload.get("build", "")),
            fingerprint=str(payload.get("fingerprint", "")),
            managed=payload.get("managed"),
            users=_optional_int(payload.get("users")),
            is_tv=bool(payload.get("is_tv", False)),
            battery=dict(payload.get("battery") or {}),
            profiles=_string_tuple(payload.get("profiles")),
            documented_profiles=_string_tuple(payload.get("documented_profiles")),
            auto_apply_profiles=_string_tuple(payload.get("auto_apply_profiles")),
            reference_profiles=_string_tuple(payload.get("reference_profiles")),
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
        return cls(
            action=str(payload.get("action", "")),
            package=str(payload.get("package", "")),
            why=str(payload.get("why") or ""),
            breaks=str(payload.get("breaks") or ""),
            reason=str(payload.get("reason") or ""),
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
        profile = payload["profile"]
        return cls(
            profile_id=str(profile["id"]),
            match=bool(payload.get("match", False)),
            verification=str(payload.get("verification", "")),
            auto_apply=bool(payload.get("auto_apply", False)),
            rows=tuple(PlanRow.from_dict(row) for row in payload.get("rows") or ()),
        )
