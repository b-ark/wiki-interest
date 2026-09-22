"""Settings defaults, environment overrides and immutability."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

import wiki_interest
from wiki_interest.config import RUNS_DIRNAME, Settings, default_user_agent, skill_root
from wiki_interest.domain.models import ReliabilityThresholds


def test_skill_root_is_the_directory_with_pyproject() -> None:
    assert (skill_root() / "pyproject.toml").is_file()
    assert (skill_root() / "SKILL.md").is_file()


def test_default_user_agent_names_tool_version_and_contact() -> None:
    agent = default_user_agent()
    assert agent.startswith(f"wiki-interest/{wiki_interest.__version__} (")
    assert "https://" in agent, "Wikimedia's UA policy requires a contact URL"


def test_defaults_are_sensible(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("WIKI_INTEREST_"):
            monkeypatch.delenv(name)
    settings = Settings()
    assert settings.user_agent == default_user_agent()
    assert settings.pageviews_base_url == "https://wikimedia.org/api/rest_v1"
    assert settings.wikidata_api_url == "https://www.wikidata.org/w/api.php"
    assert settings.http_timeout_s == 30.0
    assert settings.max_retries == 5
    assert settings.max_concurrency == 8
    assert settings.open_period_ttl_s == 86_400
    assert settings.closed_period_ttl_s is None
    assert settings.resolution_ttl_s == 7 * 86_400
    assert settings.cache_path == skill_root() / ".cache" / "http.sqlite"


def test_reliability_thresholds_default_to_domain_defaults() -> None:
    assert Settings().reliability_thresholds() == ReliabilityThresholds()


def test_environment_overrides_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WIKI_INTEREST_MAX_RETRIES", "1")
    monkeypatch.setenv("WIKI_INTEREST_CLOSED_PERIOD_TTL_S", "3600")
    monkeypatch.setenv("WIKI_INTEREST_MIN_PERIODS_OK", "18")
    monkeypatch.setenv("WIKI_INTEREST_SEARCH_FALLBACK_WARNS", "false")
    monkeypatch.setenv("WIKI_INTEREST_CACHE_PATH", str(tmp_path / "c.sqlite"))
    settings = Settings()
    assert settings.max_retries == 1
    assert settings.closed_period_ttl_s == 3600
    assert settings.cache_path == tmp_path / "c.sqlite"
    thresholds = settings.reliability_thresholds()
    assert thresholds.min_periods_ok == 18
    assert thresholds.search_fallback_warns is False


def test_settings_are_frozen() -> None:
    settings = Settings()
    with pytest.raises(ValidationError):
        settings.max_retries = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("MAX_RETRIES", "-1"),
        ("HTTP_TIMEOUT_S", "0"),
        ("COMPLETENESS_OK", "1.5"),
        ("MAX_CONCURRENCY", "0"),
    ],
)
def test_out_of_range_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    monkeypatch.setenv(f"WIKI_INTEREST_{field}", value)
    with pytest.raises(ValidationError):
        Settings()


def test_runs_are_written_to_the_working_directory_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert Settings().runs_dir == tmp_path / RUNS_DIRNAME
