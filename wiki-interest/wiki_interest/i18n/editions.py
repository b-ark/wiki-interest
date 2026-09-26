"""How the reports name a language edition, in English, Russian and Ukrainian.

Two forms per edition: the name ("російська Вікіпедія") and the place ("у російській
Вікіпедії"), so a template never has to decline a name it is given. Keys are
``edition.name.<code>`` and ``edition.in.<code>``; the English forms are the catalog's, the
others are written labels (:mod:`wiki_interest.i18n.ru`, :mod:`wiki_interest.i18n.uk`).
Codes without a form here fall back to the English one, which the agent translates.
"""

# ruff: noqa: RUF001, RUF002  -- the names are Cyrillic on purpose.

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["EN", "RU", "UK"]

_ENGLISH: Mapping[str, str] = {
    "ar": "Arabic", "bg": "Bulgarian", "ca": "Catalan", "cs": "Czech", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "eo": "Esperanto", "es": "Spanish",
    "et": "Estonian", "fa": "Persian", "fi": "Finnish", "fr": "French", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian", "it": "Italian",
    "ja": "Japanese", "kk": "Kazakh", "ko": "Korean", "lt": "Lithuanian", "lv": "Latvian",
    "nl": "Dutch", "no": "Norwegian", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian", "sv": "Swedish",
    "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese", "zh": "Chinese",
}  # fmt: skip
"""The same names as the observations use (``edition_name``)."""

_UK_ADJECTIVES: Mapping[str, str] = {
    "ar": "арабськ", "bg": "болгарськ", "ca": "каталанськ", "cs": "чеськ", "da": "данськ",
    "de": "німецьк", "el": "грецьк", "en": "англійськ", "es": "іспанськ", "et": "естонськ",
    "fa": "перськ", "fi": "фінськ", "fr": "французьк", "hr": "хорватськ", "hu": "угорськ",
    "id": "індонезійськ", "it": "італійськ", "ja": "японськ", "kk": "казахськ",
    "ko": "корейськ", "lt": "литовськ", "lv": "латиськ", "nl": "нідерландськ",
    "no": "норвезьк", "pl": "польськ", "pt": "португальськ", "ro": "румунськ",
    "ru": "російськ", "sk": "словацьк", "sl": "словенськ", "sr": "сербськ", "sv": "шведськ",
    "th": "тайськ", "tr": "турецьк", "uk": "українськ", "vi": "в'єтнамськ", "zh": "китайськ",
}  # fmt: skip
"""Adjective stems: ``+а Вікіпедія``, ``у +ій Вікіпедії``."""
_UK_PHRASES: Mapping[str, tuple[str, str]] = {
    "eo": ("Вікіпедія есперанто", "у Вікіпедії есперанто"),
    "he": ("Вікіпедія на івриті", "у Вікіпедії на івриті"),
    "hi": ("Вікіпедія гінді", "у Вікіпедії гінді"),
}

_RU_ADJECTIVES: Mapping[str, str] = {
    "ar": "арабск", "bg": "болгарск", "ca": "каталанск", "cs": "чешск", "da": "датск",
    "de": "немецк", "el": "греческ", "en": "английск", "es": "испанск", "et": "эстонск",
    "fa": "персидск", "fi": "финск", "fr": "французск", "hr": "хорватск", "hu": "венгерск",
    "id": "индонезийск", "it": "итальянск", "ja": "японск", "kk": "казахск", "ko": "корейск",
    "lt": "литовск", "lv": "латышск", "nl": "нидерландск", "no": "норвежск", "pl": "польск",
    "pt": "португальск", "ro": "румынск", "ru": "русск", "sk": "словацк", "sl": "словенск",
    "sr": "сербск", "sv": "шведск", "th": "тайск", "tr": "турецк", "uk": "украинск",
    "vi": "вьетнамск", "zh": "китайск",
}  # fmt: skip
"""Adjective stems: ``+ая Википедия``, ``в +ой Википедии``."""
_RU_PHRASES: Mapping[str, tuple[str, str]] = {
    "eo": ("Википедия на эсперанто", "в Википедии на эсперанто"),
    "he": ("Википедия на иврите", "в Википедии на иврите"),
    "hi": ("Википедия на хинди", "в Википедии на хинди"),
}
_UK_VOWELS = "аеєиіїоуюяaeiou"


def _uk(stem: str) -> tuple[str, str]:
    preposition = "в" if stem[0].lower() in _UK_VOWELS else "у"
    return f"{stem}а Вікіпедія", f"{preposition} {stem}ій Вікіпедії"


def _ru(stem: str) -> tuple[str, str]:
    preposition = "во" if stem.startswith("вь") else "в"
    return f"{stem}ая Википедия", f"{preposition} {stem}ой Википедии"


def _labels(forms: Mapping[str, tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for code, (name, place) in sorted(forms.items()):
        out[f"edition.name.{code}"] = name
        out[f"edition.in.{code}"] = place
    return out


EN: Mapping[str, str] = _labels(
    {code: (f"the {name} Wikipedia", f"in the {name} Wikipedia") for code, name in _ENGLISH.items()}
)
UK: Mapping[str, str] = _labels({**{c: _uk(s) for c, s in _UK_ADJECTIVES.items()}, **_UK_PHRASES})
RU: Mapping[str, str] = _labels({**{c: _ru(s) for c, s in _RU_ADJECTIVES.items()}, **_RU_PHRASES})
