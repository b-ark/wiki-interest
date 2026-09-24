"""One-page A4 PDF report built with fpdf2.

The page reads top to bottom as a decision memo: the answer as the headline; what was
analysed (topic, Wikidata item, editions, period); the key numbers as a small table; the main
chart and the second one; what happened; how robust the conclusion is; what it means for the
decision, with the next step. The footer defines the attention share and the windows, states
that views are curiosity and that a language is not a country, names the months that stand
out in the comparison, and points to ``method.md`` for every computation.

It must never spill onto a second page, and text is never set smaller to make it fit: the
renderer draws the page on a throwaway document, measures, and if the content overflows
retries with fewer items (the seasonal chart, the data line, decision lines, what-happened
sentences, run-specific caveats, the second chart), then lower charts, and finally a layout
that truncates with a pointer to ``summary.md``. A chart too tall for its place is drawn
again lower, not shrunk: every full-width chart keeps the page width, and their plots line
up. With ``report.appendix`` a second page carries the method. Fonts come from matplotlib's
bundled DejaVu Sans so Cyrillic and Central European diacritics render without shipping font
files. Metadata is fixed (no creation timestamp) so re-runs are byte-identical.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import matplotlib
from fpdf import FPDF, XPos, YPos
from fpdf.errors import FPDFException
from PIL import Image

from wiki_interest.adapters.method_report import method_markdown
from wiki_interest.adapters.report_blocks import (
    GENERATED_AT_FORMAT,
    decision_lines,
    kpi_table,
    ordered_assessments,
    report_title,
    robustness_lines,
    short_label,
)
from wiki_interest.adapters.report_theme import PdfTheme, ReportTheme
from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator
from wiki_interest.ports import ChartRenderer

__all__ = ["FONT_DIR", "FpdfReportRenderer"]

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
"""DejaVu Sans as shipped with matplotlib; the project deliberately stores no fonts."""
FONT_FAMILY = "DejaVu"
FONT_FILES = {"": "DejaVuSans.ttf", "B": "DejaVuSans-Bold.ttf"}
FIXED_CREATION_DATE = datetime(2000, 1, 1, tzinfo=UTC)
"""Constant so the PDF bytes (which hash the creation date) do not vary between runs."""
PT_PER_MM = 72 / 25.4
PAGE_FORMAT = "A4"
BULLET = "•  "
FLOAT_TOLERANCE = 1e-6
TABLE_VALUE_MAX_MM = 34.0
TABLE_VALUES_SHARE = 0.62
"""The edition columns take at most this share of the width; the metric names the rest."""
TABLE_PADDING_MM = 1.2
CHART_STEP_MM = 10.0
"""How much lower the charts get per tightening step."""
METHOD_FILE = "method.md"
MAX_FOOTER_MONTHS = 3
REDRAW_SLACK_MM = 0.3
"""A redrawn chart aims this much under its height: its pixels round up, not over."""

Redraw = Callable[[str, float], Path | None]
"""Draws the chart of an id again at a figure height in millimetres; its PNG, or ``None``."""


@dataclass(frozen=True, slots=True)
class _Layout:
    """One attempt at fitting the page; attempts get tighter until the content fits.

    ``None`` limits show everything.
    """

    charts: int = 3
    show_data_note: bool = True
    all_robustness: bool = True
    """``False`` keeps robustness lines only where the last months do not confirm the trend;
    the table's row says "yes" for the others."""
    max_decision: int | None = None
    max_happening: int | None = None
    max_caveats: int | None = None
    chart_height: float | None = None
    truncate: bool = False


class _Rgb(tuple[int, int, int]):
    """RGB triple parsed from a ``#RRGGBB`` theme colour."""

    __slots__ = ()

    @classmethod
    def parse(cls, value: str) -> _Rgb:
        digits = value.lstrip("#")
        return cls(int(digits[i : i + 2], 16) for i in (0, 2, 4))


class FpdfReportRenderer:
    """Renders ``report.pdf``: one A4 page in the report language, plus the method if asked.

    Args:
        translator: Supplies section titles and number formatting.
        theme_path: Theme JSON; ``None`` selects the one shipped in ``assets/``.
        charts: Draws a chart again at the height the page leaves it; without it, a chart too
            tall is shrunk, and the full-width charts with it so their plots stay lined up.
    """

    def __init__(
        self,
        translator: Translator,
        theme_path: Path | None = None,
        *,
        charts: ChartRenderer | None = None,
    ) -> None:
        self._t = translator
        self._theme = ReportTheme.load(theme_path)
        self._charts = charts
        for name in FONT_FILES.values():
            if not (FONT_DIR / name).is_file():
                msg = f"Font file {name} not found in {FONT_DIR}"
                raise RenderError(msg, hint="Reinstall matplotlib; it bundles DejaVu Sans")

    def render(self, summary: AnalysisSummary, charts: Sequence[Path], output_path: Path) -> Path:
        """Write the PDF.

        Raises:
            RenderError: If no layout fits (cannot happen with the truncating fallback, but
                guarded), or fpdf2/the file system fails.
        """
        try:
            with tempfile.TemporaryDirectory(prefix="charts-") as scratch:
                redraw = (
                    _ChartRedraw(self._charts, summary.charts, Path(scratch))
                    if self._charts is not None
                    else None
                )
                page = self._fit(summary, charts, redraw)
                if summary.request.report.appendix:
                    page.draw_appendix(method_markdown(summary))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                page.pdf.output(str(output_path))
        except (OSError, FPDFException, ValueError) as exc:
            msg = f"Cannot write PDF report to {output_path}: {exc}"
            raise RenderError(msg, hint="Check the chart files and the run directory") from exc
        return output_path

    def _fit(
        self, summary: AnalysisSummary, charts: Sequence[Path], redraw: Redraw | None
    ) -> _Page:
        for layout in self._layouts():
            page = _Page(self._t, self._theme, summary, charts, layout, redraw=redraw)
            page.draw()
            if not page.overflowed:
                return page
        msg = "Report content does not fit on one page even when truncated"
        raise RenderError(msg, hint="Shorten the report title or the verdict headline")

    def _layouts(self) -> Iterator[_Layout]:
        """Tightening sequence, from what the reader misses least to what they miss most.

        The seasonal chart goes first (the text states the season), then the line on the
        data (``method.md`` has it in full), decision lines beyond the conclusion, sentences
        of what happened beyond two, run-specific caveats; then both charts get lower, the
        robustness lines the table already answers ("yes") go, then the second chart, and the
        main one gets lower still. The headline, the table, the main chart, the conclusion with the
        next step and the footer always stay; the font never shrinks.
        """
        style = self._theme.pdf
        layout = _Layout()
        yield layout
        for step in (
            {"charts": 2},
            {"show_data_note": False},
            {"max_decision": 2},
            {"max_happening": 3},
            {"max_decision": 1},
            {"max_happening": 2},
            {"max_caveats": 1},
            {"max_caveats": 0},
        ):
            layout = replace(layout, **step)
            yield layout
        # Two lower charts read better than one: lower both to the middle height first, then
        # drop the second and lower the main one to the minimum.
        heights = []
        height = style.chart_max_height_mm - CHART_STEP_MM
        while height >= style.chart_min_height_mm - FLOAT_TOLERANCE:
            heights.append(height)
            height -= CHART_STEP_MM
        middle = heights[: max(1, len(heights) // 2 + 1)]
        for height in middle:
            layout = replace(layout, chart_height=height)
            yield layout
        layout = replace(layout, all_robustness=False)
        yield layout
        layout = replace(layout, charts=1, chart_height=None)
        yield layout
        for height in heights:
            layout = replace(layout, chart_height=height)
            yield layout
        yield replace(layout, truncate=True)


def _aspect(image: Path) -> float:
    """Width over height of an image."""
    with Image.open(image) as opened:
        pixel_w, pixel_h = opened.size
    return float(pixel_w) / pixel_h


class _ChartRedraw:
    """Draws charts again at other heights, each height once, for the attempts of one page."""

    def __init__(self, charts: ChartRenderer, specs: Sequence[ChartSpec], directory: Path) -> None:
        self._charts = charts
        self._specs = {spec.id: spec for spec in specs}
        self._directory = directory
        self._drawn: dict[tuple[str, int], Path | None] = {}

    def __call__(self, chart_id: str, height_mm: float) -> Path | None:
        spec = self._specs.get(chart_id)
        if spec is None:
            return None
        tenths = round(height_mm * 10)
        key = (chart_id, tenths)
        if key not in self._drawn:
            lower = spec.model_copy(update={"id": f"{chart_id}-h{tenths}", "height_mm": height_mm})
            written = self._charts.render(lower, self._directory)
            self._drawn[key] = next((p for p in written if p.suffix.lower() == ".png"), None)
        return self._drawn[key]


class _Page:
    """Draws one attempt and records whether anything ran past the content area."""

    def __init__(  # noqa: PLR0913 -- one attempt needs all of it
        self,
        translator: Translator,
        theme: ReportTheme,
        summary: AnalysisSummary,
        charts: Sequence[Path],
        layout: _Layout,
        *,
        redraw: Redraw | None = None,
    ) -> None:
        self._t = translator
        self._theme = theme
        self._style: PdfTheme = theme.pdf
        self._summary = summary
        self._charts = charts
        self._layout = layout
        self._redraw = redraw
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

    def _line_height(self, points: float) -> float:
        return points * self._style.line_height / PT_PER_MM

    def _font(self, points: float, *, bold: bool = False, color: str | None = None) -> float:
        self.pdf.set_font(FONT_FAMILY, "B" if bold else "", points)
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
            self._headline,
            self._key_numbers,
            self._charts_block,
            self._happening,
            self._robustness,
            self._decision,
        ]
        for section in sections:
            if self._stopped:
                break
            section()

    def _headline(self) -> None:
        """The answer as the title, then what was analysed."""
        summary, t = self._summary, self._t
        self._paragraph(summary.verdict.headline, self._style.title_pt, bold=True)
        topics = "; ".join(
            f"{r.label or r.query} ({r.qid})" if r.qid else (r.label or r.query)
            for r in summary.resolution
        )
        editions = ", ".join(a.label for a in ordered_assessments(summary))
        period = f"{summary.period.start:%Y-%m} – {summary.period.end:%Y-%m}"
        parts = [p for p in (topics, editions, f"{t.t('report.period')}: {period}") if p]
        self._paragraph(" · ".join(parts), self._style.subtitle_pt, color=self._theme.muted_color)
        note = summary.request.report.audience_note
        if note:
            self._paragraph(note, self._style.subtitle_pt, color=self._theme.muted_color)

    def _key_numbers(self) -> None:
        """Rows of metrics, one column per audience, header in short labels."""
        header, rows = kpi_table(self._summary, self._t)
        if not rows:
            return
        items = ordered_assessments(self._summary)
        header = [header[0], *(short_label(self._summary, a) for a in items)]
        pdf, style = self.pdf, self._style
        columns = max(1, len(header) - 1)
        value_w = min(TABLE_VALUE_MAX_MM, pdf.epw * TABLE_VALUES_SHARE / columns)
        label_w = pdf.epw - value_w * columns
        widths = [label_w, *([value_w] * (len(header) - 1))]
        line_h = self._line_height(style.body_pt)
        heights = [self._row_height(row, widths, line_h) for row in (header, *rows)]
        self._gap()
        if not self._fits(sum(heights)):
            return
        top = pdf.get_y()
        pdf.set_fill_color(*_Rgb.parse(style.table_fill))
        pdf.rect(pdf.l_margin, top, pdf.epw, heights[0], style="F")
        y = top
        for index, (row, height) in enumerate(zip((header, *rows), heights, strict=True)):
            x = pdf.l_margin
            for column, (cell, width) in enumerate(zip(row, widths, strict=True)):
                self._font(style.body_pt, bold=index == 0)
                pdf.set_xy(x + TABLE_PADDING_MM, y + TABLE_PADDING_MM / 2)
                pdf.multi_cell(
                    width - 2 * TABLE_PADDING_MM,
                    line_h,
                    cell,
                    align="L" if column == 0 else "R",
                )
                x += width
            y += height
            pdf.set_draw_color(*_Rgb.parse(style.rule_color))
            pdf.line(pdf.l_margin, y, pdf.l_margin + pdf.epw, y)
        pdf.set_xy(pdf.l_margin, y)

    def _row_height(self, row: Sequence[str], widths: Sequence[float], line_h: float) -> float:
        tallest = 0.0
        for cell, width in zip(row, widths, strict=True):
            self._font(self._style.body_pt)
            height = cast(
                float,
                self.pdf.multi_cell(
                    width - 2 * TABLE_PADDING_MM, line_h, cell, dry_run=True, output="HEIGHT"
                ),
            )
            tallest = max(tallest, height)
        return tallest + TABLE_PADDING_MM

    def _charts_block(self) -> None:
        """The main chart across the page, the second under it, the season if it fits."""
        images = [c for c in self._charts if c.suffix.lower() == ".png"][: self._layout.charts]
        if not images:
            return
        main, rest = images[0], images[1:]
        wide = [main, *(i for i in rest if not self._is_half(i))]
        half = [i for i in rest if self._is_half(i)]
        # Full-width charts share their plot's edges (see the chart renderer). Too tall for their
        # place, they are drawn again lower, all by the same share, so the page keeps both;
        # what still does not fit (a chart cannot get lower and stay legible) shrinks, all of
        # them by one scale so the edges stay lined up.
        wide = self._lowered(wide)
        scale = min(self._chart_box(image, self.pdf.epw)[0] / self.pdf.epw for image in wide)
        for image in wide:
            if not self._chart_row([image], scale=scale):
                return
        if half:
            self._chart_row(half)

    def _lowered(self, images: Sequence[Path]) -> list[Path]:
        """``images``, drawn again lower by one share when the tallest is over its height.

        The share is what the tallest needs to fit at the page width; the others get as much
        lower, so the charts together take about the room they took when they were shrunk.
        """
        redraw = self._redraw
        if redraw is None:
            return list(images)
        epw = self.pdf.epw
        heights = {image: epw / _aspect(image) for image in images}
        max_height = self._layout.chart_height or self._style.chart_max_height_mm
        share = min(1.0, max_height / max(heights.values()))
        if share >= 1.0 - FLOAT_TOLERANCE:
            return list(images)
        to_figure = self._theme.chart.width_mm / epw
        return [
            redraw(image.stem, (heights[image] * share - REDRAW_SLACK_MM) * to_figure) or image
            for image in images
        ]

    def _chart_box(
        self, image: Path, slot: float, scale: float | None = None
    ) -> tuple[float, float]:
        """Width and height of ``image`` in ``slot``: its full width, less when too tall.

        With ``scale``, the image takes that share of the slot's width.
        """
        aspect = _aspect(image)
        if scale is not None:
            width = slot * scale
            return width, width / aspect
        width, height = slot, slot / aspect
        max_height = self._layout.chart_height or self._style.chart_max_height_mm
        if height > max_height + FLOAT_TOLERANCE:
            width, height = max_height * aspect, max_height
        return width, height

    def _chart_row(self, images: Sequence[Path], *, scale: float | None = None) -> bool:
        gap = self._style.chart_gap_mm
        columns = 2 if len(images) > 1 else 1
        slot = (self.pdf.epw - gap * (columns - 1)) / columns
        if columns == 1 and self._is_half(images[0]):
            slot = (self.pdf.epw - gap) / 2
        boxes = [self._chart_box(image, slot, scale) for image in images]
        row_height = max(h for _, h in boxes)
        self._gap()
        if not self._fits(row_height):
            return False
        top = self.pdf.get_y()
        for column, (image, (width, height)) in enumerate(zip(images, boxes, strict=True)):
            x = self.pdf.l_margin + column * (slot + gap) + (slot - width) / 2
            self.pdf.image(str(image), x=x, y=top, w=width, h=height)
        self.pdf.set_y(top + row_height)
        return True

    def _is_half(self, image: Path) -> bool:
        return any(s.id == image.stem and s.size == "half" for s in self._summary.charts)

    def _happening(self) -> None:
        items = self._summary.happening
        limit = self._layout.max_happening
        shown = items if limit is None else items[:limit]
        if not shown or not self._heading("report.happening"):
            return
        self._bullets(shown)

    def _robustness(self) -> None:
        """How robust the conclusion is per audience, then the state of the data in one line."""
        items = robustness_lines(self._summary)
        if not self._layout.all_robustness:
            items = [
                a.robustness_line
                for a in ordered_assessments(self._summary)
                if a.robustness_line and str(a.robustness) != "confirmed"
            ]
        if not items or not self._heading("report.robustness"):
            return
        self._bullets(items)
        note = self._summary.data_note
        if note and self._layout.show_data_note:
            self._paragraph(" ".join(note), self._style.small_pt, color=self._theme.muted_color)

    def _decision(self) -> None:
        """The conclusion and per-audience lines, then the next step, which always stays."""
        lines = decision_lines(self._summary)
        if not lines or not self._heading("report.decision"):
            return
        *body, next_step = lines
        limit = self._layout.max_decision
        shown = body if limit is None else body[:limit]
        self._bullets([*shown, next_step])

    # -- footer ------------------------------------------------------------------------------

    def _footer_lines(self) -> list[str]:
        """Definitions and caveats, then the months that stand out, the method and sources."""
        t, summary = self._t, self._summary
        measured = [a for a in summary.assessments if a.measured]
        bases = {a.basis for a in measured if a.basis}
        basis = t.t(f"basis.{bases.pop()}") if len(bases) == 1 else t.t("basis.mixed")
        months = {a.recent_months for a in measured if a.recent_months}
        recent = t.t("report.recent_basis", months=months.pop() if len(months) == 1 else 3)
        lines = [
            t.t("report.footer_share", basis=basis, recent=recent),
            t.t("report.footer_caveats"),
        ]
        limit = self._layout.max_caveats
        caveats = summary.limitations if limit is None else summary.limitations[:limit]
        lines += caveats
        items = [
            t.t(
                "report.footer_month_item",
                label=a.label,
                note=t.t(
                    f"chart.note.{m.nature}",
                    month=m.month,
                    multiple=t.number(max(m.multiples.values(), key=lambda v: abs(v - 1)), 1),
                ),
                change=t.percent(m.change_without, 0, signed=True),
            )
            for a in summary.assessments
            for m in a.months
            if m.in_change and m.change_without is not None
        ][:MAX_FOOTER_MONTHS]
        if items:
            lines.append(t.t("report.footer_months", items="; ".join(items)))
        provenance = summary.provenance
        generated = provenance.generated_at.strftime(GENERATED_AT_FORMAT)
        lines.append(
            " · ".join(
                [
                    t.t("report.footer_method"),
                    f"{t.t('report.sources')}: {t.t('report.sources_names')}",
                    f"{t.t('report.data_through')}: {provenance.data_through}",
                    f"{t.t('report.generated')}: {generated}",
                    f"{t.t('report.version')}: {provenance.code_version}",
                ]
            )
        )
        return lines

    def _draw_footer(self) -> float:
        """Draw the footer at the page bottom and return the y where content must end."""
        text = "\n".join(self._footer_lines())
        line_h = self._font(self._style.small_pt, color=self._theme.muted_color)
        height = cast(
            float, self.pdf.multi_cell(self.pdf.epw, line_h, text, dry_run=True, output="HEIGHT")
        )
        top = self.pdf.h - self._style.margin_mm - height
        self.pdf.set_draw_color(*_Rgb.parse(self._style.rule_color))
        rule_y = top - self._style.section_gap_mm / 2
        self.pdf.line(self.pdf.l_margin, rule_y, self.pdf.l_margin + self.pdf.epw, rule_y)
        self.pdf.set_xy(self.pdf.l_margin, top)
        self.pdf.multi_cell(
            self.pdf.epw, line_h, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        method_line_y = self.pdf.get_y() - line_h
        self.pdf.link(self.pdf.l_margin, method_line_y, self.pdf.epw / 3, line_h, METHOD_FILE)
        self.pdf.set_xy(self.pdf.l_margin, self._style.margin_mm)
        return top - self._style.section_gap_mm

    # -- appendix ----------------------------------------------------------------------------

    def draw_appendix(self, markdown: str) -> None:
        """The method on further pages: headings bold, bullets indented, text wrapped."""
        pdf, style = self.pdf, self._style
        pdf.set_auto_page_break(True, margin=style.margin_mm)
        pdf.add_page()
        for raw in markdown.splitlines():
            line = raw.rstrip()
            if not line:
                pdf.ln(self._line_height(style.small_pt) / 2)
                continue
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                size = style.heading_pt if level > 1 else style.title_pt
                height = self._font(size, bold=True, color=self._theme.accent_color)
                pdf.multi_cell(
                    pdf.epw, height, line.lstrip("# "), new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
                continue
            indent = (len(line) - len(line.lstrip())) / 2
            text = line.strip().replace("`", "")
            if text.startswith("- "):
                text = BULLET + text[2:]
            height = self._font(style.body_pt)
            pdf.set_x(pdf.l_margin + indent * TABLE_PADDING_MM * 2)
            pdf.multi_cell(
                pdf.epw - indent * TABLE_PADDING_MM * 2,
                height,
                text,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
