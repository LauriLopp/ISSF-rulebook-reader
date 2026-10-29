"""Parse stage: page layouts → verbatim rule records with structure and provenance."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from issf_rules.models.layout import Line, PageLayout
from issf_rules.models.records import Division, LineAssignment, ParsedDocument, RuleRecord
from issf_rules.models.source import SourceDocument
from issf_rules.parse.assemble import Assembled, assemble_division
from issf_rules.parse.builder import DivisionBuilder, RuleColumns
from issf_rules.parse.contents import contents_blocks, find_divisions, is_title_line
from issf_rules.parse.crossrefs import documents_in_book, find_references, resolve
from issf_rules.parse.definitions import table_definitions
from issf_rules.parse.patterns import match_rule_start
from issf_rules.parse.rows import PageItem, Row, page_items
from issf_rules.parse.sections import split_sections

CONTENTS = "contents"
DIVISION_TITLE = "division-title"


class ParseError(ValueError):
    """The document does not have the structure the parser relies on."""


def parse_document(source: SourceDocument, pages: Sequence[PageLayout]) -> ParsedDocument:
    assignments: list[LineAssignment] = []
    items_by_page: dict[int, list[PageItem]] = {}
    titles_by_page: dict[int, list[Line]] = {}
    for page in pages:
        flow_lines = []
        contents = contents_blocks(page)
        for line in page.lines:
            if line.block in contents:
                consumer = CONTENTS
            elif is_title_line(line):
                consumer = DIVISION_TITLE
                titles_by_page.setdefault(page.pdf_page, []).append(line)
            else:
                flow_lines.append(line)
                continue
            assignments.append(
                LineAssignment(pdf_page=page.pdf_page, line_index=line.index, consumer=consumer)
            )
        items_by_page[page.pdf_page] = page_items(page, flow_lines)

    columns = detect_rule_columns(items_by_page)
    divisions = tuple(
        section
        for division in find_divisions(pages)
        for section in split_sections(division, items_by_page, titles_by_page, columns)
    )
    printed = {page.pdf_page: page.footer.printed_page if page.footer else None for page in pages}

    combined = Assembled()
    for division in divisions:
        builder = DivisionBuilder(columns)
        for number in range(division.first_page, division.last_page + 1):
            builder.feed(items_by_page.get(number, []))
        part = assemble_division(source.id, division, builder.finish(), printed)
        combined.rules.extend(part.rules)
        combined.tables.extend(part.tables)
        combined.figures.extend(part.figures)
        combined.assignments.extend(part.assignments)

    assignments.extend(combined.assignments)
    assignments.sort(key=lambda a: (a.pdf_page, a.line_index))
    rules = _with_definitions(source.id, combined)
    return ParsedDocument(
        source=source,
        divisions=divisions,
        rules=tuple(_with_cross_references(rules, divisions)),
        tables=tuple(combined.tables),
        figures=tuple(combined.figures),
        assignments=tuple(assignments),
    )


def detect_rule_columns(items_by_page: dict[int, list[PageItem]]) -> RuleColumns:
    """Find where rule numbers sit on odd and even pages.

    Uses only multi-level numbers ("6.11.3"), which are unambiguous, and takes the most common
    x-position per page parity. The book mirrors its margins, so the two differ.
    """
    positions: dict[int, Counter[float]] = {0: Counter(), 1: Counter()}
    for number, items in items_by_page.items():
        for item in items:
            if isinstance(item, Row):
                start = match_rule_start(item.text)
                if start is not None and "." in start.rule_id:
                    positions[number % 2][round(item.x0)] += 1
    if not positions[0] or not positions[1]:
        raise ParseError("could not find rule numbers on both odd and even pages")
    return RuleColumns(
        odd=float(positions[1].most_common(1)[0][0]),
        even=float(positions[0].most_common(1)[0][0]),
    )


def _with_definitions(source_id: str, combined: Assembled) -> list[RuleRecord]:
    """All records, with each definition placed right after the rule that holds its table."""
    owner_of = {table.uid: table.rule_uid for table in combined.tables}
    by_owner: dict[str, list[RuleRecord]] = {}
    for record in table_definitions(source_id, combined.rules, combined.tables):
        by_owner.setdefault(owner_of[record.table_uids[0]], []).append(record)
    return [record for rule in combined.rules for record in (rule, *by_owner.get(rule.uid, ()))]


def _with_cross_references(
    rules: list[RuleRecord], divisions: Sequence[Division]
) -> list[RuleRecord]:
    index: dict[tuple[str, str], str] = {}
    for rule in rules:
        if rule.rule_id is not None:
            index.setdefault((rule.namespace, rule.rule_id), rule.uid)
    # Annexes are cited by their article number ("3.13.3.6, Annex R"): point at their first record.
    first_record: dict[str, str] = {}
    for rule in rules:
        first_record.setdefault(rule.namespace, rule.uid)
    for division in divisions:
        if division.reference_number and division.namespace in first_record:
            part = f"part-{division.reference_number.split('.')[0]}"
            index.setdefault((part, division.reference_number), first_record[division.namespace])

    documents = documents_in_book(divisions)
    updated = []
    for rule in rules:
        refs = resolve(find_references(rule.official_text), rule.namespace, index, documents)
        # An annex introduction naming its own number ("Article 3.13.3.10, Annex S") is a
        # title, not a reference.
        refs = tuple(ref for ref in refs if ref.target_uid != rule.uid)
        updated.append(rule.model_copy(update={"cross_refs": refs}))
    return updated
