"""Composition root wiring."""

from __future__ import annotations

from pathlib import Path

from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import MediaWikiApi
from wiki_interest.adapters.wikidata import WikidataApi
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews
from wiki_interest.cli.container import Container
from wiki_interest.config import Settings
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.domain.models import Access, Agent


def _request(**overrides: object) -> AnalysisRequest:
    data: dict[str, object] = {
        "question_type": "assess",
        "topics": [{"query": "astronomy"}],
        "projects": ["uk"],
    }
    data.update(overrides)
    return AnalysisRequest.model_validate(data)


def test_build_wires_real_adapters_with_in_memory_cache() -> None:
    with Container.build(Settings(), persistent_cache=False) as container:
        assert isinstance(container.http, HttpJsonClient)
        assert isinstance(container.pageviews, WikimediaRestPageviews)
        assert isinstance(container.wikidata, WikidataApi)
        assert isinstance(container.mediawiki, MediaWikiApi)
        assert len(container.closeables) == 1
    assert container.closeables == []


def test_build_with_persistent_cache_creates_the_file_and_closes_it(tmp_path: Path) -> None:
    settings = Settings(cache_path=tmp_path / "cache" / "http.sqlite")
    container = Container.build(settings, persistent_cache=True)
    assert len(container.closeables) == 2
    container.close()
    container.close()  # idempotent
    assert (tmp_path / "cache" / "http.sqlite").exists()


def test_loader_and_analysis_settings_follow_the_request() -> None:
    settings = Settings(max_concurrency=3, trend_p_value=0.01)
    with Container.build(settings, persistent_cache=False) as container:
        request = _request(agent="all-agents", access="desktop", normalization="absolute")
        loader = container.loader(request)
        assert loader._settings.agent is Agent.ALL
        assert loader._settings.access is Access.DESKTOP
        assert loader._settings.max_workers == 3
        analysis = container.analysis_settings(request)
        assert analysis.normalise is False
        assert analysis.metrics.alpha == 0.01
        assert container.resolver() is not None
