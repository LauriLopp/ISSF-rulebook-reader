"""The spot-check sheet: each PDF page next to the records parsed from it.

Automated checks prove that no text is lost or altered, but not that it went to the right
record, that a guessed heading is right, or that table cells are in order. This sheet makes
that quick to judge by eye. Every page shows its render with a box around each record, and
beside it those records as parsed.

Pages are selected by what is worth a look, found in the data (never by page number): guessed
headings, rules continuing from the previous page, tables, table warnings, definitions, and
other validation findings. Output is local HTML under the artefact directory, which is
gitignored: it shows rulebook content.
"""

from __future__ import annotations

import html
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import pymupdf

from issf_rules.models.layout import BBox, PageLayout
from issf_rules.models.records import FigureRecord, ParsedDocument, RuleRecord, TableRecord
from issf_rules.models.report import ValidationReport

DPI = 100
REASONS = {
    "guessed heading": "Short non-bold text after a rule number was taken as its heading",
    "page break": "A rule continues from the previous page",
    "table": "The page has a table: check rows and cell order",
    "table warning": "A table-quality finding",
    "definition": "Definitions were taken from this page",
    "figure": "The page has a figure: check that it belongs to the rule it is attached to",
    "finding": "An error or warning from the validation report",
}
_COLOURS = ("#c0392b", "#2471a3", "#1e8449", "#b9770e", "#7d3c98", "#117a65", "#a04000")


def page_reasons(parsed: ParsedDocument, report: ValidationReport) -> dict[int, set[str]]:
    """Why each page is worth checking; pages with nothing notable are left out."""
    reasons: dict[int, set[str]] = defaultdict(set)
    for rule in parsed.rules:
        if not rule.pages:
            continue
        if "heading-not-bold" in rule.parse_flags:
            reasons[rule.pages[0].pdf_page].add("guessed heading")
        if rule.kind == "definition":
            for ref in rule.pages:
                reasons[ref.pdf_page].add("definition")
        elif len(rule.pages) > 1:
            for ref in rule.pages[1:]:
                reasons[ref.pdf_page].add("page break")
    for table in parsed.tables:
        reasons[table.page.pdf_page].add("table")
    for figure in parsed.figures:
        reasons[figure.page.pdf_page].add("figure")
    for finding in report.findings:
        if finding.pdf_page is None or finding.severity == "info":
            continue
        kind = "table warning" if finding.check == "table-quality" else "finding"
        reasons[finding.pdf_page].add(kind)
    return dict(reasons)


def write_spotcheck(
    pdf: Path,
    parsed: ParsedDocument,
    pages: Sequence[PageLayout],
    report: ValidationReport,
    out_dir: Path,
    only: Iterable[int] | None = None,
) -> int:
    """Write `out_dir/index.html` and one page file per selected page. Returns the count."""
    reasons = page_reasons(parsed, report)
    selected = sorted(set(only) if only is not None else reasons)
    layouts = {page.pdf_page: page for page in pages}
    on_page = _records_by_page(parsed.rules)
    tables = {table.uid: table for table in parsed.tables}
    figures = {figure.uid: figure for figure in parsed.figures}
    findings: dict[int, list[str]] = defaultdict(list)
    for f in report.findings:
        if f.pdf_page is not None and f.severity != "info":
            findings[f.pdf_page].append(f"{f.severity}: {f.check}: {f.message}")
    titles = {d.namespace: d.title for d in parsed.divisions}

    (out_dir / "img").mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as doc:
        for n, number in enumerate(selected):
            doc[number - 1].get_pixmap(dpi=DPI).save(out_dir / "img" / f"p{number:04d}.png")
            neighbours = (
                selected[n - 1] if n > 0 else None,
                selected[n + 1] if n + 1 < len(selected) else None,
            )
            body = _page_html(
                layouts[number],
                on_page.get(number, []),
                tables,
                figures,
                sorted(reasons.get(number, ())),
                findings.get(number, []),
                neighbours,
            )
            _write(out_dir / f"p{number:04d}.html", f"Page {number}", body)
    _write(out_dir / "index.html", "Spot-check", _index_html(selected, reasons, on_page, titles))
    return len(selected)


def _records_by_page(rules: Sequence[RuleRecord]) -> dict[int, list[RuleRecord]]:
    by_page: dict[int, list[RuleRecord]] = defaultdict(list)
    for rule in rules:
        for ref in rule.pages:
            by_page[ref.pdf_page].append(rule)
    return by_page


def _page_html(
    layout: PageLayout,
    records: Sequence[RuleRecord],
    tables: Mapping[str, TableRecord],
    figures: Mapping[str, FigureRecord],
    reasons: Sequence[str],
    findings: Sequence[str],
    neighbours: tuple[int | None, int | None],
) -> str:
    number = layout.pdf_page
    boxes = []
    cards = []
    for i, rule in enumerate(records):
        colour = _COLOURS[i % len(_COLOURS)]
        label = _short(rule)
        dashed = rule.kind == "definition"
        for ref in rule.pages:
            # A definition from a table shares the table's box; drawing it adds only clutter.
            if ref.pdf_page == number and not (dashed and rule.table_uids):
                boxes.append(_box(ref.bbox, colour, label, dashed))
        cards.append(_card(rule, number, colour, tables, figures))
        for uid in rule.figure_uids:
            figure = figures.get(uid)
            if figure is not None and figure.page.pdf_page == number:
                boxes.append(_box(figure.page.bbox, colour, f"figure \u2192 {label}", True))
    for table in layout.tables:
        boxes.append(_box(table.bbox, "#555", f"table {table.index}", dashed=True))

    previous, following = neighbours
    nav = " · ".join(
        part
        for part in (
            f'<a href="p{previous:04d}.html">← p. {previous}</a>' if previous else "",
            '<a href="index.html">index</a>',
            f'<a href="p{following:04d}.html">p. {following} →</a>' if following else "",
        )
        if part
    )
    printed = (
        layout.footer.printed_page if layout.footer and layout.footer.printed_page else "\u2013"
    )
    tags = "".join(f'<span class="tag" title="{REASONS[r]}">{r}</span>' for r in reasons)
    notes = "".join(f"<li>{html.escape(f)}</li>" for f in findings)
    svg = (
        f'<svg viewBox="0 0 {layout.width} {layout.height}" class="page">'
        f'<image href="img/p{number:04d}.png" width="{layout.width}" height="{layout.height}"/>'
        f"{''.join(boxes)}</svg>"
    )
    return (
        f"<header><nav>{nav}</nav><h1>PDF page {number} <small>(printed {printed})</small></h1>"
        f"{tags}{f'<ul class=findings>{notes}</ul>' if notes else ''}</header>"
        f'<main><div class="left">{svg}</div><div class="right">{"".join(cards)}</div></main>'
        f"<script>{_KEYS}</script>"
    )


def _box(bbox: BBox, colour: str, label: str, dashed: bool) -> str:
    x0, y0, x1, y1 = bbox
    dash = ' stroke-dasharray="4 3"' if dashed else ""
    return (
        f'<rect x="{x0 - 2}" y="{y0 - 2}" width="{x1 - x0 + 4}" height="{y1 - y0 + 4}" '
        f'fill="none" stroke="{colour}" stroke-width="1.2"{dash}/>'
        f'<text x="{x0 - 2}" y="{y0 - 4}" fill="{colour}" font-size="7">'
        f"{html.escape(label)}</text>"
    )


def _card(
    rule: RuleRecord,
    page: int,
    colour: str,
    tables: Mapping[str, TableRecord],
    figures: Mapping[str, FigureRecord],
) -> str:
    other = [ref.pdf_page for ref in rule.pages if ref.pdf_page != page]
    span = f" · also on p. {', '.join(map(str, other))}" if other else ""
    meta = [rule.kind, *rule.parse_flags]
    if rule.items:
        meta.append("items: " + " ".join(item.label for item in rule.items))
    head = html.escape(" ".join(p for p in (rule.printed_number, rule.heading) if p) or "—")
    table_html = "".join(
        _table(tables[uid])
        for uid in rule.table_uids
        if uid in tables and rule.kind != "definition"
    )
    return (
        f'<section style="border-left-color:{colour}">'
        f'<div class="uid" style="color:{colour}">{html.escape(_short(rule))}{span}</div>'
        f"<h2>{head}</h2>"
        f'<div class="path">{html.escape(" \u203a ".join(rule.heading_path))}</div>'
        f'<div class="meta">{html.escape(" · ".join(meta))}</div>'
        f"<pre>{html.escape(rule.official_text)}</pre>{table_html}"
        f"{''.join(_figure(figures[uid]) for uid in rule.figure_uids if uid in figures)}"
        "</section>"
    )


def _table(table: TableRecord) -> str:
    rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell or '')}</td>" for cell in row) + "</tr>"
        for row in table.rows
    )
    return (
        f'<div class="tablewrap"><div class="meta">{table.uid.rsplit(":", 1)[-1]}</div>'
        f"<table>{rows}</table></div>"
    )


def _figure(figure: FigureRecord) -> str:
    name = figure.uid.rsplit(":", 1)[-1]
    where = f"figure {name}, p. {figure.page.pdf_page}"
    if figure.image_file is None:
        return f'<div class="meta">{where} (not rendered; run extract with figures)</div>'
    # Figure crops live in the artefact directory, one level above this sheet.
    return (
        f'<figure><img src="../{html.escape(figure.image_file)}" alt="{where}">'
        f"<figcaption>{where}</figcaption></figure>"
    )


def _index_html(
    selected: Sequence[int],
    reasons: Mapping[int, set[str]],
    on_page: Mapping[int, Sequence[RuleRecord]],
    titles: Mapping[str, str],
) -> str:
    counts = {r: sum(1 for p in selected if r in reasons.get(p, ())) for r in REASONS}
    buttons = "".join(
        f'<label title="{REASONS[r]}"><input type="checkbox" value="{r}" checked> {r} '
        f"({counts[r]})</label>"
        for r in REASONS
        if counts[r]
    )
    rows = []
    for number in selected:
        records = on_page.get(number, [])
        numbered = [r.rule_id for r in records if r.rule_id]
        span = f"{numbered[0]} \u2013 {numbered[-1]}" if len(numbered) > 1 else "".join(numbered)
        division = titles.get(records[0].namespace, "") if records else ""
        tags = sorted(reasons.get(number, ()))
        rows.append(
            f'<tr data-tags="{"|".join(tags)}"><td><a href="p{number:04d}.html">{number}</a></td>'
            f"<td>{html.escape(division)}</td><td>{html.escape(span)}</td>"
            f"<td>{''.join(f'<span class=tag>{t}</span>' for t in tags)}</td></tr>"
        )
    return (
        "<header><h1>Spot-check</h1><p>Each page shows the PDF next to the records parsed from "
        "it. Check that every box holds the right text, headings are real headings, and table "
        "cells are in order. Arrow keys move between pages.</p>"
        f'<div class="filters">{buttons}</div></header>'
        "<table class=index><tr><th>PDF page</th><th>Part</th><th>Rules</th><th>Why</th></tr>"
        f"{''.join(rows)}</table><script>{_FILTER}</script>"
    )


def _short(rule: RuleRecord) -> str:
    return rule.uid.split(":", 1)[1]


def _write(path: Path, title: str, body: str) -> None:
    page = (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>'
        f"<style>{_CSS}</style></head><body>{body}</body></html>"
    )
    path.write_text(page, encoding="utf-8")


_KEYS = """
document.addEventListener('keydown', e => {
  const links = [...document.querySelectorAll('nav a')];
  const go = t => {
    const a = links.find(l => l.textContent.includes(t));
    if (a) location = a.href;
  };
  if (e.key === 'ArrowLeft') go('←');
  if (e.key === 'ArrowRight') go('→');
});"""

_FILTER = """
const boxes = [...document.querySelectorAll('.filters input')];
function apply() {
  const on = new Set(boxes.filter(b => b.checked).map(b => b.value));
  for (const tr of document.querySelectorAll('tr[data-tags]')) {
    tr.hidden = !tr.dataset.tags.split('|').some(t => on.has(t));
  }
}
boxes.forEach(b => b.addEventListener('change', apply));"""

_CSS = """
body { font: 14px/1.4 system-ui, sans-serif; margin: 0; padding: 12px 16px; color: #222;
  background: #fafafa; }
header h1 { font-size: 18px; margin: 4px 0; } header small { color: #777; font-weight: normal; }
nav { margin-bottom: 4px; } a { color: #2471a3; }
.tag { display: inline-block; background: #eef; border-radius: 3px; padding: 0 6px;
  margin: 2px 4px 2px 0; font-size: 12px; }
.findings { color: #a00; font-size: 13px; margin: 4px 0; }
main { display: flex; gap: 16px; align-items: flex-start; }
.left { flex: 0 0 48%; position: sticky; top: 8px; }
.page { width: 100%; background: white; box-shadow: 0 0 4px #aaa; }
.right { flex: 1; min-width: 0; }
section { background: white; border-left: 4px solid; padding: 6px 10px; margin-bottom: 10px; }
section h2 { font-size: 15px; margin: 2px 0; } .uid { font: 12px monospace; }
.path, .meta { color: #666; font-size: 12px; }
pre { white-space: pre-wrap; font: 13px/1.45 system-ui, sans-serif; margin: 6px 0; }
.tablewrap { overflow-x: auto; } table { border-collapse: collapse; margin: 4px 0; }
td, th { border: 1px solid #ccc; padding: 2px 5px; vertical-align: top; font-size: 12px; }
.index td { font-size: 13px; } .filters label { margin-right: 12px; }
figure { margin: 6px 0; } figure img { max-width: 100%; max-height: 260px; border: 1px solid #ddd; }
figcaption { color: #666; font-size: 12px; }
"""
