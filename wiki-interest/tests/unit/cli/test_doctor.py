"""Doctor checks with fake gateways."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from fakes import FakeClock, FakeEntity, FakeMediaWiki, FakePage, FakePageviews, FakeWikidata
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.cli.app import app
from wiki_interest.cli.container import Container
from wiki_interest.cli.doctor import run_doctor
from wiki_interest.config import Settings
from wiki_interest.domain.models import Access, Agent, Series, WikiProject, Window
from wiki_interest.errors import UpstreamError

EN = WikiProject("en")


def _container(tmp_path: Path, *, healthy: bool = True) -> Container:
    settings = Settings(cache_path=tmp_path / "cache" / "http.sqlite")
    pageviews = FakePageviews()
    wikidata = FakeWikidata()
    mediawiki = FakeMediaWiki()
    if healthy:
        pageviews.set_aggregate(EN, {date(2026, 8, 1): 8.5e9})
        wikidata.add(FakeEntity("Q333", {"en": "astronomy"}))
        mediawiki.add_page(EN, FakePage("Astronomy", qid="Q333"))
    return Container(
        settings=settings,
        clock=FakeClock(date(2026, 9, 22)),
        http=HttpJsonClient(settings, InMemoryCache()),
        pageviews=pageviews,
        wikidata=wikidata,
        mediawiki=mediawiki,
    )


def test_healthy_environment_passes_every_check(tmp_path: Path) -> None:
    report = run_doctor(_container(tmp_path))
    assert report.ok, report.to_dict()
    names = [c.name for c in report.checks]
    assert names == [
        "python_version",
        "package",
        "cache_dir",
        "fonts",
        "pageviews_api",
        "wikidata_api",
        "mediawiki_api",
    ]
    assert "8,500,000,000" in report.checks[4].detail
    assert (tmp_path / "cache").is_dir()


def test_offline_skips_network_probes(tmp_path: Path) -> None:
    report = run_doctor(_container(tmp_path, healthy=False), online=False)
    assert report.ok
    assert len(report.checks) == 4


def test_unexpected_answers_are_reported_but_reachable(tmp_path: Path) -> None:
    report = run_doctor(_container(tmp_path, healthy=False))
    by_name = {c.name: c for c in report.checks}
    assert by_name["pageviews_api"].ok
    assert "no data yet" in by_name["pageviews_api"].detail
    assert by_name["wikidata_api"].ok
    assert "instead of Q333" in by_name["wikidata_api"].detail
    assert by_name["mediawiki_api"].ok
    assert "not found" in by_name["mediawiki_api"].detail


def test_upstream_failure_is_a_failed_check_with_the_hint(tmp_path: Path) -> None:
    class Down(FakePageviews):
        def aggregate(
            self, project: WikiProject, window: Window, *, access: Access, agent: Agent
        ) -> Series:
            raise UpstreamError("timeout", retryable=True, hint="check the network")

    container = _container(tmp_path)
    container.pageviews = Down()
    report = run_doctor(container)
    check = next(c for c in report.checks if c.name == "pageviews_api")
    assert not check.ok
    assert check.detail == "timeout (check the network)"
    assert not report.ok


def test_cli_doctor_offline_prints_json_and_exits_zero() -> None:
    result = CliRunner().invoke(app, ["doctor", "--offline"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert {c["name"] for c in payload["checks"]} == {
        "python_version",
        "package",
        "cache_dir",
        "fonts",
    }
