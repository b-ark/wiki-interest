"""One-page A4 PDF report built with fpdf2.

The page reads top to bottom as an answer: the title, the answer in two or three sentences,
three cards (size of interest, its change, whether recent months confirm it), the main chart
(share of attention over time), whether the topic grows faster or slower than its whole
edition (next to a smaller chart), how robust the conclusion is with one line on the data,
what it means for the decision with the next step, further observations, run-specific
limitations, one line on what the method measures, and the footer.

It must never spill onto a second page, so the renderer draws the page on a throwaway
document, measures, and if the content overflows retries with a progressively tighter
layout: no coverage line, fewer limitation lines, fewer observations, no secondary charts, a
smaller font, no data line, and finally a layout that truncates with a pointer to
``summary.md``. Fonts come from matplotlib's bundled DejaVu Sans so Cyrillic and Central
European diacritics render without shipping font files. Metadata is fixed (no creation
timestamp) so re-runs are byte-identical.
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
    period_text,
    question_line,
    report_title,
)
from wiki_interest.adapters.report_blocks import (
    Card,
    cards,
    coverage_line,
    decision_lines,
    edition_basis,
    edition_lines,
    robustness_lines,
)
from wiki_interest.adapters.report_theme import PdfTheme, ReportTheme
from wiki_interest.contracts.summary import AnalysisSummary
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
TILE_LARGE_VALUE_MAX_ROWS = 2
"""With more rows than this a tile falls back to body-size values to stay inside its box."""
TILE_PADDING_MM = 2.0
BULLET = "•  "
FLOAT_TOLERANCE = 1e-6
MAX_CHARTS = 3
REDUCED_CHARTS = 1
"""Only the main chart is kept when the page is tight; the text says the rest."""
LIMITATION_STEPS = (2, 1)
INITIAL_MAX_FINDINGS = 2
"""Further observations on the page; ``report.md`` and ``summary.md`` list all of them."""
REDUCED_FINDINGS = 1
FIRST_FONT_STEP = 1
"""Font steps tried before the data line is dropped; the rest come after."""
ANSWER_SCALE = 1.04
"""The answer is set a little larger than body text: it is what the page is for."""
METHOD_NOTE_ITEM = 0
"""The general limitation quoted on the page (what the numbers measure); the full list is in
``report.md`` and ``summary.md``."""


@dataclass(frozen=True, slots=True)
class _Layout:
    """One attempt at fitting the page; attempts get tighter until the content fits."""

    show_data_note: bool = True
    max_limitations: int | None = None
    max_findings: int = INITIAL_MAX_FINDINGS
    show_coverage: bool = True
    font_scale: float = 1.0
    max_charts: int = MAX_CHARTS
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
        """Tightening sequence, from what the reader misses least to what they miss most.

        The coverage line goes first (it is context, and complete in ``report.md``), then
        run-specific limitations beyond the first, further observations beyond one, and the
        secondary charts (the text above them states what they show). Then a step of font
        size, and only after that the line on the state of the data (it is in ``report.md``
        in full). The answer, the cards, the main chart and the robustness lines always stay.
        """
        pdf_theme = self._theme.pdf
        scales: list[float] = []
        scale = 1.0 - pdf_theme.font_scale_step
        while scale >= pdf_theme.min_font_scale - FLOAT_TOLERANCE:
            scales.append(scale)
            scale -= pdf_theme.font_scale_step
        layout = _Layout()
        yield layout
        layout = replace(layout, show_coverage=False)
        yield layout
        for limitations in LIMITATION_STEPS:
            layout = replace(layout, max_limitations=limitations)
            yield layout
        layout = replace(layout, max_findings=REDUCED_FINDINGS)
        yield layout
        layout = replace(layout, max_charts=REDUCED_CHARTS)
        yield layout
        for scale in scales[:FIRST_FONT_STEP]:
            layout = replace(layout, font_scale=scale)
            yield layout
        layout = replace(layout, show_data_note=False)
        yield layout
        for scale in scales[FIRST_FONT_STEP:]:
            layout = replace(layout, font_scale=scale)
            yield layout
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
        self._edition_drawn = False
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

    def _bullets(self, items: Sequence[str], points: float | None = None) -> None:
        for item in items:
            if not self._paragraph(f"{BULLET}{item}", points or self._style.body_pt):
                return

    def _text_height(self, text: str, points: float, width: float) -> float:
        line_h = self._font(points)
        return cast(float, self.pdf.multi_cell(width, line_h, text, dry_run=True, output="HEIGHT"))

    def _gap(self) -> None:
        self.pdf.set_y(self.pdf.get_y() + self._style.section_gap_mm)

    # -- sections ----------------------------------------------------------------------------

    def draw(self) -> None:
        """Draw every section in order; stops early only in truncating layouts."""
        sections: list[Callable[[], None]] = [
            self._title,
            self._answer,
            self._tiles,
            self._chart_grid,
            self._vs_edition,
            self._robustness,
            self._decision,
            self._findings,
            self._limitations,
            self._method_note,
        ]
        for section in sections:
            if self._stopped:
                break
            section()

    def _title(self) -> None:
        summary, t = self._summary, self._t
        self._paragraph(report_title(summary, t), self._style.title_pt, bold=True)
        subtitle = f"{question_line(summary, t)} · {t.t('report.period')}: {period_text(summary)}"
        self._paragraph(subtitle, self._style.subtitle_pt, color=self._theme.muted_color)
        note = summary.request.report.audience_note
        if note:
            self._paragraph(note, self._style.subtitle_pt, color=self._theme.muted_color)

    def _answer(self) -> None:
        if not self._heading("report.answer"):
            return
        if not self._paragraph(
            self._summary.verdict.headline, self._style.body_pt * ANSWER_SCALE, bold=True
        ):
            return
        self._bullets(self._summary.happening)

    def _tiles(self) -> None:
        tiles = cards(self._summary, self._t)
        if not tiles:
            return
        self._gap()
        gap = self._style.tile_gap_mm
        width = (self.pdf.epw - gap * (len(tiles) - 1)) / len(tiles)
        row_count = max(len(card.rows) for card in tiles)
        value_pt = (
            self._style.tile_value_pt
            if row_count <= TILE_LARGE_VALUE_MAX_ROWS
            else self._style.body_pt
        )
        inner = width - 2 * TILE_PADDING_MM
        note_height = max(
            (self._text_height(c.note, self._style.small_pt, inner) for c in tiles if c.note),
            default=0.0,
        )
        needed = (
            2 * TILE_PADDING_MM
            + self._line_height(self._style.small_pt)
            + row_count * self._line_height(value_pt)
            + note_height
        )
        height = max(self._style.tile_height_mm * self._layout.font_scale, needed)
        if not self._fits(height):
            return
        top = self.pdf.get_y()
        for index, card in enumerate(tiles):
            origin = (self.pdf.l_margin + index * (width + gap), top)
            self._draw_tile(origin, (width, height), card, value_pt)
        self.pdf.set_y(top + height)

    def _draw_tile(
        self,
        origin: tuple[float, float],
        size: tuple[float, float],
        card: Card,
        value_pt: float,
    ) -> None:
        (x, y), (w, h) = origin, size
        pdf = self.pdf
        inner = w - 2 * TILE_PADDING_MM
        pdf.set_fill_color(*_Rgb.parse(self._style.tile_fill))
        pdf.rect(x, y, w, h, style="F")
        pdf.set_xy(x + TILE_PADDING_MM, y + TILE_PADDING_MM)
        label_h = self._font(self._style.small_pt, color=self._theme.muted_color)
        pdf.cell(inner, label_h, card.label)
        line_h = self._font(value_pt, bold=True)
        for offset, row in enumerate(card.rows):
            pdf.set_xy(x + TILE_PADDING_MM, y + TILE_PADDING_MM + label_h + offset * line_h)
            pdf.cell(inner, line_h, row)
        if card.note:
            pdf.set_xy(x + TILE_PADDING_MM, y + TILE_PADDING_MM + label_h + len(card.rows) * line_h)
            note_h = self._font(self._style.small_pt, color=self._theme.muted_color)
            pdf.multi_cell(inner, note_h, card.note, align="L")

    def _chart_grid(self) -> None:
        """The main chart across the page, then the smaller ones side by side.

        A lone half-width chart shares its row with the topic-against-edition lines, which
        is the question it illustrates, so the row carries no empty half.
        """
        images = [c for c in self._charts if c.suffix.lower() == ".png"][: self._layout.max_charts]
        if not images:
            return
        main, rest = images[0], images[1:]
        if not self._chart_row([main]):
            return
        if len(rest) == 1 and self._is_half(rest[0]) and edition_lines(self._summary):
            self._chart_beside_text(rest[0])
        elif rest:
            self._chart_row(rest)

    def _chart_box(self, image: Path, slot: float) -> tuple[float, float]:
        with Image.open(image) as opened:
            pixel_w, pixel_h = opened.size
        width, height = slot, slot * pixel_h / pixel_w
        max_height = self._style.chart_max_height_mm * self._layout.font_scale
        if height > max_height:
            width, height = max_height * pixel_w / pixel_h, max_height
        return width, height

    def _chart_row(self, images: Sequence[Path]) -> bool:
        gap = self._style.chart_gap_mm
        columns = 2 if len(images) > 1 or self._is_half(images[0]) else 1
        slot = (self.pdf.epw - gap * (columns - 1)) / columns
        boxes = [self._chart_box(image, slot) for image in images]
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

    def _chart_beside_text(self, image: Path) -> None:
        """A half-width chart on the left, the topic-against-edition section on the right."""
        gap = self._style.chart_gap_mm
        slot = (self.pdf.epw - gap) / 2
        width, height = self._chart_box(image, slot)
        heading, lines = self._edition_texts()
        body = "\n".join(f"{BULLET}{line}" for line in lines)
        text_h = self._text_height(heading, self._style.heading_pt, slot) + self._text_height(
            body, self._style.body_pt, slot
        )
        self._gap()
        if not self._fits(max(height, text_h)):
            return
        top = self.pdf.get_y()
        self.pdf.image(str(image), x=self.pdf.l_margin, y=top, w=width, h=height)
        x = self.pdf.l_margin + slot + gap
        self.pdf.set_xy(x, top)
        line_h = self._font(self._style.heading_pt, bold=True, color=self._theme.accent_color)
        self.pdf.multi_cell(slot, line_h, heading, align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        line_h = self._font(self._style.body_pt)
        self.pdf.multi_cell(slot, line_h, body, align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.pdf.set_xy(self.pdf.l_margin, top + max(height, text_h))
        self._edition_drawn = True

    def _is_half(self, image: Path) -> bool:
        return any(s.id == image.stem and s.size == "half" for s in self._summary.charts)

    def _edition_texts(self) -> tuple[str, list[str]]:
        """Heading and lines of the topic-against-edition section, the basis last."""
        lines = edition_lines(self._summary)
        basis = edition_basis(self._summary, self._t)
        return self._t.t("report.vs_edition"), [*lines, *([basis] if basis else [])]

    def _vs_edition(self) -> None:
        """Whether the topic grows faster or slower than its edition, one line per audience."""
        if self._edition_drawn or not edition_lines(self._summary):
            return
        if not self._heading("report.vs_edition"):
            return
        self._bullets(edition_lines(self._summary))
        basis = edition_basis(self._summary, self._t)
        if basis:
            self._paragraph(basis, self._style.small_pt, color=self._theme.muted_color)

    def _decision(self) -> None:
        lines = decision_lines(self._summary)
        if not lines or not self._heading("report.decision"):
            return
        self._bullets(lines)

    def _findings(self) -> None:
        items = self._summary.verdict.bullets
        shown = items[: self._layout.max_findings]
        if not shown or not self._heading("report.other_findings"):
            return
        self._bullets(shown)

    def _robustness(self) -> None:
        """How robust the conclusion is per audience, then the state of the data in one line."""
        items = robustness_lines(self._summary)
        if not items or not self._heading("report.robustness"):
            return
        self._bullets(items)
        note = self._summary.data_note
        if note and self._layout.show_data_note:
            self._paragraph(" ".join(note), self._style.small_pt, color=self._theme.muted_color)
        coverage = coverage_line(self._summary, self._t)
        if coverage and self._layout.show_coverage:
            self._paragraph(coverage, self._style.small_pt, color=self._theme.muted_color)

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

    def _method_note(self) -> None:
        notes = self._summary.general_limitations
        if not notes:
            return
        self._gap()
        text = f"{self._t.t('report.method_note')}: {notes[METHOD_NOTE_ITEM]}"
        self._paragraph(text, self._style.small_pt, color=self._theme.muted_color)

    def _draw_footer(self) -> float:
        """Draw the footer at the page bottom and return the y where content must end."""
        t, provenance = self._t, self._summary.provenance
        generated = provenance.generated_at.strftime(GENERATED_AT_FORMAT)
        text = " · ".join(
            [
                f"{t.t('report.sources')}: {t.t('report.sources_names')}",
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
