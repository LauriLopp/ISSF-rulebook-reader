"""Finding figures and rendering them for display.

The PDF's own figure alt text is unusable (auto-generated or file paths, see the M1 report), so
figures are located geometrically. Only raster images count as figures: in the current rulebook
every vector-drawn region turned out to be a form field, a text box or a table grid, never a
drawing. Revisit this if a new edition introduces vector diagrams.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from issf_rules.extract.lines import round_bbox
from issf_rules.models.layout import BBox, FigureRegion

MIN_FIGURE_SIZE = 20.0
"""Smaller images (bullets, icons, decorations) are not figures. In PDF points."""
RENDER_DPI = 150


def find_figures(page: pymupdf.Page) -> list[FigureRegion]:
    boxes = [round_bbox(info["bbox"]) for info in page.get_image_info()]
    # The same image can be placed twice at one spot; keep one, ordered top to bottom.
    unique = sorted(
        {bbox for bbox in boxes if _big_enough(bbox)},
        key=lambda bbox: (bbox[1], bbox[0], bbox[3], bbox[2]),
    )
    return [FigureRegion(index=i, bbox=bbox) for i, bbox in enumerate(unique)]


def render_figure(page: pymupdf.Page, bbox: BBox, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(clip=pymupdf.Rect(bbox), dpi=RENDER_DPI).save(str(target))


def overlap_ratio(inner: BBox, outer: BBox) -> float:
    """Share of `inner`'s area that lies inside `outer` (0.0-1.0)."""
    width = min(inner[2], outer[2]) - max(inner[0], outer[0])
    height = min(inner[3], outer[3]) - max(inner[1], outer[1])
    if width <= 0 or height <= 0:
        return 0.0
    area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return (width * height) / area if area > 0 else 0.0


def _big_enough(bbox: BBox) -> bool:
    return bbox[2] - bbox[0] >= MIN_FIGURE_SIZE and bbox[3] - bbox[1] >= MIN_FIGURE_SIZE
