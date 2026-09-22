"""Runtime configuration: one immutable ``Settings`` object read from the environment.

Every tunable the adapters and the domain need (endpoints, User-Agent, timeouts, cache
policy, reliability thresholds) lives here so nothing is hard-coded across modules and every
value can be overridden with a ``WIKI_INTEREST_*`` environment variable. The module is a leaf:
it imports the domain for the threshold value object but never an adapter, so adapters can
depend on it without cycles.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from wiki_interest import __version__
from wiki_interest.domain.models import ReliabilityThresholds

__all__ = ["Settings", "default_user_agent", "skill_root"]

_SECONDS_PER_DAY = 86_400
_RESOLUTION_TTL_DAYS = 7
_PROJECT_URL = "https://github.com/b-ark/wiki-interest"
_DEFAULT_THRESHOLDS = ReliabilityThresholds()


def skill_root() -> Path:
    """Return the skill directory (the one containing ``SKILL.md`` and ``pyproject.toml``).

    Derived from the package location rather than the working directory because the agent
    runs the scripts from arbitrary folders; the cache and run bundles must still land inside
    the skill directory, which is git-ignored for them.
    """
    return Path(__file__).resolve().parent.parent


def default_user_agent() -> str:
    """Build the User-Agent Wikimedia's policy asks for: tool name, version and a contact URL.

    Wikimedia rejects or throttles generic client strings; see
    https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy.
    The project URL doubles as the contact channel.
    """
    return f"wiki-interest/{__version__} ({_PROJECT_URL})"


def _default_cache_path() -> Path:
    return skill_root() / ".cache" / "http.sqlite"


class Settings(BaseSettings):
    """All tunables, overridable with ``WIKI_INTEREST_<FIELD>`` environment variables.

    The reliability thresholds are flat fields (``WIKI_INTEREST_MIN_PERIODS_OK=18``) so they
    can be tuned per run without a config file; :meth:`reliability_thresholds` packs them
    into the domain value object.

    Attributes:
        user_agent: Sent with every request; must identify the tool and give a contact.
        pageviews_base_url: Wikimedia REST base (Pageviews API lives under ``/metrics``).
        wikidata_api_url: MediaWiki Action API endpoint of Wikidata.
        http_timeout_s: Per-request timeout; the Pageviews API can be slow on multi-year daily
            ranges, so this is generous.
        max_retries: Retries after the first attempt for transient failures (timeouts, 429,
            5xx); the total number of attempts is ``max_retries + 1``.
        max_concurrency: Upper bound on parallel requests. Wikimedia tolerates ~100 req/s; we
            stay far below to be a good citizen and to avoid 429s that would only slow us down.
        open_period_ttl_s: Cache TTL for series whose last bucket is in the current month; that
            data is still being written upstream and must be refreshed daily.
        closed_period_ttl_s: Cache TTL for series entirely in past months. ``None`` means never
            expires: the Pageviews API does not restate closed months.
        resolution_ttl_s: Cache TTL for Wikidata and MediaWiki lookups (labels, sitelinks,
            redirects, links); they change rarely but do change.
        cache_path: SQLite file for the HTTP cache; parent directories are created on demand.
    """

    model_config = SettingsConfigDict(env_prefix="WIKI_INTEREST_", frozen=True)

    user_agent: str = Field(default_factory=default_user_agent)
    pageviews_base_url: str = "https://wikimedia.org/api/rest_v1"
    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"
    http_timeout_s: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=5, ge=0)
    max_concurrency: int = Field(default=8, ge=1)
    open_period_ttl_s: int = Field(default=_SECONDS_PER_DAY, ge=0)
    closed_period_ttl_s: int | None = Field(default=None, ge=0)
    resolution_ttl_s: int = Field(default=_RESOLUTION_TTL_DAYS * _SECONDS_PER_DAY, ge=0)
    cache_path: Path = Field(default_factory=_default_cache_path)

    # Reliability thresholds; defaults come from the domain so there is one source of truth.
    min_periods_ok: int = Field(default=_DEFAULT_THRESHOLDS.min_periods_ok, ge=1)
    min_periods_warn: int = Field(default=_DEFAULT_THRESHOLDS.min_periods_warn, ge=1)
    completeness_ok: float = Field(default=_DEFAULT_THRESHOLDS.completeness_ok, ge=0, le=1)
    completeness_warn: float = Field(default=_DEFAULT_THRESHOLDS.completeness_warn, ge=0, le=1)
    spike_share_warn: float = Field(default=_DEFAULT_THRESHOLDS.spike_share_warn, ge=0, le=1)
    spike_share_fail: float = Field(default=_DEFAULT_THRESHOLDS.spike_share_fail, ge=0, le=1)
    trend_p_value: float = Field(default=_DEFAULT_THRESHOLDS.trend_p_value, gt=0, lt=1)
    automated_share_warn: float = Field(
        default=_DEFAULT_THRESHOLDS.automated_share_warn, ge=0, le=1
    )
    min_views_avg: float = Field(default=_DEFAULT_THRESHOLDS.min_views_avg, ge=0)
    search_fallback_warns: bool = _DEFAULT_THRESHOLDS.search_fallback_warns

    def reliability_thresholds(self) -> ReliabilityThresholds:
        """Pack the flat threshold fields into the domain value object."""
        return ReliabilityThresholds(
            min_periods_ok=self.min_periods_ok,
            min_periods_warn=self.min_periods_warn,
            completeness_ok=self.completeness_ok,
            completeness_warn=self.completeness_warn,
            spike_share_warn=self.spike_share_warn,
            spike_share_fail=self.spike_share_fail,
            trend_p_value=self.trend_p_value,
            automated_share_warn=self.automated_share_warn,
            min_views_avg=self.min_views_avg,
            search_fallback_warns=self.search_fallback_warns,
        )
