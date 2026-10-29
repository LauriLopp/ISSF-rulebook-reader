"""Turning drafts into final, immutable records with uids, heading paths and provenance."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from issf_rules.models.layout import BBox
from issf_rules.models.records import (
    Division,
    FigureRecord,
    LineAssignment,
    PageRef,
    RuleItem,
    RuleRecord,
    TableRecord,
)
from issf_rules.parse.builder import Block, Draft
from issf_rules.parse.definitions import definition_record, paragraph_entries
from issf_rules.parse.patterns import parent_rule_id, rule_level
from issf_rules.textnorm import join_lines


@dataclass
class Assembled:
    rules: list[RuleRecord] = field(default_factory=list)
    tables: list[TableRecord] = field(default_factory=list)
    figures: list[FigureRecord] = field(default_factory=list)
    assignments: list[LineAssignment] = field(default_factory=list)


def assemble_division(
    source_id: str,
    division: Division,
    drafts: Sequence[Draft],
    printed_pages: Mapping[int, str | None],
) -> Assembled:
    out = Assembled()
    used_uids: set[str] = set()
    headings: dict[str, str | None] = {}  # first occurrence of each rule_id in this division

    for draft in drafts:
        uid, duplicate = _unique_uid(
            source_id, division.namespace, draft.rule_id or draft.key, used_uids
        )
        flags = list(draft.flags) + (["duplicate-id"] if duplicate else [])
        if draft.rule_id is not None:
            headings.setdefault(draft.rule_id, draft.heading)

        table_uids = []
        for mark in draft.tables:
            table_uid = f"{source_id}:table:p{mark.pdf_page:04d}-{mark.region.index}"
            table_uids.append(table_uid)
            out.tables.append(
                TableRecord(
                    uid=table_uid,
                    rule_uid=uid,
                    page=_page_ref(mark.pdf_page, [mark.region.bbox], printed_pages),
                    rows=mark.region.rows,
                )
            )
            out.assignments.extend(
                LineAssignment(pdf_page=mark.pdf_page, line_index=i, consumer=table_uid)
                for i in mark.line_indices
            )
        figure_uids = []
        for figure in draft.figures:
            figure_uid = f"{source_id}:figure:p{figure.pdf_page:04d}-{figure.region.index}"
            figure_uids.append(figure_uid)
            out.figures.append(
                FigureRecord(
                    uid=figure_uid,
                    rule_uid=uid,
                    page=_page_ref(figure.pdf_page, [figure.region.bbox], printed_pages),
                    image_file=figure.region.image_file,
                    text=join_lines(line.text for line in figure.lines),
                )
            )
            out.assignments.extend(
                LineAssignment(pdf_page=figure.pdf_page, line_index=line.index, consumer=figure_uid)
                for line in figure.lines
            )
        out.assignments.extend(
            LineAssignment(pdf_page=page, line_index=index, consumer=uid)
            for page, index in draft.line_refs
        )

        boxes = {page: list(b) for page, b in draft.boxes.items()}
        for mark in draft.tables:
            boxes.setdefault(mark.pdf_page, []).append(mark.region.bbox)
        for figure in draft.figures:
            boxes.setdefault(figure.pdf_page, []).append(figure.region.bbox)

        out.rules.append(
            RuleRecord(
                uid=uid,
                kind="rule" if draft.rule_id is not None else "preamble",
                namespace=division.namespace,
                rule_id=draft.rule_id,
                printed_number=draft.printed_number,
                parent_id=parent_rule_id(draft.rule_id) if draft.rule_id else None,
                level=rule_level(draft.rule_id) if draft.rule_id else 0,
                heading=draft.heading,
                heading_path=(),  # filled below, once all headings of the division are known
                official_text="\n".join(_block_text(b) for b in draft.blocks),
                items=tuple(RuleItem(label=b.label, text=b.text) for b in draft.blocks if b.label),
                table_uids=tuple(table_uids),
                figure_uids=tuple(figure_uids),
                pages=tuple(_page_ref(page, boxes[page], printed_pages) for page in sorted(boxes)),
                parse_flags=tuple(flags),
            )
        )

    out.rules = [
        rule.model_copy(update={"heading_path": _heading_path(rule, division, headings)})
        for rule in out.rules
    ]
    out.rules = _with_glossary_entries(source_id, out.rules, drafts, printed_pages)
    return out


def _with_glossary_entries(
    source_id: str,
    rules: Sequence[RuleRecord],
    drafts: Sequence[Draft],
    printed_pages: Mapping[int, str | None],
) -> list[RuleRecord]:
    """Each record, followed by a definition for every entry of a glossary in its text."""
    used = {rule.uid for rule in rules}
    result: list[RuleRecord] = []
    for rule, draft in zip(rules, drafts, strict=True):
        result.append(rule)
        blocks = draft.blocks
        for entry in paragraph_entries([_block_text(b) for b in blocks]):
            boxes: dict[int, list[BBox]] = {}
            for block in blocks[entry.first : entry.last + 1]:
                for page, page_boxes in block.boxes.items():
                    boxes.setdefault(page, []).extend(page_boxes)
            pages = [_page_ref(page, boxes[page], printed_pages) for page in sorted(boxes)]
            result.append(definition_record(source_id, rule, entry.term, entry.text, pages, used))
    return result


def _heading_path(
    rule: RuleRecord, division: Division, headings: Mapping[str, str | None]
) -> tuple[str, ...]:
    path = [division.title]
    ancestors: list[str] = []
    parent = rule.parent_id
    while parent is not None:
        heading = headings.get(parent)
        if heading:
            ancestors.append(f"{parent} {heading}")
        parent = parent_rule_id(parent)
    path.extend(reversed(ancestors))
    if rule.rule_id is not None:
        path.append(f"{rule.rule_id} {rule.heading}" if rule.heading else rule.rule_id)
    elif rule.printed_number:  # an appendix
        path.append(" ".join(p for p in (rule.printed_number, rule.heading) if p))
    return tuple(path)


def _unique_uid(
    source_id: str, namespace: str, rule_id: str | None, used: set[str]
) -> tuple[str, bool]:
    base = f"{source_id}:{namespace}:{rule_id or 'preamble'}"
    uid, n = base, 1
    while uid in used:
        n += 1
        uid = f"{base}#{n}"
    used.add(uid)
    return uid, n > 1 and rule_id is not None


def _block_text(block: Block) -> str:
    if block.label is None:
        return block.text
    marker = block.marker or f"{block.label})"
    return f"{marker} {block.text}"


def _page_ref(pdf_page: int, boxes: Sequence[BBox], printed: Mapping[int, str | None]) -> PageRef:
    union = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    return PageRef(pdf_page=pdf_page, printed_page=printed.get(pdf_page), bbox=union)
