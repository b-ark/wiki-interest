"""Self-diagnosis: is the environment able to run an analysis?

Run by ``scripts/doctor.py`` when something fails, and useful right after installation. Each
check is independent and reports a one-line detail, so an agent can relay exactly what is
wrong (no network, unwritable cache, missing fonts) instead of guessing from a traceback.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

from wiki_interest import __version__
from wiki_interest.cli.container import Container
from wiki_interest.contracts.request import Period
from wiki_interest.domain.models import Access, Agent, Granularity, WikiProject, Window
from wiki_interest.errors import WikiInterestError

__all__ = ["DoctorCheck", "DoctorReport", "run_doctor"]

MIN_PYTHON = (3, 12)
_PROBE_PROJECT = WikiProject("en")
_PROBE_QUERY = "astronomy"
_PROBE_QID = "Q333"
_PROBE_TITLE = "Astronomy"


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """Outcome of one diagnostic check."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """All checks of one doctor run."""

    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        """Whether every check passed."""
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        """JSON-ready representation."""
        return {"ok": self.ok, "checks": [asdict(check) for check in self.checks]}


def run_doctor(container: Container, *, online: bool = True) -> DoctorReport:
    """Run every check and collect the outcomes.

    Args:
        container: Wired adapters; the network checks go through the real gateways so they
            exercise the same code path as an analysis.
        online: Whether to contact Wikimedia services.
    """
    checks = [
        _python_version(),
        _package(),
        _cache_dir(container.settings.cache_path),
        _fonts(),
    ]
    if online:
        checks.extend(
            [
                _guard("pageviews_api", lambda: _probe_pageviews(container)),
                _guard("wikidata_api", lambda: _probe_wikidata(container)),
                _guard("mediawiki_api", lambda: _probe_mediawiki(container)),
            ]
        )
    return DoctorReport(tuple(checks))


def _python_version() -> DoctorCheck:
    version = sys.version_info[:3]
    ok = version >= MIN_PYTHON
    return DoctorCheck(
        "python_version",
        ok,
        f"Python {'.'.join(map(str, version))}"
        + ("" if ok else f" (need {'.'.join(map(str, MIN_PYTHON))}+)"),
    )


def _package() -> DoctorCheck:
    return DoctorCheck("package", True, f"wiki-interest {__version__}")


def _cache_dir(cache_path: Path) -> DoctorCheck:
    directory = cache_path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".doctor-", delete=True):
            pass
    except OSError as exc:
        return DoctorCheck("cache_dir", False, f"{directory} is not writable: {exc}")
    return DoctorCheck("cache_dir", True, f"{directory} is writable")


def _fonts() -> DoctorCheck:
    font_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    needed = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
    missing = [name for name in needed if not (font_dir / name).exists()]
    if missing:
        return DoctorCheck("fonts", False, f"missing in {font_dir}: {', '.join(missing)}")
    return DoctorCheck("fonts", True, f"DejaVu Sans found in {font_dir}")


def _guard(name: str, probe: Callable[[], str]) -> DoctorCheck:
    """Turn a probe into a check, converting known failures into a readable detail."""
    try:
        return DoctorCheck(name, True, probe())
    except WikiInterestError as exc:
        hint = f" ({exc.hint})" if exc.hint else ""
        return DoctorCheck(name, False, f"{exc}{hint}")


def _probe_pageviews(container: Container) -> str:
    period = Period.last_full_months(container.clock.today(), count=1)
    window = Window(Granularity.MONTHLY, period.start, period.end)
    series = container.pageviews.aggregate(
        _PROBE_PROJECT, window, access=Access.ALL, agent=Agent.USER
    )
    views = series.values[0]
    if views is None:
        return f"reachable, but no data yet for {period.start:%Y-%m}"
    return f"{_PROBE_PROJECT.domain} had {views:,.0f} views in {period.start:%Y-%m}"


def _probe_wikidata(container: Container) -> str:
    candidates = container.wikidata.search_entities(_PROBE_QUERY, "en", limit=3)
    if not any(c.qid == _PROBE_QID for c in candidates):
        found = ", ".join(c.qid for c in candidates) or "nothing"
        return f"reachable, but {_PROBE_QUERY!r} resolved to {found} instead of {_PROBE_QID}"
    return f"{_PROBE_QUERY!r} resolves to {_PROBE_QID}"


def _probe_mediawiki(container: Container) -> str:
    info = container.mediawiki.page_info(_PROBE_PROJECT, [_PROBE_TITLE]).get(_PROBE_TITLE)
    if info is None:
        return f"reachable, but {_PROBE_TITLE!r} was not found on {_PROBE_PROJECT.host}"
    return f"{_PROBE_TITLE!r} exists on {_PROBE_PROJECT.host} ({info.qid})"
