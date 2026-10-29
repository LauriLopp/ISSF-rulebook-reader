"""Running the stages and moving their artefacts to and from disk.

Each stage reads only the previous stage's files, so any stage can be re-run on its own (for
example, re-parse after a parser fix without re-extracting the PDF).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from issf_rules.extract import extract_pdf
from issf_rules.fetch import ensure_source, find_source, load_manifest
from issf_rules.jsonl import read_json, read_jsonl, write_json, write_jsonl, write_text
from issf_rules.models.layout import PageLayout
from issf_rules.models.records import (
    Division,
    FigureRecord,
    LineAssignment,
    ParsedDocument,
    RuleRecord,
    TableRecord,
)
from issf_rules.models.report import ValidationReport
from issf_rules.models.source import SourceDocument
from issf_rules.parse import parse_document
from issf_rules.paths import ArtefactPaths
from issf_rules.prepare import prepare_records
from issf_rules.review import write_spotcheck
from issf_rules.validate import render_markdown, validate


class MissingArtefactError(FileNotFoundError):
    """A stage was run before the stage it depends on."""


@dataclass(frozen=True)
class Context:
    source: SourceDocument
    paths: ArtefactPaths

    @classmethod
    def load(cls, manifest: Path, data_dir: Path, source_id: str | None) -> Context:
        source = find_source(load_manifest(manifest), source_id)
        return cls(source=source, paths=ArtefactPaths(data_dir=data_dir, sha256=source.sha256))


def run_fetch(ctx: Context) -> Path:
    return ensure_source(ctx.source, ctx.paths.sources_dir)


def run_extract(ctx: Context, render_figures: bool = True) -> list[PageLayout]:
    pdf = ensure_source(ctx.source, ctx.paths.sources_dir)
    pages = extract_pdf(pdf, ctx.paths.figures_dir if render_figures else None)
    write_jsonl(ctx.paths.layout, pages)
    return pages


def run_parse(ctx: Context) -> ParsedDocument:
    parsed = parse_document(ctx.source, load_layout(ctx))
    p = ctx.paths
    write_json(p.source, parsed.source)
    write_jsonl(p.divisions, parsed.divisions)
    write_jsonl(p.rules, parsed.rules)
    write_jsonl(p.tables, parsed.tables)
    write_jsonl(p.figures, parsed.figures)
    write_jsonl(p.coverage, parsed.assignments)
    return parsed


def run_validate(ctx: Context) -> ValidationReport:
    report = validate(load_parsed(ctx), load_layout(ctx))
    write_json(ctx.paths.report_json, report)
    write_text(ctx.paths.report_md, render_markdown(report))
    return report


def run_prepare(ctx: Context) -> int:
    return write_jsonl(ctx.paths.retrieval, prepare_records(load_parsed(ctx)))


def run_spotcheck(ctx: Context, only: Sequence[int] | None = None) -> int:
    """Write the spot-check sheet (a review tool, not a stage; see `review.spotcheck`)."""
    _require(ctx.paths.report_json, "validate")
    pdf = ensure_source(ctx.source, ctx.paths.sources_dir)
    report = read_json(ctx.paths.report_json, ValidationReport)
    return write_spotcheck(
        pdf, load_parsed(ctx), load_layout(ctx), report, ctx.paths.spotcheck_dir, only
    )


def load_layout(ctx: Context) -> list[PageLayout]:
    _require(ctx.paths.layout, "extract")
    return read_jsonl(ctx.paths.layout, PageLayout)


def load_parsed(ctx: Context) -> ParsedDocument:
    p = ctx.paths
    for path in (p.source, p.divisions, p.rules, p.tables, p.figures, p.coverage):
        _require(path, "parse")
    return ParsedDocument(
        source=read_json(p.source, SourceDocument),
        divisions=tuple(read_jsonl(p.divisions, Division)),
        rules=tuple(read_jsonl(p.rules, RuleRecord)),
        tables=tuple(read_jsonl(p.tables, TableRecord)),
        figures=tuple(read_jsonl(p.figures, FigureRecord)),
        assignments=tuple(read_jsonl(p.coverage, LineAssignment)),
    )


def _require(path: Path, stage: str) -> None:
    if not path.exists():
        raise MissingArtefactError(f"{path} not found; run the '{stage}' stage first")
