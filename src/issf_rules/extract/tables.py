"""Table detection with PyMuPDF's table finder (ADR 0002; Docling comparison is task T4).

PyMuPDF supplies the cell grid only. Cell text is rebuilt from the page's own text spans,
because `Table.extract()` scrambles ligatures ("fl" in "Rifle" comes out as "Rifel"); the spans
read by `extract.lines` have them right.
"""

from __future__ import annotations

from collections.abc import Sequence

import pymupdf

from issf_rules.extract.lines import round_bbox
from issf_rules.models.layout import BBox, Line, TableRegion
from issf_rules.textnorm import join_lines


def find_tables(page: pymupdf.Page, lines: Sequence[Line]) -> list[TableRegion]:
    """Return tables, top to bottom. Single cells (1x1) are boxed text, not tables.

    Single-row tables are kept: a table continued from the previous page often has just one
    (tall) row, e.g. the finals procedure grids in GTR 6.17.
    """
    regions: list[TableRegion] = []
    for table in page.find_tables().tables:
        rows = tuple(
            tuple(None if cell is None else cell_text(lines, cell) for cell in row.cells)
            for row in table.rows
        )
        if len(rows) < 2 and max((len(row) for row in rows), default=0) < 2:
            continue
        regions.append(TableRegion(index=0, bbox=round_bbox(table.bbox), rows=rows))
    regions.sort(key=lambda region: (region.bbox[1], region.bbox[0]))
    return [region.model_copy(update={"index": i}) for i, region in enumerate(regions)]


def cell_text(lines: Sequence[Line], cell: Sequence[float]) -> str | None:
    """Text of the spans whose centre lies in `cell`, one piece per line, joined like a
    paragraph. None for an empty cell."""
    x0, y0, x1, y1 = cell
    pieces = []
    for line in sorted(lines, key=lambda line: (line.bbox[1], line.bbox[0])):
        inside = "".join(span.text for span in line.spans if _centre_in(span.bbox, x0, y0, x1, y1))
        if inside.strip():
            pieces.append(inside.replace("\t", " "))
    return join_lines(pieces) or None


def _centre_in(bbox: BBox, x0: float, y0: float, x1: float, y1: float) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return x0 <= cx <= x1 and y0 <= cy <= y1
