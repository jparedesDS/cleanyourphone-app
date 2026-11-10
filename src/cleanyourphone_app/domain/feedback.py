"""Build the optional checklist and validate a feedback message.

The app never sends feedback automatically. This module only prepares the
payload; the dialog and the HTTP client are separate so the local-only flow
stays testable. Serials, IP addresses, IMEI and MAC addresses are never added
to the checklist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import ProbeData

FEEDBACK_ENDPOINT = "https://cleanyourphone-feedback.subtitleme.workers.dev"
FEEDBACK_KINDS = ("feedback", "bug", "profile")
MAX_MESSAGE = 4000
MAX_CHECKLIST = 6000
MAX_CONTACT = 200


@dataclass(frozen=True)
class FeedbackPayload:
    kind: str
    message: str
    checklist: str
    contact: str = ""
    app_version: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "message": self.message,
            "checklist": self.checklist,
            "contact": self.contact,
            "app_version": self.app_version,
            "website": "",
        }


def build_checklist(
    probe: ProbeData | None,
    profile_id: str | None = None,
    packages: Iterable[str] = (),
    verification: str = "device",
) -> str:
    """Return a plain-text checklist without device identifiers."""
    lines = ["CleanYourPhone checklist"]
    if probe is None:
        lines.extend(
            [
                "Phone: (not connected)",
                "Android:",
                "Build:",
                "Fingerprint:",
                "Profile:",
                "Packages:",
            ]
        )
        return "\n".join(lines)

    model = " ".join(part for part in (probe.brand, probe.model) if part).strip()
    lines.extend(
        [
            f"Phone: {model} ({probe.device})" if probe.device else f"Phone: {model}",
            f"Android: {probe.android} (SDK {probe.sdk})",
            f"Build: {probe.build}",
            f"Fingerprint: {probe.fingerprint}",
            f"Profile: {profile_id or 'none'}",
            f"Verification: {verification}",
        ]
    )
    selected = tuple(dict.fromkeys(packages))
    if selected:
        lines.append("Packages: " + ", ".join(selected[:50]))
    return "\n".join(lines)


def validate_feedback(
    *,
    kind: str,
    message: str,
    checklist: str,
    contact: str,
) -> str | None:
    """Return an i18n key for the first problem, or ``None`` when valid."""
    if kind not in FEEDBACK_KINDS:
        return "feedback.invalid_kind"
    if not isinstance(message, str) or not isinstance(checklist, str):
        return "feedback.invalid"
    if not message.strip() and not checklist.strip():
        return "feedback.empty"
    if len(message) > MAX_MESSAGE:
        return "feedback.message_too_long"
    if len(checklist) > MAX_CHECKLIST:
        return "feedback.checklist_too_long"
    if len(contact) > MAX_CONTACT:
        return "feedback.contact_too_long"
    return None


def feedback_payload(
    *,
    kind: str,
    message: str,
    checklist: str,
    contact: str = "",
    app_version: str = "",
) -> FeedbackPayload:
    """Build a payload after the caller has validated it."""
    return FeedbackPayload(
        kind=kind.strip().lower(),
        message=message.strip(),
        checklist=checklist.strip(),
        contact=contact.strip(),
        app_version=app_version.strip(),
    )


__all__ = [
    "FEEDBACK_ENDPOINT",
    "FEEDBACK_KINDS",
    "MAX_CHECKLIST",
    "MAX_CONTACT",
    "MAX_MESSAGE",
    "FeedbackPayload",
    "build_checklist",
    "feedback_payload",
    "validate_feedback",
]
