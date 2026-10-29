"""Extract stage: PDF → per-page layout (lines with fonts, tables, figures, footer)."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from issf_rules.extract.figures import find_figures, render_figure
from issf_rules.extract.footer import split_footer
from issf_rules.extract.lines import read_lines
from issf_rules.extract.tables import find_tables
from issf_rules.models.layout import PageLayout


def extract_pdf(pdf_path: Path, figures_dir: Path | None = None) -> list[PageLayout]:
    """Read every page of `pdf_path`.

    If `figures_dir` is given, each figure is rendered to `<figures_dir>/p<page>-<n>.png` and
    the path (relative to the parent of `figures_dir`) is stored on the figure region.
    """
    pages: list[PageLayout] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            pages.append(extract_page(page, figures_dir))
    return pages


def extract_page(page: pymupdf.Page, figures_dir: Path | None = None) -> PageLayout:
    pdf_page = page.number + 1
    footer, body = split_footer(read_lines(page), page.rect.height)
    tables = find_tables(page, body)
    figures = find_figures(page)
    if figures_dir is not None:
        rendered = []
        for figure in figures:
            target = figures_dir / f"p{pdf_page:04d}-{figure.index}.png"
            render_figure(page, figure.bbox, target)
            relative = target.relative_to(figures_dir.parent).as_posix()
            rendered.append(figure.model_copy(update={"image_file": relative}))
        figures = rendered
    return PageLayout(
        pdf_page=pdf_page,
        width=round(page.rect.width, 1),
        height=round(page.rect.height, 1),
        footer=footer,
        lines=tuple(body),
        tables=tuple(tables),
        figures=tuple(figures),
    )
