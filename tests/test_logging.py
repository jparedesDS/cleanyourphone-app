import logging
from pathlib import Path

from cleanyourphone_app.services.logging import (
    RedactionFilter,
    configure_logging,
    default_log_dir,
    default_log_path,
    redact,
)


def test_redacts_serial_code_and_ip():
    text = "serial R58M123456 code 123456 ip 192.168.1.42"
    assert "R58M123456" not in redact(text)
    assert "123456" not in redact(text)
    assert "192.168.1.42" not in redact(text)


def test_redacts_package_ids():
    text = "disable com.google.android.apps.wellbeing and com.example.secret"
    result = redact(text)
    assert "com.google.android.apps.wellbeing" not in result
    assert "com.example.secret" not in result
    assert result.count("[redacted]") == 2


def test_redacts_wireless_endpoints_with_port():
    result = redact("connected to 192.168.1.42:37123")
    assert "192.168.1.42" not in result
    assert "37123" not in result


def test_redacts_adb_and_emulator_serials():
    result = redact("adb-3A1B2C4D-QWERTY emulator-5554")
    assert "adb-3A1B2C4D-QWERTY" not in result
    assert "emulator-5554" not in result


def test_leaves_ordinary_text_and_versions_alone():
    text = "ADB 37.0.1 on Android 14; model SM-S918B"
    assert redact(text) == text


def test_does_not_redact_logger_names():
    text = "cleanyourphone_app.ui.pages.check"
    assert redact(text) == text


def test_default_log_dir_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_log_dir() == tmp_path / "CleanYourPhone" / "logs"
    assert default_log_path() == tmp_path / "CleanYourPhone" / "logs" / "app.log"


def test_default_log_dir_falls_back_to_the_home_directory(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert default_log_dir() == Path.home() / ".cleanyourphone" / "logs"


def test_redaction_filter_scrubs_log_records():
    record = logging.LogRecord(
        name="cleanyourphone_app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="serial %s code %s",
        args=("R58M123456", "123456"),
        exc_info=None,
    )
    assert RedactionFilter().filter(record) is True
    assert "R58M123456" not in record.getMessage()
    assert "123456" not in record.getMessage()


def _logger():
    return logging.getLogger("cleanyourphone_app")


def _flush_logger():
    for handler in _logger().handlers:
        handler.flush()


def test_configure_logging_writes_a_redacted_log(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    assert configure_logging(log_path) == log_path
    _logger().info(
        "serial R58M123456 code 123456 ip 192.168.1.42 package com.example.secret"
    )
    _flush_logger()

    text = log_path.read_text(encoding="utf-8")
    assert "R58M123456" not in text
    assert "123456" not in text
    assert "192.168.1.42" not in text
    assert "com.example.secret" not in text
    assert "[redacted]" in text


def test_configure_logging_redacts_format_arguments(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    configure_logging(log_path)
    _logger().warning("paired %s at %s", "R58M123456", "192.168.1.42")
    _flush_logger()

    text = log_path.read_text(encoding="utf-8")
    assert "R58M123456" not in text
    assert "192.168.1.42" not in text


def test_configure_logging_redacts_exception_text(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    configure_logging(log_path)
    try:
        raise RuntimeError("device R58M123456 at 192.168.1.42")
    except RuntimeError:
        _logger().exception("connection failed")
    _flush_logger()

    text = log_path.read_text(encoding="utf-8")
    assert "R58M123456" not in text
    assert "192.168.1.42" not in text


def test_configure_logging_replaces_its_own_handlers(tmp_path):
    configure_logging(tmp_path / "logs" / "app.log")
    first = len(_logger().handlers)
    configure_logging(tmp_path / "logs" / "app.log")
    assert len(_logger().handlers) == first


def test_configure_logging_uses_a_rotating_handler(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    configure_logging(log_path, max_bytes=1024, backup_count=2)
    handlers = [
        handler
        for handler in _logger().handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    ]
    assert len(handlers) == 1
    handler = handlers[0]
    assert handler.maxBytes == 1024
    assert handler.backupCount == 2


def test_configure_logging_rotates_the_file(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    configure_logging(log_path, max_bytes=64, backup_count=2)
    for _ in range(20):
        _logger().info("a line long enough to force a rotation")
    _flush_logger()

    assert log_path.is_file()
    assert (tmp_path / "logs" / "app.log.1").is_file()
