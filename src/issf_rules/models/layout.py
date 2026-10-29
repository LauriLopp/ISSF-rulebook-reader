"""Output of the extract stage: the physical layout of each PDF page.

Nothing here interprets rule structure. It records what is on the page (text lines with font
information, table cells, figure regions) together with exact positions, so later stages can be
re-run without touching the PDF again.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

BBox = tuple[float, float, float, float]
"""(x0, y0, x1, y1) in PDF points, origin top-left, rounded to 0.1 pt."""


class Span(BaseModel):
    """A run of text with uniform font, as reported by MuPDF."""

    model_config = ConfigDict(frozen=True)

    text: str
    font: str
    size: float
    bold: bool
    italic: bool
    bbox: BBox


class Line(BaseModel):
    """One text line. `index` is unique within its page and is the unit of coverage tracking."""

    model_config = ConfigDict(frozen=True)

    index: int
    block: int
    bbox: BBox
    spans: tuple[Span, ...]

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def size(self) -> float:
        """Font size of the first non-blank span (the line's dominant size in practice)."""
        for span in self.spans:
            if span.text.strip():
                return span.size
        return self.spans[0].size if self.spans else 0.0


class PageFooter(BaseModel):
    """The running footer on every page: "EDITION 2025 (...)  Effective ...  © ISSF  12"."""

    model_config = ConfigDict(frozen=True)

    text: str
    printed_page: str | None


class TableRegion(BaseModel):
    """A table found on the page. `rows` holds cell text; None marks a merged/empty cell."""

    model_config = ConfigDict(frozen=True)

    index: int
    bbox: BBox
    rows: tuple[tuple[str | None, ...], ...]


class FigureRegion(BaseModel):
    """A raster image placed on the page."""

    model_config = ConfigDict(frozen=True)

    index: int
    bbox: BBox
    image_file: str | None = None
    """Path of the rendered crop, relative to the artefact directory (None if not rendered)."""


class PageLayout(BaseModel):
    """Everything the extract stage knows about one page."""

    model_config = ConfigDict(frozen=True)

    pdf_page: int
    """1-based page index in the PDF file."""
    width: float
    height: float
    footer: PageFooter | None
    lines: tuple[Line, ...]
    """Body lines (footer excluded), in MuPDF order."""
    tables: tuple[TableRegion, ...] = ()
    figures: tuple[FigureRegion, ...] = ()
