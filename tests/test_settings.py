import json
from pathlib import Path

from cleanyourphone_app.services.settings import Settings


def test_settings_round_trip(tmp_path):
    settings = Settings.load(tmp_path / "settings.json")
    settings.language = "es"
    settings.adb_path = "C:/tools/adb.exe"
    settings.save()
    loaded = Settings.load(tmp_path / "settings.json")
    assert loaded.language == "es"
    assert loaded.adb_path == "C:/tools/adb.exe"


def test_default_path_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert Settings.default_path() == tmp_path / "CleanYourPhone" / "settings.json"


def test_default_path_falls_back_to_the_home_directory(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert Settings.default_path() == Path.home() / ".cleanyourphone" / "settings.json"


def test_missing_file_returns_defaults(tmp_path):
    settings = Settings.load(tmp_path / "missing.json")
    assert settings.language == ""
    assert settings.adb_path is None
    assert settings.path == tmp_path / "missing.json"


def test_save_creates_the_parent_directory(tmp_path):
    path = tmp_path / "nested" / "CleanYourPhone" / "settings.json"
    Settings.load(path).save()
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "language": "",
        "adb_path": None,
    }


def test_malformed_json_returns_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    settings = Settings.load(path)
    assert settings.language == ""
    assert settings.adb_path is None


def test_unknown_language_is_ignored_on_load(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "fr", "adb_path": "   "}), encoding="utf-8")
    settings = Settings.load(path)
    assert settings.language == ""
    assert settings.adb_path is None


def test_saved_language_is_validated(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings.load(path)
    settings.language = "fr"
    settings.save()
    assert Settings.load(path).language == ""


def test_in_memory_settings_do_not_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings.in_memory(language="es", adb_path="C:/tools/adb.exe")
    settings.save()
    assert list(tmp_path.iterdir()) == []
    assert settings.language == "es"
    assert settings.adb_path == "C:/tools/adb.exe"


def test_non_object_json_returns_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[]", encoding="utf-8")
    settings = Settings.load(path)
    assert settings.language == ""
    assert settings.adb_path is None
