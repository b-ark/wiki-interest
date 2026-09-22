"""Catalog completeness and Translator behaviour."""

import pytest

from wiki_interest.domain.models import ReliabilityLevel
from wiki_interest.i18n import CATALOGS, SUPPORTED_LANGUAGES, Translator, style_for
from wiki_interest.i18n.formatting import NARROW_NO_BREAK_SPACE, format_number, format_percent

REASON_KEYS = [
    "window_length.ok",
    "window_length.short",
    "window_length.too_short",
    "completeness.ok",
    "completeness.gaps",
    "completeness.sparse",
    "spikes.low",
    "spikes.notable",
    "spikes.dominant",
    "spikes.unavailable",
    "trend.significant",
    "trend.not_significant",
    "trend.unavailable",
    "resolution.sitelink",
    "resolution.search_fallback",
    "resolution.manual",
    "resolution.not_found",
    "automated.low",
    "automated.high",
    "automated.unavailable",
    "volume.ok",
    "volume.low",
    "bundle.consistent",
    "bundle.diverges",
]

LABEL_KEYS = [
    *[f"level.{v}" for v in ("high", "medium", "low")],
    *[f"status.{v}" for v in ("pass", "warn", "fail", "info")],
    *[f"direction.{v}" for v in ("rising", "falling", "flat", "unknown")],
    *[
        f"profile.{v}"
        for v in ("early_niche", "growth_market", "mature_market", "declining", "insufficient_data")
    ],
    *[f"bundle_status.{v}" for v in ("found", "found_via_search", "not_found")],
    *[
        f"source.{v}"
        for v in ("sitelink", "wikidata_relation", "lead_link", "search_fallback", "manual")
    ],
    *[f"role.{v}" for v in ("main", "related", "manual")],
    "unit.views",
    "unit.per_million",
]

SECTION_KEYS = [
    "report.title_default",
    "report.question",
    "report.key_numbers",
    "report.chart",
    "report.verdict",
    "report.reliability",
    "report.limitations",
    "report.next_steps",
    "report.sources",
    "report.period",
    "report.generated",
    "report.bundle_composition",
    "report.comparison_table",
    "report.ranking_table",
    *[
        f"col.{v}"
        for v in (
            "topic",
            "project",
            "views_avg",
            "per_million_avg",
            "growth_yoy",
            "growth_halves",
            "trend",
            "reliability",
            "rank",
            "score",
            "profile",
            "article",
            "weight",
            "source",
        )
    ],
    *[
        f"summary.{v}"
        for v in (
            "answer",
            "key_numbers",
            "trust",
            "caveats",
            "refine",
            "artifacts",
            "clarification_needed",
            "bundles",
        )
    ],
    "chart.axis_per_million",
    "chart.axis_views",
    "chart.footnote",
    "chart.growth_title",
    "chart.trend_title",
    "chart.compare_title",
]


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_every_catalog_has_exactly_the_english_keys(language: str) -> None:
    english = set(CATALOGS["en"])
    other = set(CATALOGS[language])
    assert other == english, (
        f"{language}: missing {sorted(english - other)}, extra {sorted(other - english)}"
    )


@pytest.mark.parametrize("key", REASON_KEYS + LABEL_KEYS + SECTION_KEYS)
def test_required_key_exists_in_english(key: str) -> None:
    assert key in CATALOGS["en"]


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_catalog_values_are_non_empty_and_translated(language: str) -> None:
    for key, value in CATALOGS[language].items():
        assert value.strip(), f"{language}: empty value for {key}"


@pytest.mark.parametrize("language", ["uk", "ru", "pl", "cs"])
def test_translations_differ_from_english_for_prose_keys(language: str) -> None:
    prose = [k for k in REASON_KEYS if k != "resolution.manual"] + ["report.title_default"]
    same = [k for k in prose if CATALOGS[language][k] == CATALOGS["en"][k]]
    assert not same, f"{language}: untranslated {same}"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
@pytest.mark.parametrize("key", REASON_KEYS)
def test_reason_templates_format_with_their_parameters(language: str, key: str) -> None:
    params = {
        "months": 24,
        "missing_months": 3,
        "share": 0.235,
        "p_value": 0.0123,
        "direction": "rising",
        "title": "Astronomie",
        "views_avg": 12345.6,
        "main_direction": "rising",
        "bundle_direction": "flat",
    }
    text = Translator(language).t(key, **params)
    assert "{" not in text, text


def test_share_is_rendered_as_whole_percent() -> None:
    text = Translator("en").t("spikes.notable", share=0.2349)
    assert "23%" in text


def test_p_value_has_three_decimals() -> None:
    text = Translator("en").t("trend.not_significant", p_value=0.04567)
    assert "p = 0.046" in text


def test_direction_parameter_is_localised() -> None:
    text = Translator("uk").t("trend.significant", p_value=0.01, direction="rising")
    assert "зростає" in text
    assert "rising" not in text


def test_bundle_directions_are_localised_in_diverges_message() -> None:
    text = Translator("ru").t("bundle.diverges", main_direction="rising", bundle_direction="flat")
    assert "растёт" in text
    assert "без изменений" in text


def test_thousands_separator_follows_report_locale() -> None:
    assert "12,346" in Translator("en").t("volume.ok", views_avg=12345.6)
    assert f"12{NARROW_NO_BREAK_SPACE}346" in Translator("uk").t("volume.ok", views_avg=12345.6)


def test_string_in_numeric_slot_does_not_crash() -> None:
    text = Translator("en").t("spikes.notable", share="n/a")
    assert "n/a" in text


def test_unknown_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match=r"no\.such\.key"):
        Translator("en").t("no.such.key")


def test_missing_parameter_raises_key_error() -> None:
    with pytest.raises(KeyError):
        Translator("en").t("window_length.ok")


def test_unsupported_language_falls_back_to_english() -> None:
    translator = Translator("xx")
    assert translator.language == "en"
    assert translator.t("level.high") == "high"


def test_key_missing_in_language_falls_back_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    translator = Translator("uk")
    monkeypatch.setattr(translator, "_catalog", {})
    assert translator.t("level.high") == "high"
    assert translator.has("level.high")


def test_label_accepts_enum_members_and_strings() -> None:
    translator = Translator("pl")
    assert translator.label("level", ReliabilityLevel.HIGH) == "wysoka"
    assert translator.label("level", "high") == "wysoka"


def test_number_and_percent_helpers_handle_none() -> None:
    translator = Translator("cs")
    assert translator.number(None) == "n/a"
    assert translator.percent(None) == "n/a"
    assert translator.number(1234.5, 1) == f"1{NARROW_NO_BREAK_SPACE}234,5"
    assert translator.percent(0.153, signed=True) == f"+15{NARROW_NO_BREAK_SPACE}%"
    assert Translator("en").percent(-0.153, signed=True) == "-15%"


def test_formatting_functions_are_locale_explicit() -> None:
    en = style_for("en")
    assert format_number(1234567.891, en, 2) == "1,234,567.89"
    assert format_percent(0.5, en) == "50%"
