import json
from pathlib import Path

import pytest

from cleanyourphone_app.i18n.translator import Translator

CATALOG_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "cleanyourphone_app" / "i18n"
)


def test_translation_keys_match():
    en = json.loads((CATALOG_DIR / "en.json").read_text(encoding="utf-8"))
    es = json.loads((CATALOG_DIR / "es.json").read_text(encoding="utf-8"))
    assert en.keys() == es.keys()


def test_spanish_copy_uses_desactivar_not_quitar():
    text = (
        Path("src/cleanyourphone_app/i18n/es.json").read_text(encoding="utf-8").lower()
    )
    assert "desactivar" in text
    assert "quitar" not in text


def test_spanish_copy_never_says_uninstall():
    text = (CATALOG_DIR / "es.json").read_text(encoding="utf-8").lower()
    assert "desinstalar" not in text


def test_spanish_default_when_system_is_spanish():
    assert Translator.for_system_language("es-ES").language == "es"


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("es-ES", "es"),
        ("es_MX", "es"),
        ("ES", "es"),
        ("en-US", "en"),
        ("en_GB", "en"),
        ("fr-FR", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_system_language_is_normalized(locale, expected):
    assert Translator.for_system_language(locale).language == expected


def test_translator_returns_spanish_copy():
    translator = Translator("es")
    assert translator.tr("step.done") == "Listo"
    assert translator.tr("welcome.title") == "Conecta tu móvil"


def test_translator_formats_placeholders():
    assert Translator("es").tr("review.disable_n", count=7) == "Desactivar 7 apps"
    assert Translator("en").tr("review.disable_n", count=7) == "Disable 7 apps"


def test_unknown_language_falls_back_to_english():
    translator = Translator("fr")
    assert translator.language == "en"
    assert translator.tr("step.done") == "Done"


def test_missing_spanish_key_falls_back_to_english():
    translator = Translator(
        "es",
        catalogs={
            "en": {"only.in.english": "English copy"},
            "es": {},
        },
    )
    assert translator.tr("only.in.english") == "English copy"


def test_missing_key_returns_the_key():
    assert Translator("es").tr("not.a.real.key") == "not.a.real.key"


def test_formatting_a_missing_placeholder_does_not_crash():
    translator = Translator("en", catalogs={"en": {"hello": "Hello {name}"}, "es": {}})
    assert translator.tr("hello") == "Hello {name}"


def test_set_language_switches_catalogs():
    translator = Translator("en")
    assert translator.set_language("es") == "es"
    assert translator.language == "es"
    assert translator.tr("step.done") == "Listo"
    assert translator.set_language("fr") == "en"


@pytest.mark.parametrize("language", ["en", "es"])
def test_catalogs_are_non_empty_json_objects_of_text(language):
    catalog = json.loads((CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))
    assert isinstance(catalog, dict)
    assert catalog
    for key, value in catalog.items():
        assert isinstance(key, str) and key
        assert isinstance(value, str) and value.strip()
