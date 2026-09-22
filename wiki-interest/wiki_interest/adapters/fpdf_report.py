"""One-page A4 PDF report built with fpdf2.

The page is a strict grid (title, key-number tiles, the first chart, verdict, reliability,
limitations, footer) drawn from the theme in ``assets/report_theme.json``. It must never
spill onto a second page, so the renderer draws the page on a throwaway document, measures,
and if the content overflows retries with a progressively tighter layout: fewer reliability
reasons, then fewer limitation lines, then a smaller font down to a floor, and finally a
layout that truncates lists with a pointer to ``summary.md``. Fonts come from matplotlib's
bundled DejaVu Sans so Cyrillic and Central European diacritics render without shipping
font files. Metadata is fixed (no creation timestamp) so re-runs are byte-identical.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import matplotlib
from fpdf import FPDF, XPos, YPos
from fpdf.errors import FPDFException
from PIL import Image

from wiki_interest.adapters.markdown_report import (
    GENERATED_AT_FORMAT,
    PER_MILLION_DECIMALS,
    PERCENT_DECIMALS,
    SCORE_DECIMALS,
    period_text,
    question_line,
    report_title,
    row_label,
    sorted_checks,
)
from wiki_interest.adapters.report_theme import PdfTheme, ReportTheme
from wiki_interest.contracts.summary import AnalysisSummary, ReliabilityOut
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

__all__ = ["FONT_DIR", "FpdfReportRenderer"]

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
"""DejaVu Sans as shipped with matplotlib; the project deliberately stores no fonts."""
FONT_FAMILY = "DejaVu"
FONT_FILES = {"": "DejaVuSans.ttf", "B": "DejaVuSans-Bold.ttf"}
FIXED_CREATION_DATE = datetime(2000, 1, 1, tzinfo=UTC)
"""Constant so the PDF bytes (which hash the creation date) do not vary between runs."""
PT_PER_MM = 72 / 25.4
PAGE_FORMAT = "A4"
MAX_TILES = 4
TILE_MAX_ROWS = 3
TILE_LARGE_VALUE_MAX_ROWS = 2
"""With more rows than this a tile falls back to body-size values to stay inside its box."""
TILE_KEY_MAX_CHARS = 14
TILE_PADDING_MM = 2.0
BULLET = "•  "
ELLIPSIS = "…"
FLOAT_TOLERANCE = 1e-6
INITIAL_MAX_REASONS = 3
REASON_STEPS = (2, 1)
LIMITATION_STEPS = (4, 2)


@dataclass(frozen=True, slots=True)
class _Layout:
    """One attempt at fitting the page; attempts get tighter until the content fits."""

    max_reasons: int = INITIAL_MAX_REASONS
    max_limitations: int | None = None
    font_scale: float = 1.0
    truncate: bool = False


class _Rgb(tuple[int, int, int]):
    """RGB triple parsed from a ``#RRGGBB`` theme colour."""

    __slots__ = ()

    @classmethod
    def parse(cls, value: str) -> _Rgb:
        digits = value.lstrip("#")
        return cls(int(digits[i : i + 2], 16) for i in (0, 2, 4))


class FpdfReportRenderer:
    """Renders ``report.pdf``: a single A4 page in the report language.

    Args:
        translator: Supplies section titles and number formatting.
        theme_path: Theme JSON; ``None`` selects the one shipped in ``assets/``.
    """

    def __init__(self, translator: Translator, theme_path: Path | None = None) -> None:
        self._t = translator
        self._theme = ReportTheme.load(theme_path)
        for name in FONT_FILES.values():
            if not (FONT_DIR / name).is_file():
                msg = f"Font file {name} not found in {FONT_DIR}"
                raise RenderError(msg, hint="Reinstall matplotlib; it bundles DejaVu Sans")

    def render(self, summary: AnalysisSummary, charts: Sequence[Path], output_path: Path) -> Path:
        """Write the one-page PDF.

        Raises:
            RenderError: If no layout fits (cannot happen with the truncating fallback, but
                guarded), or fpdf2/the file system fails.
        """
        try:
            document = self._fit(summary, charts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            document.output(str(output_path))
        except (OSError, FPDFException, ValueError) as exc:
            msg = f"Cannot write PDF report to {output_path}: {exc}"
            raise RenderError(msg, hint="Check the chart files and the run directory") from exc
        return output_path

    def _fit(self, summary: AnalysisSummary, charts: Sequence[Path]) -> FPDF:
        for layout in self._layouts():
            page = _Page(self._t, self._theme, summary, charts, layout)
            page.draw()
            if not page.overflowed:
                return page.pdf
        msg = "Report content does not fit on one page even when truncated"
        raise RenderError(msg, hint="Shorten the report title or the verdict headline")

    def _layouts(self) -> Iterator[_Layout]:
        """Tightening sequence: reasons, then limitation lines, then font size, then truncate."""
        layout = _Layout()
        yield layout
        for reasons in REASON_STEPS:
            layout = replace(layout, max_reasons=reasons)
            yield layout
        for limitations in LIMITATION_STEPS:
            layout = replace(layout, max_limitations=limitations)
            yield layout
        pdf_theme = self._theme.pdf
        scale = 1.0 - pdf_theme.font_scale_step
        while scale >= pdf_theme.min_font_scale - FLOAT_TOLERANCE:
            layout = replace(layout, font_scale=scale)
            yield layout
            scale -= pdf_theme.font_scale_step
        yield replace(layout, truncate=True)


class _Page:
    """Draws one attempt and records whether anything ran past the content area."""

    def __init__(
        self,
        translator: Translator,
        theme: ReportTheme,
        summary: AnalysisSummary,
        charts: Sequence[Path],
        layout: _Layout,
    ) -> None:
        self._t = translator
        self._theme = theme
        self._style: PdfTheme = theme.pdf
        self._summary = summary
        self._charts = charts
        self._layout = layout
        self.overflowed = False
        self._stopped = False
        self.pdf = self._new_document()
        self._footer_top = self._draw_footer()
        self._limit = self._footer_top - self._style.section_gap_mm
        if layout.truncate:
            self._limit -= self._line_height(self._style.small_pt)

    # -- document setup ----------------------------------------------------------------------

    def _new_document(self) -> FPDF:
        pdf = FPDF(orientation="P", unit="mm", format=PAGE_FORMAT)
        pdf.set_auto_page_break(False)
        margin = self._style.margin_mm
        pdf.set_margins(margin, margin, margin)
        for style, name in FONT_FILES.items():
            pdf.add_font(FONT_FAMILY, style=style, fname=str(FONT_DIR / name))
        pdf.set_creation_date(FIXED_CREATION_DATE)
        pdf.set_title(report_title(self._summary, self._t))
        pdf.set_author("wiki-interest")
        pdf.set_creator("wiki-interest")
        pdf.set_producer("wiki-interest")
        pdf.set_lang(self._t.language)
        pdf.add_page()
        return pdf

    def _size(self, points: float) -> float:
        return points * self._layout.font_scale

    def _line_height(self, points: float) -> float:
        return self._size(points) * self._style.line_height / PT_PER_MM

    def _font(self, points: float, *, bold: bool = False, color: str | None = None) -> float:
        self.pdf.set_font(FONT_FAMILY, "B" if bold else "", self._size(points))
        self.pdf.set_text_color(*_Rgb.parse(color or self._theme.text_color))
        return self._line_height(points)

    # -- fitting primitives ------------------------------------------------------------------

    def _fits(self, height: float) -> bool:
        """Whether ``height`` more millimetres fit; on failure stop or flag the overflow."""
        if self._stopped:
            return False
        if self.pdf.get_y() + height <= self._limit + FLOAT_TOLERANCE:
            return True
        if self._layout.truncate:
            self._stopped = True
            self._draw_ellipsis()
        else:
            self.overflowed = True
        return False

    def _draw_ellipsis(self) -> None:
        line_h = self._font(self._style.small_pt, color=self._theme.muted_color)
        self.pdf.multi_cell(
            self.pdf.epw,
            line_h,
            self._t.t("report.see_summary"),
            align="L",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    def _paragraph(
        self, text: str, points: float, *, bold: bool = False, color: str | None = None
    ) -> bool:
        line_h = self._font(points, bold=bold, color=color)
        height = cast(
            float, self.pdf.multi_cell(self.pdf.epw, line_h, text, dry_run=True, output="HEIGHT")
        )
        if not self._fits(height):
            return False
        self.pdf.multi_cell(
            self.pdf.epw, line_h, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        return True

    def _heading(self, key: str) -> bool:
        self._gap()
        return self._paragraph(
            self._t.t(key), self._style.heading_pt, bold=True, color=self._theme.accent_color
        )

    def _bullets(self, items: Sequence[str]) -> None:
        for item in items:
            if not self._paragraph(f"{BULLET}{item}", self._style.body_pt):
                return

    def _gap(self) -> None:
        self.pdf.set_y(self.pdf.get_y() + self._style.section_gap_mm)

    # -- sections ----------------------------------------------------------------------------

    def draw(self) -> None:
        """Draw every section in order; stops early only in truncating layouts."""
        sections: list[Callable[[], None]] = [
            self._title,
            self._tiles,
            self._chart,
            self._verdict,
            self._reliability,
            self._limitations,
        ]
        for section in sections:
            if self._stopped:
                break
            section()

    def _title(self) -> None:
        summary, t = self._summary, self._t
        self._paragraph(report_title(summary, t), self._style.title_pt, bold=True)
        subtitle = (
            f"{question_line(summary, t)} · {t.t('report.period')}: {period_text(summary)} · "
            f"{t.t('report.projects')}: {', '.join(summary.request.projects)}"
        )
        self._paragraph(subtitle, self._style.subtitle_pt, color=self._theme.muted_color)
        note = summary.request.report.audience_note
        if note:
            self._paragraph(note, self._style.subtitle_pt, color=self._theme.muted_color)

    def _tiles(self) -> None:
        tiles = self._tile_contents()
        if not tiles:
            return
        self._gap()
        height = self._style.tile_height_mm * self._layout.font_scale
        if not self._fits(height):
            return
        gap = self._style.tile_gap_mm
        width = (self.pdf.epw - gap * (len(tiles) - 1)) / len(tiles)
        top = self.pdf.get_y()
        for index, (label, rows) in enumerate(tiles):
            origin = (self.pdf.l_margin + index * (width + gap), top)
            self._draw_tile(origin, (width, height), label, rows)
        self.pdf.set_y(top + height)

    def _draw_tile(
        self,
        origin: tuple[float, float],
        size: tuple[float, float],
        label: str,
        rows: Sequence[str],
    ) -> None:
        (x, y), (w, h) = origin, size
        pdf = self.pdf
        pdf.set_fill_color(*_Rgb.parse(self._style.tile_fill))
        pdf.rect(x, y, w, h, style="F")
        pdf.set_xy(x + TILE_PADDING_MM, y + TILE_PADDING_MM)
        line_h = self._font(self._style.small_pt, color=self._theme.muted_color)
        pdf.cell(w - 2 * TILE_PADDING_MM, line_h, label)
        large = len(rows) <= TILE_LARGE_VALUE_MAX_ROWS
        value_pt = self._style.tile_value_pt if large else self._style.body_pt
        line_h = self._font(value_pt, bold=True)
        for offset, row in enumerate(rows):
            pdf.set_xy(
                x + TILE_PADDING_MM,
                y + TILE_PADDING_MM + self._line_height(self._style.small_pt) + offset * line_h,
            )
            pdf.cell(w - 2 * TILE_PADDING_MM, line_h, row)

    def _tile_contents(self) -> list[tuple[str, list[str]]]:
        """Up to four (label, value lines) pairs from the comparison, else from the ranking."""
        t, summary = self._t, self._summary
        if summary.comparison:
            rows = summary.comparison[:TILE_MAX_ROWS]
            keys = _tile_keys([(r.topic_id, r.project, r.label) for r in rows])
            return [
                (
                    t.t("col.views_avg"),
                    [f"{k}: {t.number(r.views_avg)}" for k, r in zip(keys, rows, strict=True)],
                ),
                (
                    t.t("col.per_million_avg"),
                    [
                        f"{k}: {t.number(r.per_million_avg, PER_MILLION_DECIMALS)}"
                        for k, r in zip(keys, rows, strict=True)
                    ],
                ),
                (
                    t.t("col.growth_yoy"),
                    [
                        f"{k}: {t.percent(r.growth_yoy, PERCENT_DECIMALS, signed=True)}"
                        for k, r in zip(keys, rows, strict=True)
                    ],
                ),
                (
                    t.t("col.reliability"),
                    [
                        f"{k}: {t.label('level', r.reliability)}"
                        for k, r in zip(keys, rows, strict=True)
                    ],
                ),
            ][:MAX_TILES]
        if summary.ranking:
            ranked = sorted(summary.ranking, key=lambda r: r.rank)[:TILE_MAX_ROWS]
            keys = _tile_keys([(r.topic_id, r.project, r.label) for r in ranked])
            return [
                (
                    t.t("col.score"),
                    [
                        f"{r.rank}. {k}: {t.number(r.score, SCORE_DECIMALS)}"
                        for k, r in zip(keys, ranked, strict=True)
                    ],
                ),
                (
                    t.t("col.profile"),
                    [
                        f"{k}: {t.label('profile', r.profile)}"
                        for k, r in zip(keys, ranked, strict=True)
                    ],
                ),
                (
                    t.t("col.reliability"),
                    [
                        f"{k}: {t.label('level', r.reliability)}"
                        for k, r in zip(keys, ranked, strict=True)
                    ],
                ),
            ]
        return []

    def _chart(self) -> None:
        image = next((c for c in self._charts if c.suffix.lower() == ".png"), None)
        if image is None:
            return
        with Image.open(image) as opened:
            pixel_w, pixel_h = opened.size
        width = self.pdf.epw
        height = width * pixel_h / pixel_w
        max_height = self._style.chart_max_height_mm * self._layout.font_scale
        if height > max_height:
            width, height = max_height * pixel_w / pixel_h, max_height
        self._gap()
        if not self._fits(height):
            return
        x = self.pdf.l_margin + (self.pdf.epw - width) / 2
        self.pdf.image(str(image), x=x, y=self.pdf.get_y(), w=width, h=height)
        self.pdf.set_y(self.pdf.get_y() + height)

    def _verdict(self) -> None:
        if not self._heading("report.verdict"):
            return
        if not self._paragraph(self._summary.verdict.headline, self._style.body_pt, bold=True):
            return
        self._bullets(self._summary.verdict.bullets)

    def _reliability(self) -> None:
        if not self._summary.reliability or not self._heading("report.reliability"):
            return
        for item in self._summary.reliability:
            if not self._paragraph(self._reliability_line(item), self._style.body_pt):
                return

    def _reliability_line(self, item: ReliabilityOut) -> str:
        label = row_label(self._summary, item.topic_id, item.project)
        level = self._t.label("level", item.level)
        reasons = sorted_checks(item.checks)[: self._layout.max_reasons]
        return f"{label} — {item.project}: {level}. " + "; ".join(c.message for c in reasons)

    def _limitations(self) -> None:
        items = self._summary.limitations
        if not items or not self._heading("report.limitations"):
            return
        limit = self._layout.max_limitations
        shown = items if limit is None else items[:limit]
        self._bullets(shown)
        if len(shown) < len(items) and not self._stopped:
            self._paragraph(
                self._t.t("report.see_summary"), self._style.small_pt, color=self._theme.muted_color
            )

    def _draw_footer(self) -> float:
        """Draw the footer at the page bottom and return the y where content must end."""
        t, provenance = self._t, self._summary.provenance
        generated = provenance.generated_at.strftime(GENERATED_AT_FORMAT)
        text = " · ".join(
            [
                f"{t.t('report.sources')}: {', '.join(provenance.sources)}",
                f"{t.t('report.data_through')}: {provenance.data_through}",
                f"{t.t('report.generated')}: {generated}",
                f"{t.t('report.version')}: {provenance.code_version}",
            ]
        )
        line_h = self._font(self._style.small_pt, color=self._theme.muted_color)
        height = cast(
            float, self.pdf.multi_cell(self.pdf.epw, line_h, text, dry_run=True, output="HEIGHT")
        )
        top = self.pdf.h - self._style.margin_mm - height
        self.pdf.set_draw_color(*_Rgb.parse(self._style.rule_color))
        self.pdf.line(
            self.pdf.l_margin,
            top - self._style.section_gap_mm / 2,
            self.pdf.l_margin + self.pdf.epw,
            top - self._style.section_gap_mm / 2,
        )
        self.pdf.set_xy(self.pdf.l_margin, top)
        self.pdf.multi_cell(
            self.pdf.epw, line_h, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        self.pdf.set_xy(self.pdf.l_margin, self._style.margin_mm)
        return top - self._style.section_gap_mm


def _tile_keys(rows: Sequence[tuple[str, str, str]]) -> list[str]:
    """Short row identifiers for tiles: the language code alone when the topic is the same."""
    single_topic = len({topic for topic, _, _ in rows}) == 1
    keys = []
    for _, project, label in rows:
        code = project.split(".")[0]
        keys.append(code if single_topic else f"{code} {_shorten(label)}")
    return keys


def _shorten(text: str) -> str:
    if len(text) <= TILE_KEY_MAX_CHARS:
        return text
    return text[: TILE_KEY_MAX_CHARS - 1] + ELLIPSIS
