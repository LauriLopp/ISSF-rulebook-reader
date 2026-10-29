"""Builders for hand-made layout objects, so unit tests need no PDF."""

from __future__ import annotations

import datetime as dt
from itertools import count

from issf_rules.models.layout import Line, PageFooter, PageLayout, Span, TableRegion
from issf_rules.models.source import SourceDocument
from issf_rules.parse.rows import Row

_indices = count()

SOURCE = SourceDocument(
    id="test-book",
    document="test",
    title="Test Rule Book",
    edition="Edition 2030",
    print_run="First Print 01/2030",
    effective=dt.date(2030, 1, 1),
    url="https://example.invalid/book.pdf",
    filename="book.pdf",
    sha256="0" * 64,
)


def span(text: str, x: float, y: float, size: float = 11.8, bold: bool = False) -> Span:
    width = 6.0 * len(text)
    return Span(
        text=text,
        font="Arial-BoldMT" if bold else "ArialMT",
        size=size,
        bold=bold,
        italic=False,
        bbox=(x, y, x + width, y + size),
    )


def line(
    text: str,
    x: float,
    y: float,
    size: float = 11.8,
    bold: bool = False,
    index: int | None = None,
    block: int = 0,
) -> Line:
    s = span(text, x, y, size, bold)
    return Line(
        index=next(_indices) if index is None else index, block=block, bbox=s.bbox, spans=(s,)
    )


def row(page: int, *lines: Line) -> Row:
    return Row(pdf_page=page, lines=tuple(lines))


def page(
    number: int,
    lines: list[Line],
    tables: tuple[TableRegion, ...] = (),
    footer: str | None = "EDITION 2030 (First Print 01/2030)  Effective 1 January 2030  © T",
) -> PageLayout:
    numbered = tuple(ln.model_copy(update={"index": i}) for i, ln in enumerate(lines))
    return PageLayout(
        pdf_page=number,
        width=595.0,
        height=842.0,
        footer=PageFooter(text=f"{footer}  {number}", printed_page=str(number)) if footer else None,
        lines=numbered,
        tables=tables,
    )
