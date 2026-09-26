"""Runtime configuration: one immutable ``Settings`` object read from the environment.

Every tunable the adapters and the domain need (endpoints, User-Agent, timeouts, cache
policy, reliability thresholds) lives here so nothing is hard-coded across modules and every
value can be overridden with a ``WIKI_INTEREST_*`` environment variable. The module is a leaf:
it imports the domain for the threshold value object but never an adapter, so adapters can
depend on it without cycles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from wiki_interest import __version__
from wiki_interest.domain.assessment import AssessmentSettings
from wiki_interest.domain.models import ReliabilityThresholds
from wiki_interest.domain.monthly_anomalies import AnomalySettings
from wiki_interest.domain.seasonality import SeasonSettings
from wiki_interest.domain.trust import TrustSettings

__all__ = ["RUNS_DIRNAME", "Settings", "default_user_agent", "skill_root"]

_SECONDS_PER_DAY = 86_400
_RESOLUTION_TTL_DAYS = 7
_PROJECT_URL = "https://github.com/b-ark/wiki-interest"
_DEFAULT_THRESHOLDS = ReliabilityThresholds()
_DEFAULT_ASSESSMENT = AssessmentSettings()
_DEFAULT_SEASON = SeasonSettings()
_DEFAULT_ANOMALY = AnomalySettings()
_DEFAULT_TRUST = TrustSettings()


def skill_root() -> Path:
    """Return the skill directory (the one containing ``SKILL.md`` and ``pyproject.toml``).

    Derived from the package location rather than the working directory because the agent
    runs the scripts from arbitrary folders; the shared HTTP cache must still land inside the
    skill directory, which is git-ignored for it.
    """
    return Path(__file__).resolve().parent.parent


def default_user_agent() -> str:
    """Build the User-Agent Wikimedia's policy asks for: tool name, version and a contact URL.

    Wikimedia rejects or throttles generic client strings; see
    https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy.
    The project URL doubles as the contact channel.
    """
    return f"wiki-interest/{__version__} ({_PROJECT_URL})"


RUNS_DIRNAME = "wiki-interest-runs"


def _default_runs_dir() -> Path:
    """Where analysis bundles are written: ``wiki-interest-runs/`` in the working directory.

    Reports belong to the user's project, not to the skill installation: skill directories
    may be read-only or hidden (``.claude/skills/...``), and agents are often not allowed to
    write there. The HTTP cache, which is shared across projects, stays in the skill.
    """
    return Path.cwd() / RUNS_DIRNAME


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
        publish_lag_days: Days after a window's last day before it counts as closed: the API
            publishes a month some days after it ends, and a run on the 1st that cached the
            month's absence forever kept it missing in every later run.
        resolution_ttl_s: Cache TTL for Wikidata and MediaWiki lookups (labels, sitelinks,
            redirects, links); they change rarely but do change.
        cache_path: SQLite file for the HTTP cache; parent directories are created on demand.
        runs_dir: Where run directories are written; ``wiki-interest-runs/`` in the current
            working directory by default, so reports land in the user's project.
        stop_after: ``"resolve"`` ends a run once the topics are resolved and every edition
            has an article or a decision, without fetching pageviews. Used by the evaluation
            harness to test the topic stage (questions, entity choice) on its own; a run in
            this mode says so in ``summary.md``.
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
    publish_lag_days: int = Field(default=7, ge=0)
    resolution_ttl_s: int = Field(default=_RESOLUTION_TTL_DAYS * _SECONDS_PER_DAY, ge=0)
    cache_path: Path = Field(default_factory=_default_cache_path)
    runs_dir: Path = Field(default_factory=_default_runs_dir)
    stop_after: Literal["resolve"] | None = None

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

    # Conclusions: when a change counts as growth, when recent months confirm it.
    min_momentum: float = Field(default=_DEFAULT_ASSESSMENT.min_momentum, ge=0)
    similar_size_ratio: float = Field(default=_DEFAULT_ASSESSMENT.similar_size_ratio, ge=1)
    min_share_shift: float = Field(default=_DEFAULT_ASSESSMENT.min_share_shift, ge=0)
    min_recent_shift: float = Field(default=_DEFAULT_ASSESSMENT.min_recent_shift, ge=0)
    min_recent_views: float = Field(default=_DEFAULT_ASSESSMENT.min_recent_views, ge=0)

    # Seasons, on the article's whole history.
    season_min_years: int = Field(default=_DEFAULT_SEASON.min_years, ge=2)
    season_min_consistency: float = Field(default=_DEFAULT_SEASON.min_consistency, ge=0, le=1)
    season_min_strength: float = Field(default=_DEFAULT_SEASON.min_strength, ge=0, le=1)
    season_min_range: float = Field(default=_DEFAULT_SEASON.min_range, ge=0)

    # The analysis window's verdict and the trust in it (v0.2): one field per
    # ``TrustSettings`` threshold, ``WIKI_INTEREST_TRUST_<NAME>`` in the environment.
    trust_stable_pct_per_year: float = Field(default=_DEFAULT_TRUST.stable_pct_per_year, ge=0)
    trust_min_window_months: int = Field(default=_DEFAULT_TRUST.min_window_months, ge=0)
    trust_min_segment_months: int = Field(default=_DEFAULT_TRUST.min_segment_months, ge=0)
    trust_split_step: float = Field(default=_DEFAULT_TRUST.split_step, ge=0)
    trust_volume_floor: float = Field(default=_DEFAULT_TRUST.volume_floor, ge=0)
    trust_yoy_strong: int = Field(default=_DEFAULT_TRUST.yoy_strong, ge=0)
    trust_snr_min: float = Field(default=_DEFAULT_TRUST.snr_min, ge=0)
    trust_control_explains: float = Field(default=_DEFAULT_TRUST.control_explains, ge=0)
    trust_day_spike_share: float = Field(default=_DEFAULT_TRUST.day_spike_share, ge=0)
    trust_bootstrap_reps: int = Field(default=_DEFAULT_TRUST.bootstrap_reps, ge=0)
    trust_bootstrap_block: int = Field(default=_DEFAULT_TRUST.bootstrap_block, ge=0)
    trust_bootstrap_seed: int = Field(default=_DEFAULT_TRUST.bootstrap_seed, ge=0)
    trust_ci_level: float = Field(default=_DEFAULT_TRUST.ci_level, ge=0)
    trust_rename_months: int = Field(default=_DEFAULT_TRUST.rename_months, ge=0)
    trust_control_sample: int = Field(default=_DEFAULT_TRUST.control_sample, ge=0)
    trust_control_candidates: int = Field(default=_DEFAULT_TRUST.control_candidates, ge=0)
    trust_control_top: int = Field(default=_DEFAULT_TRUST.control_top, ge=0)
    trust_control_seed: int = Field(default=_DEFAULT_TRUST.control_seed, ge=0)
    trust_control_ttl_days: int = Field(default=_DEFAULT_TRUST.control_ttl_days, ge=0)
    trust_control_spike_multiple: float = Field(default=_DEFAULT_TRUST.control_spike_multiple, ge=0)

    # Months that stand out.
    anomaly_min_multiple: float = Field(default=_DEFAULT_ANOMALY.min_multiple, gt=1)
    anomaly_strong_multiple: float = Field(default=_DEFAULT_ANOMALY.strong_multiple, gt=1)
    anomaly_mad_multiplier: float = Field(default=_DEFAULT_ANOMALY.mad_multiplier, gt=0)

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

    def thresholds(self) -> dict[str, float | int | bool]:
        """Every tunable threshold by its field name, for the run's method note."""
        names = (
            *ReliabilityThresholds.__dataclass_fields__,
            *AssessmentSettings.__dataclass_fields__,
            "season_min_years",
            "season_min_consistency",
            "season_min_strength",
            "season_min_range",
            "anomaly_min_multiple",
            "anomaly_strong_multiple",
            "anomaly_mad_multiplier",
            *(f"trust_{name}" for name in TrustSettings.__dataclass_fields__),
        )
        values = self.model_dump()
        return {name: values[name] for name in names if name in values}

    def assessment_settings(self) -> AssessmentSettings:
        """The cut-offs of the conclusions."""
        return AssessmentSettings(
            min_momentum=self.min_momentum,
            similar_size_ratio=self.similar_size_ratio,
            min_share_shift=self.min_share_shift,
            min_recent_shift=self.min_recent_shift,
            min_recent_views=self.min_recent_views,
        )

    def trust_settings(self) -> TrustSettings:
        """The window's verdict and the trust in it: every threshold in one object."""
        return TrustSettings(
            stable_pct_per_year=self.trust_stable_pct_per_year,
            min_window_months=self.trust_min_window_months,
            min_segment_months=self.trust_min_segment_months,
            split_step=self.trust_split_step,
            volume_floor=self.trust_volume_floor,
            yoy_strong=self.trust_yoy_strong,
            snr_min=self.trust_snr_min,
            control_explains=self.trust_control_explains,
            day_spike_share=self.trust_day_spike_share,
            bootstrap_reps=self.trust_bootstrap_reps,
            bootstrap_block=self.trust_bootstrap_block,
            bootstrap_seed=self.trust_bootstrap_seed,
            ci_level=self.trust_ci_level,
            rename_months=self.trust_rename_months,
            control_sample=self.trust_control_sample,
            control_candidates=self.trust_control_candidates,
            control_top=self.trust_control_top,
            control_seed=self.trust_control_seed,
            control_ttl_days=self.trust_control_ttl_days,
            control_spike_multiple=self.trust_control_spike_multiple,
        )

    def control_dir(self) -> Path:
        """Where the editions' control baskets are kept: next to the HTTP cache."""
        return self.cache_path.parent / "control"

    def season_settings(self) -> SeasonSettings:
        """When a seasonal pattern is stated."""
        return SeasonSettings(
            min_years=self.season_min_years,
            min_consistency=self.season_min_consistency,
            min_strength=self.season_min_strength,
            min_range=self.season_min_range,
        )

    def anomaly_settings(self) -> AnomalySettings:
        """When a month stands out."""
        return AnomalySettings(
            min_multiple=self.anomaly_min_multiple,
            strong_multiple=self.anomaly_strong_multiple,
            mad_multiplier=self.anomaly_mad_multiplier,
        )
