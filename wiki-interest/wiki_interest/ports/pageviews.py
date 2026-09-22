"""Port: source of pageview time series."""

from __future__ import annotations

from typing import Protocol

from wiki_interest.domain.models import Access, Agent, Series, WikiProject, Window

__all__ = ["PageviewsSource"]


class PageviewsSource(Protocol):
    """Provides pageview series for articles and whole projects.

    Contract shared by every implementation (Wikimedia REST today, dumps later):

    * The returned series covers **every** bucket of ``window``, in order, with ``None`` for
      buckets the source has no data for. Callers never have to align series.
    * "No data" is not an error. Only transport-level failures raise
      :class:`~wiki_interest.errors.UpstreamError`.
    * Implementations are free to cache; results for closed periods are immutable upstream.
    """

    def per_article(
        self,
        project: WikiProject,
        title: str,
        window: Window,
        *,
        access: Access,
        agent: Agent,
    ) -> Series:
        """Return views of one article.

        Args:
            project: Language edition the article belongs to.
            title: Canonical page title with spaces; the implementation encodes it.
            window: Buckets to cover.
            access: Access method filter.
            agent: Traffic class filter.

        Returns:
            A series in :attr:`~wiki_interest.domain.models.SeriesUnit.VIEWS` aligned to ``window``.
        """
        ...

    def aggregate(
        self,
        project: WikiProject,
        window: Window,
        *,
        access: Access,
        agent: Agent,
    ) -> Series:
        """Return total views of a whole project, used to normalise article series.

        Same bucket and gap semantics as :meth:`per_article`.
        """
        ...
