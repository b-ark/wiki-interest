"""A realistic, fully populated :class:`AnalysisSummary` for renderer and pipeline tests.

The example mirrors the ``compare-fasting`` scenario: one topic ("intermittent fasting")
resolved in the Ukrainian and Czech editions, with a Polish edition added for ``rank`` where
the article was only found via search. Every optional section is filled so a renderer test
that forgets a section shows up as missing output, not as a silently skipped branch.
"""

# ruff: noqa: RUF001  -- Cyrillic prose and typographic dashes are intentional test data.

from __future__ import annotations

from datetime import UTC, datetime

from wiki_interest.contracts.charts import (
    ChartSeries,
    ChartSpec,
    ShareChange,
    ShareLine,
    ShareMark,
    ShareSegment,
    ShareYears,
)
from wiki_interest.contracts.request import AnalysisRequest, Period, QuestionType
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    ArticleOut,
    Artifacts,
    AssessmentOut,
    BundleOut,
    CandidateOut,
    CheckOut,
    Clarification,
    ComparisonRow,
    DecisionOut,
    EvidenceOut,
    FindingOut,
    MetricsOut,
    PointOut,
    Provenance,
    RankedRow,
    ReliabilityOut,
    SeriesOut,
    TopicResolutionOut,
    Verdict,
)
from wiki_interest.domain.assessment import EditionRelation, Momentum, RelativeSize, Robustness
from wiki_interest.domain.models import (
    ArticleRole,
    AudienceProfile,
    BundleStatus,
    CheckStatus,
    Granularity,
    ReliabilityLevel,
    ResolutionSource,
    TrendDirection,
)
from wiki_interest.i18n import Translator

__all__ = ["RUN_DIR", "example_summary"]

TOPIC_ID = "intermittent-fasting"
RUN_DIR = "/runs/fasting-uk-cs/20260922-120000-abcd"
PERIOD = Period.model_validate({"start": "2024-09", "end": "2026-08"})
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13)][8:32]

_TITLES = {
    "uk.wikipedia": "Інтервальне голодування",
    "cs.wikipedia": "Přerušovaný půst",
    "pl.wikipedia": "Post przerywany",
}

_PROSE: dict[str, dict[str, list[str]]] = {
    "en": {
        "headline": [
            "Interest in intermittent fasting is growing faster in Czech than in Ukrainian"
        ],
        "bullets": [
            "Czech views per million rose +32% year over year; Ukrainian +12%",
            "Both trends are statistically significant and not driven by news spikes",
        ],
        "limitations": [
            "Wikipedia interest is a signal to verify, not a forecast of product demand",
            "Two Czech months have no data; the Czech growth figure is less certain",
            "Only the main article is counted; related articles are shown as context",
        ],
        "next_steps": [
            "Extend the period to 36 months to check whether the growth is seasonal",
            "Add the article about 'Ketogenic diet' to the bundle to cover the adjacent topic",
        ],
    },
    "uk": {
        "headline": [
            "Інтерес до інтервального голодування зростає швидше в чеському розділі, "
            "ніж в українському"
        ],
        "bullets": [
            "Перегляди на мільйон у чеському розділі зросли на +32 % рік до року; "
            "в українському на +12 %",
            "Обидва тренди статистично значущі й не зумовлені новинними сплесками",
        ],
        "limitations": [
            "Інтерес у Вікіпедії — сигнал для перевірки, а не прогноз попиту на продукт",
            "За два місяці в чеському розділі немає даних; чеське зростання менш певне",
            "Рахується лише головна стаття; пов'язані статті показано як контекст",
        ],
        "next_steps": [
            "Розширити період до 36 місяців, щоб перевірити сезонність зростання",
            "Додати до зв'язки статтю «Кетогенна дієта», щоб охопити суміжну тему",
        ],
    },
    "ru": {
        "headline": [
            "Интерес к интервальному голоданию растёт быстрее в чешском разделе, чем в украинском"
        ],
        "bullets": [
            "Просмотры на миллион в чешском разделе выросли на +32 % год к году; "
            "в украинском на +12 %",
            "Оба тренда статистически значимы и не вызваны новостными всплесками",
        ],
        "limitations": [
            "Интерес в Википедии — сигнал для проверки, а не прогноз спроса на продукт",
            "За два месяца в чешском разделе нет данных; чешский рост менее надёжен",
        ],
        "next_steps": ["Расширить период до 36 месяцев, чтобы проверить сезонность роста"],
    },
    "pl": {
        "headline": [
            "Zainteresowanie postem przerywanym rośnie szybciej w edycji czeskiej niż ukraińskiej"
        ],
        "bullets": [
            "Odsłony na milion w edycji czeskiej wzrosły o +32 % rok do roku; "
            "w ukraińskiej o +12 %",
            "Oba trendy są istotne statystycznie i nie wynikają ze skoków newsowych",
        ],
        "limitations": [
            "Zainteresowanie w Wikipedii to sygnał do weryfikacji, nie prognoza popytu",
            "W edycji czeskiej brakuje danych za dwa miesiące; czeski wzrost jest mniej pewny",
        ],
        "next_steps": ["Wydłużyć okres do 36 miesięcy, by sprawdzić sezonowość wzrostu"],
    },
    "cs": {
        "headline": ["Zájem o přerušovaný půst roste rychleji v české edici než v ukrajinské"],
        "bullets": [
            "Zobrazení na milion v české edici vzrostla meziročně o +32 %; v ukrajinské o +12 %",
            "Oba trendy jsou statisticky významné a nejsou dány zpravodajskými špičkami",
        ],
        "limitations": [
            "Zájem na Wikipedii je signál k ověření, nikoli předpověď poptávky po produktu",
            "V české edici chybí data za dva měsíce; český růst je méně jistý",
        ],
        "next_steps": ["Prodloužit období na 36 měsíců a ověřit sezónnost růstu"],
    },
}


def example_summary(
    *,
    question_type: QuestionType = "compare",
    language: str = "en",
    with_clarification: bool = False,
) -> AnalysisSummary:
    """Build the shared example summary.

    Args:
        question_type: ``compare`` (uk + cs), ``assess`` (uk only) or ``rank`` (uk, pl, cs with
            ranking rows).
        language: Report language; section prose and check messages follow it.
        with_clarification: Return the ``needs_clarification`` variant instead (no analysis
            sections, a question and three Wikidata candidates).

    Returns:
        A validated summary that round-trips through JSON.
    """
    projects = _projects_for(question_type)
    request = AnalysisRequest.model_validate(
        {
            "question_type": question_type,
            "topics": [{"query": "intermittent fasting", "query_language": "en", "id": TOPIC_ID}],
            "projects": projects,
            "period": {"start": "2024-09", "end": "2026-08"},
            "report": {
                "language": language,
                "title": "Intermittent fasting: uk vs cs",
                "audience_note": "Nutrition app choosing the next localisation",
            },
            "session": "fasting-uk-cs",
        }
    )
    if with_clarification:
        return _clarification_summary(request, language)
    translator = Translator(language)
    prose = _PROSE.get(language, _PROSE["en"])
    analysed = [p for p in projects if p != "pl.wikipedia" or question_type == "rank"]
    return AnalysisSummary(
        status="ok",
        run_id="20260922-120000-abcd",
        session="fasting-uk-cs",
        request=request,
        period=PERIOD,
        resolution=[_resolution(projects)],
        series=[s for p in analysed for s in _series_for(p)],
        metrics=[m for p in analysed for m in _metrics_for(p)],
        reliability=[_reliability_for(p, translator) for p in analysed],
        comparison=[_comparison_row(p) for p in analysed],
        ranking=_ranking(projects) if question_type == "rank" else [],
        charts=_charts(analysed, translator),
        verdict=Verdict(headline=prose["headline"][0], bullets=prose["bullets"]),
        happening=prose["bullets"][:2],
        assessments=_assessments(analysed, translator),
        decision=_decision(analysed, translator),
        data_note=[
            translator.t(
                "report.data_line",
                items="; ".join(
                    [
                        translator.t("evidence.months", months="24"),
                        translator.t("evidence.spikes_ok"),
                    ]
                ),
            ),
            translator.t(
                "report.data_concerns",
                label="cs.wikipedia",
                items=translator.t("evidence.gaps", missing_months="2"),
            ),
        ]
        if len(analysed) > 1
        else [],
        findings=[
            FindingOut(
                kind="level_shift" if index == 0 else "recent",
                topic_id=TOPIC_ID,
                project="uk.wikipedia" if index == 0 else "cs.wikipedia",
                importance=0.8 - index / 10,
                text=text,
                params={"change": 0.4} if index == 0 else {"change": 0.32},
            )
            for index, text in enumerate(prose["bullets"])
        ],
        limitations=prose["limitations"][1:],
        general_limitations=prose["limitations"][:1],
        next_steps=prose["next_steps"],
        artifacts=Artifacts(
            run_dir=RUN_DIR,
            summary_json=f"{RUN_DIR}/summary.json",
            summary_md=f"{RUN_DIR}/summary.md",
            report_pdf=f"{RUN_DIR}/report.pdf",
            charts=[f"{RUN_DIR}/charts/{c.id}.png" for c in _charts(analysed, translator)],
        ),
        provenance=Provenance(
            code_version="0.1.0",
            generated_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
            data_through="2026-08",
            user_agent="wiki-interest/0.1.0 (mailto:test@example.org)",
            sources=[
                "https://wikimedia.org/api/rest_v1/metrics/pageviews/",
                "https://www.wikidata.org/w/api.php",
            ],
            request_count=14,
            cache_hits=9,
        ),
    )


def _projects_for(question_type: QuestionType) -> list[str]:
    if question_type == "assess":
        return ["uk.wikipedia"]
    if question_type == "rank":
        return ["uk.wikipedia", "pl.wikipedia", "cs.wikipedia"]
    return ["uk.wikipedia", "cs.wikipedia"]


def _clarification_summary(request: AnalysisRequest, language: str) -> AnalysisSummary:
    question = {
        "uk": "Яку сутність ви маєте на увазі під «intermittent fasting»?",
    }.get(language, 'Which entity do you mean by "intermittent fasting"?')
    return AnalysisSummary(
        status="needs_clarification",
        run_id="20260922-120000-clar",
        session="fasting-uk-cs",
        request=request,
        period=PERIOD,
        verdict=Verdict(headline=question),
        artifacts=Artifacts(
            run_dir=RUN_DIR,
            summary_json=f"{RUN_DIR}/summary.json",
            summary_md=f"{RUN_DIR}/summary.md",
        ),
        provenance=Provenance(
            code_version="0.1.0",
            generated_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
            data_through="2026-08",
            user_agent="wiki-interest/0.1.0 (mailto:test@example.org)",
            sources=["https://www.wikidata.org/w/api.php"],
            request_count=1,
        ),
        clarification=Clarification(
            topic_id=TOPIC_ID,
            query="intermittent fasting",
            question=question,
            candidates=[
                CandidateOut(qid="Q1666254", label="intermittent fasting", description="diet"),
                CandidateOut(qid="Q1201325", label="fasting", description="abstinence from food"),
                CandidateOut(
                    qid="Q99999999", label="Intermittent Fasting (film)", description=None
                ),
            ],
        ),
    )


def _resolution(projects: list[str]) -> TopicResolutionOut:
    bundles = []
    for project in projects:
        if project == "pl.wikipedia":
            bundles.append(
                BundleOut(
                    topic_id=TOPIC_ID,
                    project=project,
                    status=BundleStatus.FOUND_VIA_SEARCH,
                    article_count=1,
                    articles=[
                        ArticleOut(
                            title=_TITLES[project],
                            role=ArticleRole.MAIN,
                            source=ResolutionSource.SEARCH_FALLBACK,
                        )
                    ],
                )
            )
            continue
        articles = [
            ArticleOut(
                title=_TITLES[project],
                role=ArticleRole.MAIN,
                source=ResolutionSource.SITELINK,
                qid="Q1666254",
                redirects=["Інтервальний піст"] if project == "uk.wikipedia" else [],
            )
        ]
        bundles.append(
            BundleOut(
                topic_id=TOPIC_ID,
                project=project,
                status=BundleStatus.FOUND,
                articles=articles,
                article_count=len(articles),
                redirect_count=len(articles[0].redirects),
            )
        )
    return TopicResolutionOut(
        topic_id=TOPIC_ID,
        query="intermittent fasting",
        label="intermittent fasting",
        qid="Q1666254",
        bundles=bundles,
    )


_BASE_VIEWS = {"uk.wikipedia": 9000.0, "cs.wikipedia": 4200.0, "pl.wikipedia": 2600.0}
_MONTHLY_GROWTH = {"uk.wikipedia": 0.010, "cs.wikipedia": 0.024, "pl.wikipedia": -0.005}
_PROJECT_TOTAL_MILLIONS = {"uk.wikipedia": 105.0, "cs.wikipedia": 48.0, "pl.wikipedia": 260.0}
_MISSING = {"cs.wikipedia": {"2025-03", "2025-04"}}
_SPIKE_MONTH = "2025-01"
_SPIKE_FACTOR = 1.6


def _views(project: str, index: int, month: str) -> float | None:
    if month in _MISSING.get(project, set()):
        return None
    value = _BASE_VIEWS[project] * (1 + _MONTHLY_GROWTH[project]) ** index
    if project == "uk.wikipedia" and month == _SPIKE_MONTH:
        value *= _SPIKE_FACTOR
    return round(value, 1)


def _series_for(project: str) -> list[SeriesOut]:
    points = []
    for index, month in enumerate(MONTHS):
        views = _views(project, index, month)
        per_million = None if views is None else round(views / _PROJECT_TOTAL_MILLIONS[project], 2)
        points.append(
            PointOut(
                period=month,
                views=views,
                per_million=per_million,
                edition_views=_PROJECT_TOTAL_MILLIONS[project] * 1_000_000,
            )
        )
    return [
        SeriesOut(
            topic_id=TOPIC_ID,
            project=project,
            granularity=Granularity.MONTHLY,
            points=points,
        )
    ]


_GROWTH_YOY = {"uk.wikipedia": 0.12, "cs.wikipedia": 0.32, "pl.wikipedia": -0.06}
_P_VALUES = {"uk.wikipedia": 0.004, "cs.wikipedia": 0.011, "pl.wikipedia": 0.41}
_DIRECTIONS = {
    "uk.wikipedia": TrendDirection.RISING,
    "cs.wikipedia": TrendDirection.RISING,
    "pl.wikipedia": TrendDirection.FLAT,
}
_LEVELS = {
    "uk.wikipedia": ReliabilityLevel.HIGH,
    "cs.wikipedia": ReliabilityLevel.MEDIUM,
    "pl.wikipedia": ReliabilityLevel.LOW,
}


def _metrics_for(project: str) -> list[MetricsOut]:
    observed = [v for i, m in enumerate(MONTHS) if (v := _views(project, i, m)) is not None]
    views_avg = sum(observed) / len(observed)
    return [
        MetricsOut(
            topic_id=TOPIC_ID,
            project=project,
            periods=len(MONTHS),
            completeness=len(observed) / len(MONTHS),
            views_total=sum(observed),
            views_avg=views_avg,
            per_million_avg=views_avg / _PROJECT_TOTAL_MILLIONS[project],
            growth_yoy=_GROWTH_YOY[project],
            growth_halves=_GROWTH_YOY[project] * 0.6,
            slope_per_year=_GROWTH_YOY[project],
            trend_p_value=_P_VALUES[project],
            trend_direction=_DIRECTIONS[project],
            seasonality_strength=0.18,
            spike_share=0.08 if project == "uk.wikipedia" else None,
            volatility_cv=0.21,
            automated_share=0.05 if project != "pl.wikipedia" else None,
        )
    ]


def _check(
    translator: Translator, name: str, status: CheckStatus, key: str, **params: float | int | str
) -> CheckOut:
    return CheckOut(
        name=name,
        status=status,
        message=translator.t(key, **params),
        reason_key=key,
        params=dict(params),
    )


def _reliability_for(project: str, translator: Translator) -> ReliabilityOut:
    checks = [
        _check(translator, "window_length", CheckStatus.PASS, "window_length.ok", months=24),
        _check(
            translator,
            "trend",
            CheckStatus.INFO,
            "trend.significant",
            p_value=_P_VALUES[project],
            direction=str(_DIRECTIONS[project].value),
        ),
        _check(translator, "volume", CheckStatus.PASS, "volume.ok", views_avg=_BASE_VIEWS[project]),
    ]
    if project == "cs.wikipedia":
        checks.insert(
            1,
            _check(
                translator,
                "completeness",
                CheckStatus.WARN,
                "completeness.gaps",
                missing_months=2,
                share=2 / 24,
            ),
        )
        checks.append(_check(translator, "spikes", CheckStatus.INFO, "spikes.unavailable"))
    elif project == "pl.wikipedia":
        checks[1] = _check(
            translator,
            "trend",
            CheckStatus.WARN,
            "trend.not_significant",
            p_value=_P_VALUES[project],
        )
        checks.append(
            _check(
                translator,
                "resolution",
                CheckStatus.FAIL,
                "resolution.search_fallback",
                title=_TITLES[project],
            )
        )
        checks.append(_check(translator, "automated", CheckStatus.INFO, "automated.unavailable"))
    else:
        checks.append(_check(translator, "spikes", CheckStatus.PASS, "spikes.low", share=0.08))
        checks.append(
            _check(translator, "automated", CheckStatus.PASS, "automated.low", share=0.05)
        )
    return ReliabilityOut(topic_id=TOPIC_ID, project=project, level=_LEVELS[project], checks=checks)


def _comparison_row(project: str) -> ComparisonRow:
    metrics = _metrics_for(project)[0]
    return ComparisonRow(
        topic_id=TOPIC_ID,
        project=project,
        label=_TITLES[project],
        views_avg=metrics.views_avg,
        per_million_avg=metrics.per_million_avg,
        growth_yoy=metrics.growth_yoy,
        growth_halves=metrics.growth_halves,
        trend_direction=_DIRECTIONS[project],
        reliability=_LEVELS[project],
        note="2 months missing" if project == "cs.wikipedia" else None,
        index=100.0 if project == "uk.wikipedia" else 60.0,
        views_growth=_GROWTH_YOY[project] - 0.05,
        edition_growth=-0.05,
    )


_EDITION_GROWTH = -0.05


def _assessments(projects: list[str], translator: Translator) -> list[AssessmentOut]:
    """Size, momentum, edition and trust per audience, as the decision layer states them."""
    shares = {p: _metrics_for(p)[0].per_million_avg or 0.0 for p in projects}
    largest = max(shares.values())
    out = []
    for project in projects:
        metrics = _metrics_for(project)[0]
        growing = _DIRECTIONS[project] is TrendDirection.RISING
        trend = Momentum.GROWING if growing else Momentum.FLAT
        size: RelativeSize | None = None
        if len(projects) > 1:
            size = RelativeSize.LARGEST if shares[project] == largest else RelativeSize.SMALLER
        low = _LEVELS[project] is ReliabilityLevel.LOW
        scale = "single" if size is None else ("large" if size is RelativeSize.LARGEST else "small")
        outcome = "low_trust" if low else f"{scale}_{trend.value}"
        article = _GROWTH_YOY[project] - 0.05
        evidence = [
            EvidenceOut(text=translator.t("evidence.months", months="24")),
            EvidenceOut(text=translator.t("evidence.spikes_ok")),
        ]
        steady = Robustness.MIXED if project == "cs.wikipedia" else Robustness.CONFIRMED
        recent = translator.t(f"outcome.recent.{steady.value}")
        if project == "cs.wikipedia":
            evidence.insert(
                0,
                EvidenceOut(text=translator.t("evidence.gaps", missing_months="2"), concern=True),
            )
        out.append(
            AssessmentOut(
                topic_id=TOPIC_ID,
                project=project,
                label=project,
                measured=True,
                per_million=metrics.per_million_avg,
                views_avg=metrics.views_avg,
                size=size,
                momentum=trend,
                change=_GROWTH_YOY[project],
                basis="yoy",
                article_change=article,
                edition_change=_EDITION_GROWTH,
                share_change=_GROWTH_YOY[project],
                relation=EditionRelation.GAINING,
                relation_basis="yoy",
                recent_months=3,
                recent_article=0.1,
                recent_edition=0.08,
                recent_shift=0.02,
                robustness=steady,
                robustness_line=translator.t(
                    f"robustness.{steady.value}.{trend.value}",
                    label=project,
                    change=translator.percent(_GROWTH_YOY[project], signed=True),
                    basis=translator.t("basis.yoy"),
                    months="3",
                    article=translator.percent(0.1, signed=True),
                    edition=translator.percent(0.08, signed=True),
                ),
                confidence=_LEVELS[project],
                evidence=evidence,
                outcome=outcome,
                decision=translator.t(f"outcome.{outcome}", label=project, recent=recent),
                edition_line=translator.t(
                    "edition.gaining",
                    label=project,
                    article=translator.percent(article, signed=True),
                    edition=translator.percent(_EDITION_GROWTH, signed=True),
                ),
            )
        )
    return out


def _decision(projects: list[str], translator: Translator) -> DecisionOut:
    items = _assessments(projects, translator)
    lines = [a.decision for a in items] if len(items) > 1 else []
    if len(items) == 1:
        return DecisionOut(
            conclusion="single_growing", lines=lines, next_step=translator.t("next_step.confirm")
        )
    best = next(a for a in items if a.size == RelativeSize.LARGEST)
    return DecisionOut(
        conclusion="strong",
        candidate=best.label,
        lines=lines,
        next_step=translator.t("next_step.confirm_for", label=best.label),
    )


def _ranking(projects: list[str]) -> list[RankedRow]:
    scores = {"cs.wikipedia": 0.81, "uk.wikipedia": 0.74, "pl.wikipedia": 0.22}
    profiles = {
        "cs.wikipedia": AudienceProfile.GROWTH_MARKET,
        "uk.wikipedia": AudienceProfile.MATURE_MARKET,
        "pl.wikipedia": AudienceProfile.INSUFFICIENT_DATA,
    }
    ordered = sorted(projects, key=lambda p: -scores[p])
    return [
        RankedRow(
            rank=rank,
            topic_id=TOPIC_ID,
            project=project,
            label=_TITLES[project],
            score=scores[project],
            components={"growth": 0.9, "volume": 0.6, "stability": 0.8, "reliability": 0.7},
            profile=profiles[project],
            reliability=_LEVELS[project],
            rationale=f"growth {_GROWTH_YOY[project]:+.0%}, reliability {_LEVELS[project].value}",
        )
        for rank, project in enumerate(ordered, start=1)
    ]


def _charts(projects: list[str], translator: Translator) -> list[ChartSpec]:
    per_million_series = [
        ChartSeries(
            label=f"{_TITLES[p]} ({p})",
            x=MONTHS,
            y=[pt.per_million for pt in _series_for(p)[0].points],
        )
        for p in projects
    ]
    uk_points = _series_for("uk.wikipedia")[0].points
    uk_values = [pt.per_million for pt in uk_points]
    trend_y: list[float | None] = [round(85.7 + 0.9 * i, 2) for i in range(len(MONTHS))]
    codes = [p.split(".")[0] for p in projects]
    return [
        ChartSpec(
            id="intermittent-fasting-per-million",
            kind="lines",
            size="wide",
            title=translator.t("chart.share.title"),
            subtitle=translator.t("chart.share.subtitle"),
            y_label=translator.t("chart.axis_per_million"),
            series=per_million_series,
        ),
        ChartSpec(
            id="intermittent-fasting-growth",
            kind="grouped_bars",
            size="half",
            title=translator.t(
                "chart.scatter_title", metric=translator.t("metric.attention_share")
            ),
            y_label=translator.t("chart.axis_growth"),
            series=[
                ChartSeries(
                    label=translator.t("metric.article_views"),
                    x=codes,
                    y=[_GROWTH_YOY[p] * 100 for p in projects],
                ),
                ChartSeries(
                    label=translator.t("chart.share.legend_month"),
                    x=codes,
                    y=[-5.0 for _ in projects],
                ),
            ],
            reference_y=0.0,
            value_suffix="%",
        ),
        ChartSpec(
            id="intermittent-fasting-uk-trend",
            kind="trend",
            size="half",
            title=translator.t("chart.season_title"),
            y_label=translator.t("chart.axis_per_million"),
            series=[ChartSeries(label=_TITLES["uk.wikipedia"], x=MONTHS, y=uk_values)],
            trend_y=trend_y,
            highlight_x=[_SPIKE_MONTH],
        ),
    ]


def share_years_data(lines: int = 2) -> ShareYears:
    """The main chart's data: calendar years 2021–2025 and a partial 2026 per audience.

    The first line takes a step in 2023-08 and a burst in 2022-08 far above its other months.
    """
    months = [f"{y}-{m:02d}" for y in range(2021, 2027) for m in range(1, 13)][:68]
    out = []
    for n in range(lines):
        base = 20.0 - 5 * n
        values: list[float | None] = [
            base
            + (4.0 if month >= "2023-08" else 0.0)
            + (60.0 if n == 0 and month == "2022-08" else 0.0)
            for month in months
        ]
        values[5] = None  # a month without data
        years = [
            ShareSegment(
                year=year,
                start=f"{year}-01",
                end="2026-08" if year == 2026 else f"{year}-12",
                value=round(base + (4.0 if year >= 2024 else 0.0), 1),
                partial=year == 2026,
            )
            for year in range(2021, 2027)
        ]
        out.append(ShareLine(label=("uk", "cs", "pl")[n], x=months, y=values, years=years))
    return ShareYears(
        lines=out,
        marks=[
            ShareMark(kind="step", line=0, x="2023-08", y=24.0, observation="step:x/uk"),
            ShareMark(kind="spike", line=0, x="2022-08", y=80.0, observation="spike:x/uk"),
        ],
        changes=[
            ShareChange(label=line.label, article=-20.0 - n, edition=-7.0)
            for n, line in enumerate(out)
        ],
        changes_start="2025-09",
        changes_end="2026-08",
    )
