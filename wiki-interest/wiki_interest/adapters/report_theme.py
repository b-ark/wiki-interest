"""Visual theme shared by the chart and PDF renderers.

Colours, fonts and layout dimensions live in ``assets/report_theme.json`` so the look of every
artifact can be tuned in one place without touching code, and so charts and the PDF cannot
drift apart. The file is validated on load: a typo in a key is a :class:`RenderError` at
start-up, not a subtly wrong report.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wiki_interest.errors import RenderError

__all__ = ["DEFAULT_THEME_PATH", "ChartTheme", "PdfTheme", "ReportTheme"]

DEFAULT_THEME_PATH = Path(__file__).resolve().parents[2] / "assets" / "report_theme.json"
"""Theme shipped with the skill; the skill runs from its checkout, so the path is stable."""

_MIN_PALETTE_SIZE = 6
"""A compare/rank request may plot up to this many editions before colours would repeat."""


MIN_TEXT_PT = 8.5
"""No text on the PDF page is smaller than this."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChartTheme(_Frozen):
    """Matplotlib figure settings; sizes in millimetres and points as named."""

    dpi: int = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    half_width_mm: float = Field(gt=0)
    half_height_mm: float = Field(gt=0)
    strip_height_mm: float = Field(gt=0)
    font_size_pt: float = Field(gt=0)
    title_size_pt: float = Field(gt=0)
    small_size_pt: float = Field(gt=0)
    line_width: float = Field(gt=0)
    marker_size: float = Field(ge=0)
    max_x_ticks: int = Field(gt=1)


class PdfTheme(_Frozen):
    """One-page report grid: margins and the type scale.

    Text is never set below :data:`MIN_TEXT_PT`; to fit the page the renderer drops items
    and lowers charts (down to ``chart_min_height_mm``), never the font size.
    """

    margin_mm: float = Field(gt=0)
    title_pt: float = Field(ge=MIN_TEXT_PT)
    subtitle_pt: float = Field(ge=MIN_TEXT_PT)
    heading_pt: float = Field(ge=MIN_TEXT_PT)
    body_pt: float = Field(ge=MIN_TEXT_PT)
    small_pt: float = Field(ge=MIN_TEXT_PT)
    line_height: float = Field(gt=0)
    section_gap_mm: float = Field(ge=0)
    table_fill: str
    rule_color: str
    chart_max_height_mm: float = Field(gt=0)
    chart_min_height_mm: float = Field(gt=0)
    chart_gap_mm: float = Field(ge=0)


class ReportTheme(_Frozen):
    """Everything renderers may ask about appearance.

    Attributes:
        palette: Series colours in plotting order; Okabe-Ito by default because it stays
            distinguishable under the common forms of colour-vision deficiency.
        font_family: Family name used by matplotlib; the PDF loads the same face from
            matplotlib's bundled TTF files.
    """

    palette: list[str] = Field(min_length=_MIN_PALETTE_SIZE)
    font_family: str
    text_color: str
    muted_color: str
    grid_color: str
    accent_color: str
    highlight_color: str
    highlight_alpha: float = Field(ge=0, le=1)
    trend_color: str
    chart: ChartTheme
    pdf: PdfTheme

    @classmethod
    def load(cls, path: Path | None = None) -> ReportTheme:
        """Read and validate a theme file, defaulting to the one shipped in ``assets/``.

        Raises:
            RenderError: If the file is missing, not JSON, or fails validation.
        """
        theme_path = DEFAULT_THEME_PATH if path is None else path
        try:
            payload = json.loads(theme_path.read_text(encoding="utf-8"))
            return cls.model_validate(payload)
        except (OSError, ValueError, ValidationError) as exc:
            msg = f"Cannot load report theme from {theme_path}: {exc}"
            raise RenderError(msg, hint="Check assets/report_theme.json or the theme_path") from exc
