"""Local rotating logs with redaction for every identifier the app may see.

Logs stay under ``%LOCALAPPDATA%\\CleanYourPhone\\logs\\``. Before a record is
written, serial-like tokens, six-digit pairing codes, IPv4 addresses/endpoints
and package ids are replaced with ``[redacted]``. The formatter redacts the
final text as well so tracebacks cannot leak a value.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
from pathlib import Path

LOGGER_NAME = "cleanyourphone_app"
REDACTED = "[redacted]"
LOG_FILE = "app.log"
DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_BACKUP_COUNT = 3

_OCTET = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
_IPV4_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9.])(?:{_OCTET}\.){{3}}{_OCTET}"
    r"(?::[0-9]{1,5})?(?![A-Za-z0-9.])"
)
_PACKAGE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.$])"
    r"(?:com|org|net|io|me|tv|app|dev|edu|gov|android|xyz)"
    r"(?:\.[A-Za-z0-9_$]+)+"
    r"(?![A-Za-z0-9_.$])"
)
_EMULATOR_SERIAL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])emulator-[0-9]+(?![A-Za-z0-9_-])"
)
_ADB_SERIAL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])adb-[A-Za-z0-9_-]+(?![A-Za-z0-9_-])"
)
_SERIAL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?=[A-Za-z0-9]{8,}(?![A-Za-z0-9]))"
    r"(?=[A-Za-z0-9]*[A-Za-z])"
    r"(?=[A-Za-z0-9]*[0-9])"
    r"[A-Za-z0-9]+"
    r"(?![A-Za-z0-9])"
)
_LONG_NUMBER_PATTERN = re.compile(r"(?<![0-9])[0-9]{8,}(?![0-9])")
_PAIRING_CODE_PATTERN = re.compile(r"(?<![0-9])[0-9]{6}(?![0-9])")


def redact(text: str) -> str:
    """Return *text* with serials, pairing codes, IPs and package ids hidden."""
    if not isinstance(text, str):
        text = str(text)
    for pattern in (
        _IPV4_PATTERN,
        _PACKAGE_PATTERN,
        _EMULATOR_SERIAL_PATTERN,
        _ADB_SERIAL_PATTERN,
        _SERIAL_PATTERN,
        _LONG_NUMBER_PATTERN,
        _PAIRING_CODE_PATTERN,
    ):
        text = pattern.sub(REDACTED, text)
    return text


class RedactionFilter(logging.Filter):
    """Scrub every record before any handler formats it."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a bad record must never break logging
            message = str(record.msg)
        record.msg = redact(message)
        record.args = ()
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True


class RedactingFormatter(logging.Formatter):
    """Redact the fully formatted line, including exception tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def default_log_dir(local_app_data: str | Path | None = None) -> Path:
    if local_app_data is not None:
        return Path(local_app_data) / "CleanYourPhone" / "logs"
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "CleanYourPhone" / "logs"
    return Path.home() / ".cleanyourphone" / "logs"


def default_log_path(local_app_data: str | Path | None = None) -> Path:
    return default_log_dir(local_app_data) / LOG_FILE


def configure_logging(
    path: str | Path | None = None,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    level: int | str = logging.INFO,
) -> Path:
    """Attach a redacted rotating file handler and return the log file path."""
    target = Path(path) if path is not None else default_log_path()
    if target.is_dir():
        target = target / LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, "_cleanyourphone_handler", False):
            logger.removeHandler(handler)
            handler.close()

    handler = logging.handlers.RotatingFileHandler(
        target,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(
        RedactingFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RedactionFilter())
    handler._cleanyourphone_handler = True  # type: ignore[attr-defined]

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return target
