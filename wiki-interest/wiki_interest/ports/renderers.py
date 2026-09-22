"""Ports: chart and report rendering."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.contracts.summary import AnalysisSummary

__all__ = ["ChartRenderer", "ReportRenderer"]


class ChartRenderer(Protocol):
    """Turns a declarative chart specification into image files."""

    def render(self, spec: ChartSpec, output_dir: Path) -> Sequence[Path]:
        """Render ``spec`` into ``output_dir``.

        Returns:
            Paths of the files written (for example a PNG and an SVG of the same chart).

        Raises:
            RenderError: If the chart cannot be produced.
        """
        ...


class ReportRenderer(Protocol):
    """Turns a summary plus rendered charts into a report document (Markdown, PDF, ...)."""

    def render(self, summary: AnalysisSummary, charts: Sequence[Path], output_path: Path) -> Path:
        """Write the report to ``output_path``.

        Args:
            summary: The complete analysis result; all prose in it is already localised.
            charts: Image files produced by a :class:`ChartRenderer`, in display order.
            output_path: Where to write; the suffix selects nothing, the renderer does.

        Returns:
            The path written.

        Raises:
            RenderError: If the document cannot be produced.
        """
        ...
