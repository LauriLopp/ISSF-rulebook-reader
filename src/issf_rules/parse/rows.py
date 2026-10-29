"""Turning a page's lines into reading-order items: text rows, tables and figures.

MuPDF reports the rule number ("6.11.3") and the text beside it as separate lines, and its
block order does not always follow the page from top to bottom. Here, lines on the same
baseline are merged into one row, and rows, tables and figures are ordered top to bottom.
Lines that sit inside a table or figure belong to that region, not to the text flow.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from issf_rules.extract.figures import overlap_ratio
from issf_rules.models.layout import BBox, FigureRegion, Line, PageLayout, Span, TableRegion

SAME_ROW_TOLERANCE = 3.0
"""Lines whose tops differ by less than this (points) are on the same visual row."""
INSIDE_REGION = 0.5
"""A line belongs to a table/figure if at least this share of its box lies inside it."""


@dataclass(frozen=True)
class Row:
    """One visual row of body text, made of one or more lines on the same baseline."""

    pdf_page: int
    lines: tuple[Line, ...]

    @property
    def x0(self) -> float:
        return self.lines[0].x0

    @property
    def y0(self) -> float:
        return min(line.y0 for line in self.lines)

    @property
    def size(self) -> float:
        return self.lines[0].size

    @property
    def text(self) -> str:
        """Raw text with tabs kept (a tab follows rule numbers and item labels)."""
        return "".join(text for _, text in self._pieces())

    @property
    def spans(self) -> tuple[Span, ...]:
        return tuple(span for line in self.lines for span in line.spans)

    def spans_from(self, offset: int) -> list[Span]:
        """Spans that hold `self.text` from character `offset` onwards."""
        selected: list[Span] = []
        position = 0
        for span, text in self._pieces():
            position += len(text)
            if span is not None and position > offset:
                selected.append(span)
        return selected

    def _pieces(self) -> list[tuple[Span | None, str]]:
        """The row text as span pieces, with a joining space (span None) between lines when
        the previous line does not already end in whitespace."""
        pieces: list[tuple[Span | None, str]] = []
        for line in self.lines:
            if pieces and not pieces[-1][1][-1:].isspace():
                pieces.append((None, " "))
            pieces.extend((span, span.text) for span in line.spans)
        return pieces

    @property
    def line_indices(self) -> tuple[int, ...]:
        return tuple(line.index for line in self.lines)


@dataclass(frozen=True)
class TableMark:
    pdf_page: int
    region: TableRegion
    line_indices: tuple[int, ...]


@dataclass(frozen=True)
class FigureMark:
    pdf_page: int
    region: FigureRegion
    lines: tuple[Line, ...]
    """Text printed inside the figure area (labels, dimensions)."""


PageItem = Row | TableMark | FigureMark


def page_items(page: PageLayout, lines: Sequence[Line] | None = None) -> list[PageItem]:
    """Reading-order items for `page`, built from `lines` (default: all body lines)."""
    remaining = list(page.lines if lines is None else lines)
    items: list[tuple[float, PageItem]] = []

    for table in page.tables:
        inside, remaining = _take_inside(remaining, table.bbox)
        mark = TableMark(page.pdf_page, table, tuple(line.index for line in inside))
        items.append((table.bbox[1], mark))
    for figure in page.figures:
        inside, remaining = _take_inside(remaining, figure.bbox)
        items.append((figure.bbox[1], FigureMark(page.pdf_page, figure, tuple(inside))))
    for row in group_rows(page.pdf_page, remaining):
        items.append((row.y0, row))

    # Regions sort before rows that start at the same height; ties keep insertion order.
    items.sort(key=lambda pair: pair[0])
    return [item for _, item in items]


def group_rows(pdf_page: int, lines: Sequence[Line]) -> list[Row]:
    ordered = sorted(lines, key=lambda line: (line.y0, line.x0, line.index))
    rows: list[list[Line]] = []
    for line in ordered:
        if rows and abs(line.y0 - rows[-1][0].y0) < SAME_ROW_TOLERANCE:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [
        Row(pdf_page, tuple(sorted(group, key=lambda line: (line.x0, line.index))))
        for group in rows
    ]


def _take_inside(lines: list[Line], bbox: BBox) -> tuple[list[Line], list[Line]]:
    inside = [line for line in lines if overlap_ratio(line.bbox, bbox) >= INSIDE_REGION]
    taken = {line.index for line in inside}
    return inside, [line for line in lines if line.index not in taken]
