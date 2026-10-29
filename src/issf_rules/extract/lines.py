"""Reading text lines with font information from a PDF page."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pymupdf

from issf_rules.models.layout import BBox, Line, Span
from issf_rules.textnorm import strip_controls

# MuPDF span flags (see the PyMuPDF "TextPage" documentation).
_FLAG_ITALIC = 2
_FLAG_BOLD = 16


def round_bbox(values: Sequence[float]) -> BBox:
    x0, y0, x1, y1 = (round(float(v), 1) for v in values)
    return (x0, y0, x1, y1)


def read_lines(page: pymupdf.Page) -> list[Line]:
    """Return the page's non-blank text lines, in MuPDF's block/line order."""
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    data: dict[str, Any] = page.get_text("dict", flags=flags)
    lines: list[Line] = []
    for block in data["blocks"]:
        if block.get("type") != 0:
            continue
        for raw_line in block["lines"]:
            spans = tuple(
                span for span in (_to_span(raw) for raw in raw_line["spans"]) if span.text
            )
            if not any(span.text.strip() for span in spans):
                continue
            lines.append(
                Line(
                    index=len(lines),
                    block=int(block["number"]),
                    bbox=round_bbox(raw_line["bbox"]),
                    spans=spans,
                )
            )
    return lines


def _to_span(raw: dict[str, Any]) -> Span:
    font = str(raw["font"])
    flags = int(raw["flags"])
    return Span(
        text=strip_controls(str(raw["text"])),
        font=font,
        size=round(float(raw["size"]), 1),
        bold=bool(flags & _FLAG_BOLD) or "Bold" in font,
        italic=bool(flags & _FLAG_ITALIC) or "Italic" in font or "Oblique" in font,
        bbox=round_bbox(raw["bbox"]),
    )
