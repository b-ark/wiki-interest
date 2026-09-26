"""English catalog completeness and Translator behaviour.

Only English has a catalog. Any other report language gets the English templates with its own
number style, and the labels the agent translated are applied through ``Translator.override``.
"""

from datetime import date
from string import Formatter

import pytest

from wiki_interest.domain.models import ReliabilityLevel
from wiki_interest.i18n import CATALOGS, LABELS, SUPPORTED_LANGUAGES, Translator, en, style_for
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
]

LABEL_KEYS = [
    *[f"level.{v}" for v in ("high", "medium", "low")],
    *[f"direction.{v}" for v in ("rising", "falling", "flat", "unknown")],
    *[
        f"profile.{v}"
        for v in ("early_niche", "growth_market", "mature_market", "declining", "insufficient_data")
    ],
    *[f"bundle_status.{v}" for v in ("found", "found_via_search", "not_found")],
]

SECTION_KEYS = [
    "report.title_default",
    "report.sources",
    "report.period",
    "report.generated",
    "report.ranking_table",
    *[
        f"col.{v}"
        for v in (
            "topic",
            "project",
            "reliability",
            "rank",
            "score",
            "profile",
        )
    ],
    *[
        f"summary.{v}"
        for v in (
            "answer",
            "caveats",
            "refine",
            "artifacts",
            "clarification_needed",
            "bundles",
        )
    ],
    "chart.axis_per_million",
    "chart.axis_views",
    "chart.share.title",
    "chart.share.legend_year",
    "chart.audience.title",
    "chart.audience.subtitle",
    "chart.share.legend_recent",
    "report.footer_share",
    "report.footer_caveats",
    "chart.season_title",
    "report.vs_edition",
    "report.decision",
    "summary.decision",
    "report.robustness",
    "value.per_million",
]


NO_CATALOG = "uk"
"""A report language without a catalog: English templates, Ukrainian number style."""


def test_only_english_has_a_catalog() -> None:
    assert SUPPORTED_LANGUAGES == ("en",)
    assert set(CATALOGS) == {"en"}


@pytest.mark.parametrize("key", REASON_KEYS + LABEL_KEYS + SECTION_KEYS)
def test_required_key_exists_in_english(key: str) -> None:
    assert key in CATALOGS["en"]


def test_catalog_values_are_non_empty() -> None:
    for key, value in CATALOGS["en"].items():
        assert value.strip(), f"empty value for {key}"


@pytest.mark.parametrize("language", ["en", NO_CATALOG])
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
    }
    text = Translator(language).t(key, **params)
    assert "{" not in text, text


def test_share_is_rendered_as_whole_percent() -> None:
    text = Translator("en").t("spikes.notable", share=0.2349)
    assert "23%" in text


def test_a_share_in_a_template_reads_like_the_other_percentages() -> None:
    share = 0.234
    assert (
        Translator("en")
        .t("automated.low", share=share)
        .startswith(f"Wikimedia classified {format_percent(share, style_for('en'))} of the visits")
    )
    ukrainian = Translator("uk").t("automated.low", share=share)
    assert f"23{NARROW_NO_BREAK_SPACE}%" in ukrainian


def test_p_value_has_three_decimals() -> None:
    text = Translator("en").t("trend.not_significant", p_value=0.04567)
    assert "p = 0.046" in text


def test_direction_parameter_is_replaced_by_its_label() -> None:
    translator = Translator(NO_CATALOG)
    translator.override({"direction.rising": "зростає"})
    text = translator.t("trend.significant", p_value=0.01, direction="rising")
    assert "зростає" in text
    assert "rising" not in text


FINDING_PARAMS = {
    "label": "uk.wikipedia",
    "topic": "Astronomy",
    "article_change": "-12 %",
    "edition_change": "-5 %",
    "share_change": "-7 %",
    "basis": "last 12 months vs the 12 before",
    "start_month": "03.2025",
    "end_month": "05.2025",
    "change": "+40 %",
    "before": "12.3",
    "after": "17.2",
    "months": "14",
    "unit": "views/month",
    "start": "03.09.2024",
    "end": "05.09.2024",
    "peak_day": "03.09.2024",
    "peak_views": "401",
    "multiple": "4.8",
    "baseline": "83",
    "share": "2.4 %",
    "peak_month": "September",
    "peak": "+119 %",
    "trough_month": "June",
    "trough": "-41 %",
    "leader": "ru.wikipedia",
    "count": "3",
    "value": "39.3",
    "others": "uk.wikipedia 28.6",
    "labels": "uk.wikipedia",
    "largest": "ru.wikipedia",
    "measure": "The topic's share of attention",
    "parts": "falling in uk.wikipedia (-22 %)",
    "project": "uk.wikipedia",
    "projects": "pl.wikipedia",
    "views": "972",
    "article": "-36 %",
    "edition": "-22 %",
    "missing_months": "2",
    "metric": "Attention share",
    "subject": "The attention share of «chess»",
    "topics": "«chess»",
    "scope": "in both editions",
    "fastest": "fastest in uk.wikipedia",
    "recent": "; recent months confirm it",
    "reason": "the period is too short for a trend",
    "items": "uk -12 % (-5 %)",
    "what": 'the broader article "Post"',
    "title": "Post",
}


@pytest.mark.parametrize("language", ["en", NO_CATALOG])
def test_answer_and_finding_templates_format(language: str) -> None:
    translator = Translator(language)
    prefixes = (
        "finding.",
        "answer.",
        "outcome.",
        "edition.",
        "next_step.",
        "evidence.",
        "card.",
        "robustness.",
        "headline.",
        "happening.",
        "kpi.",
    )
    keys = [k for k in CATALOGS["en"] if k.startswith(prefixes)]
    assert len(keys) > 60
    for key in keys:
        text = translator.t(key, **FINDING_PARAMS)
        assert "{" not in text, (key, text)


@pytest.mark.parametrize("language", ["en", NO_CATALOG])
def test_dates_default_to_the_english_convention(language: str) -> None:
    translator = Translator(language)
    assert translator.date(date(2025, 3, 14)) == "2025-03-14"
    assert translator.month_year(date(2025, 3, 1)) == "2025-03"


def test_dates_follow_the_convention_the_agent_gave() -> None:
    translator = Translator(NO_CATALOG)
    translator.override(
        {
            "format.date": "{day:02d}.{month:02d}.{year}",
            "format.month_year": "{month:02d}.{year}",
        }
    )
    assert translator.date(date(2025, 3, 14)) == "14.03.2025"
    assert translator.month_year(date(2025, 3, 1)) == "03.2025"


def test_month_names_are_nominative() -> None:
    assert Translator("en").month_name(1) == "January"
    assert Translator("de").month_name(9) == "September"
    translator = Translator("de")
    translator.override({"month.9": "September (de)"})
    assert translator.month_name(9) == "September (de)"
    assert Translator("uk").month_name(9) == "вересень"


@pytest.mark.parametrize("language", sorted(LABELS))
def test_written_labels_mirror_the_english_keys_and_placeholders(language: str) -> None:
    for key, text in LABELS[language].items():
        assert key in en.MESSAGES, key
        assert _fields(text) == _fields(en.MESSAGES[key]), key


def test_written_labels_win_over_the_agents_and_are_not_asked_for() -> None:
    translator = Translator("uk")
    translator.override({"report.happening": "Що коїться"})
    assert translator.t("report.happening") == "Що відбувається"
    assert translator.translates("report.happening")
    assert not translator.has_catalog
    # What has no written label still falls back to English and is the agent's to translate.
    assert not translator.translates("summary.answer")
    assert translator.t("summary.answer") == "Answer"


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def test_thousands_separator_follows_report_locale() -> None:
    assert "12,346" in Translator("en").t("volume.ok", views_avg=12345.6)
    uk = Translator(NO_CATALOG).t("volume.ok", views_avg=12345.6)
    assert f"12{NARROW_NO_BREAK_SPACE}346" in uk


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


def test_language_without_a_catalog_uses_english_templates_and_its_own_numbers() -> None:
    translator = Translator(NO_CATALOG)
    assert (translator.requested, translator.language) == (NO_CATALOG, "en")
    assert not translator.has_catalog
    assert Translator("en").has_catalog
    assert translator.t("level.high") == "high"
    assert translator.has("level.high")
    assert translator.number(37.9, 1) == "37,9"


def test_override_takes_the_agent_translations_before_english() -> None:
    translator = Translator(NO_CATALOG)
    translator.override({"level.high": "висока", "no.such.key": "зайвий"})
    assert translator.t("level.high") == "висока"
    assert translator.t("level.low") == "low"
    assert translator.english("level.high") == "high"
    with pytest.raises(KeyError):  # an unknown key cannot be introduced through a translation
        translator.t("no.such.key")


def test_override_keeps_formatting_the_parameters() -> None:
    translator = Translator(NO_CATALOG)
    translator.override({"volume.ok": "Близько {views_avg:,.0f} переглядів на місяць"})
    text = translator.t("volume.ok", views_avg=12345.6)
    assert text == f"Близько 12{NARROW_NO_BREAK_SPACE}346 переглядів на місяць"


def test_recording_collects_the_keys_looked_up() -> None:
    translator = Translator(NO_CATALOG)
    with translator.recording() as used:
        translator.label("level", "high")
        translator.t("volume.ok", views_avg=1.0)
    translator.t("level.low")  # outside the block: not recorded
    assert used == {"level.high", "volume.ok"}


def test_label_accepts_enum_members_and_strings() -> None:
    translator = Translator("en")
    assert translator.label("level", ReliabilityLevel.HIGH) == "high"
    assert translator.label("level", "high") == "high"
    translator = Translator(NO_CATALOG)
    translator.override({"level.high": "висока"})
    assert translator.label("level", ReliabilityLevel.HIGH) == "висока"


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


def test_a_value_that_rounds_to_zero_has_no_sign() -> None:
    """ "-0 %" read as a fall (stage15)."""
    uk = Translator("uk")
    zero = f"0{NARROW_NO_BREAK_SPACE}%"
    assert uk.percent(-0.001, signed=True) == uk.percent(0.001, signed=True) == zero
    assert uk.number(-0.04, 1) == "0,0"
    assert uk.percent(0.006, signed=True) == f"+1{NARROW_NO_BREAK_SPACE}%"
