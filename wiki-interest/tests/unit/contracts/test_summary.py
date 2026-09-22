"""Shape and round-trip behaviour of summary.json."""

from datetime import UTC, datetime

from wiki_interest.contracts.charts import ChartSeries, ChartSpec
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    Artifacts,
    CheckOut,
    Provenance,
    ReliabilityOut,
    Verdict,
)
from wiki_interest.domain.models import CheckStatus, ReliabilityLevel


def _summary() -> AnalysisSummary:
    request = AnalysisRequest.model_validate(
        {"question_type": "assess", "topics": [{"query": "astronomy"}], "projects": ["uk"]}
    )
    return AnalysisSummary(
        status="ok",
        run_id="20260922-120000-abcd",
        session=None,
        request=request,
        period=Period.model_validate({"start": "2024-09", "end": "2026-08"}),
        reliability=[
            ReliabilityOut(
                topic_id="astronomy",
                project="uk.wikipedia",
                level=ReliabilityLevel.MEDIUM,
                checks=[
                    CheckOut(
                        name="window_length",
                        status=CheckStatus.PASS,
                        message="24 months of data",
                        reason_key="window_length.ok",
                        params={"months": 24},
                    )
                ],
            )
        ],
        charts=[
            ChartSpec(
                id="astronomy-uk-trend",
                kind="trend",
                title="Astronomy, uk.wikipedia",
                y_label="views per million",
                series=[ChartSeries(label="uk", x=["2024-09", "2024-10"], y=[1.0, None])],
            )
        ],
        verdict=Verdict(headline="Interest is flat", bullets=["No significant trend"]),
        artifacts=Artifacts(
            run_dir="/runs/x", summary_json="/runs/x/summary.json", summary_md="/runs/x/summary.md"
        ),
        provenance=Provenance(
            code_version="0.1.0",
            generated_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
            data_through="2026-08",
            user_agent="wiki-interest/0.1.0",
            sources=["https://wikimedia.org/api/rest_v1/"],
        ),
    )


def test_round_trips_through_json_with_enums_as_values() -> None:
    summary = _summary()
    payload = summary.model_dump_json()
    restored = AnalysisSummary.model_validate_json(payload)
    assert restored == summary
    assert '"level":"medium"' in payload
    assert '"status":"pass"' in payload


def test_period_is_serialised_as_year_month() -> None:
    data = _summary().model_dump(mode="json")
    assert data["period"] == {"start": "2024-09", "end": "2026-08"}


def test_json_schema_can_be_generated_for_documentation() -> None:
    schema = AnalysisSummary.model_json_schema()
    assert "AnalysisRequest" in schema["$defs"]
    assert "ChartSpec" in schema["$defs"]
