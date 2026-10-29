"""Definition records: one per entry of a glossary, so a defined term can be found and cited.

Glossaries are recognized by their shape, never by page or edition:

* a table with a "Term | Definition" header row (the GTR definitions);
* a table with an "Abbrev." column (the ISSF event tables: "ARM" → "10m Air Rifle (standing)");
* a two-column table whose rows all start with a code ("DNS" → "Did not Start");
* a run of paragraphs that start with "Term: " in alphabetical order (the anti-doping
  appendix "DEFINITIONS"). A paragraph without a term continues the previous entry.

Each entry becomes a record of kind "definition", uid `<source>:<namespace>:term:<term>`,
linked to the record it was taken from (`defined_in`). The definitions consume no lines; the
coverage check verifies that each one repeats its source text exactly.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import pairwise

from issf_rules.models.records import PageRef, RuleRecord, TableRecord

_TERM_HEADER = re.compile(r"terms?", re.IGNORECASE)
_DEFINITION_HEADER = re.compile(r"definitions?|meaning|description", re.IGNORECASE)
_ABBREVIATION_HEADER = re.compile(r"abbrev(iations?|\.)?", re.IGNORECASE)
_CODE = re.compile(r"[A-Z]{2,6}")
MIN_CODE_ROWS = 3
"""A two-column table counts as an abbreviation list only if all of at least this many rows
start with a code; smaller tables are too weak evidence."""
_NON_ALNUM = re.compile(r"[^\w]+")
_TERM_PARAGRAPH = re.compile(r"^(?P<term>[A-Z0-9][^:.;\n]{0,79}?):\s+(?=\S)")
MIN_GLOSSARY_ENTRIES = 5
MIN_ALPHABETICAL = 0.8
"""Share of neighbouring terms that must be in alphabetical order for a run of "Term: "
paragraphs to count as a glossary rather than ordinary text with colons."""


@dataclass(frozen=True)
class Entry:
    term: str
    text: str
    title: str | None
    """What the table is about, e.g. "EVENTS FOR MEN AND MEN JUNIOR"; None if untitled."""


@dataclass(frozen=True)
class ParagraphEntry:
    term: str
    text: str
    first: int
    """Index of the paragraph that starts the entry."""
    last: int
    """Index of its last paragraph (continuations included)."""


def table_entries(rows: Sequence[Sequence[str | None]]) -> list[Entry]:
    """The (term, text) pairs of a glossary-style table, or [] for any other table."""
    header = next((i for i, row in enumerate(rows) if _is_definition_header(row)), None)
    if header is not None:
        title = rows[header][1]
        return [
            Entry(term, text, title)
            for term, text in (_pair(row, 0, 1) for row in rows[header + 1 :])
            if term and text and not _is_definition_header((term, text))
        ]
    header = next(
        (i for i, row in enumerate(rows) if any(_matches(_ABBREVIATION_HEADER, c) for c in row)),
        None,
    )
    if header is not None:
        column = next(i for i, c in enumerate(rows[header]) if _matches(_ABBREVIATION_HEADER, c))
        title = rows[0][0] if header > 0 and not any(rows[0][1:]) else None
        return [
            Entry(term, text, title)
            for term, text in (_pair(row, column, 0) for row in rows[header + 1 :])
            if term and text
        ]
    pairs = [_pair(row, 0, 1) for row in rows if len(row) == 2]
    codes = [
        Entry(term, text, None) for term, text in pairs if term and text and _CODE.fullmatch(term)
    ]
    return codes if len(codes) == len(rows) >= MIN_CODE_ROWS else []


def paragraph_entries(paragraphs: Sequence[str]) -> list[ParagraphEntry]:
    """The entries of a glossary written as "Term: text" paragraphs, or [] if there is none."""
    starts = [
        (i, m.group("term"), p[m.end() :])
        for i, p in enumerate(paragraphs)
        if (m := _TERM_PARAGRAPH.match(p))
    ]
    if len(starts) < MIN_GLOSSARY_ENTRIES:
        return []
    terms = [_sort_key(term) for _, term, _ in starts]
    ordered = sum(a < b for a, b in pairwise(terms))  # a repeated term is no glossary
    if ordered < MIN_ALPHABETICAL * (len(terms) - 1):
        return []
    # A "Term: " paragraph out of alphabetical order between two neighbours that are in order
    # ("Nota bene: ..." between "Event" and "Event Period") is a note inside the previous
    # entry, not an entry of its own.
    starts = [
        start
        for n, start in enumerate(starts)
        if not 0 < n < len(starts) - 1
        or not terms[n - 1] < terms[n + 1]
        or terms[n - 1] < terms[n] < terms[n + 1]
    ]
    entries = []
    for n, (i, term, rest) in enumerate(starts):
        last = starts[n + 1][0] - 1 if n + 1 < len(starts) else len(paragraphs) - 1
        text = "\n".join([rest, *paragraphs[i + 1 : last + 1]])
        entries.append(ParagraphEntry(term=term, text=text, first=i, last=last))
    return entries


def definition_record(
    source_id: str,
    owner: RuleRecord,
    term: str,
    text: str,
    pages: Sequence[PageRef],
    used: set[str],
    title: str | None = None,
    table_uid: str | None = None,
) -> RuleRecord:
    base = f"{source_id}:{owner.namespace}:term:{term}"
    uid, n = base, 1
    while uid in used:
        n += 1
        uid = f"{base}#{n}"
    used.add(uid)
    return RuleRecord(
        uid=uid,
        kind="definition",
        namespace=owner.namespace,
        rule_id=None,
        printed_number=None,
        parent_id=owner.rule_id,
        level=0,
        heading=term,
        heading_path=(*owner.heading_path, *((title,) if title else ()), term),
        official_text=text,
        table_uids=(table_uid,) if table_uid else (),
        pages=tuple(pages),
        parse_flags=("duplicate-id",) if n > 1 else (),
        defined_in=owner.uid,
    )


def table_definitions(
    source_id: str, rules: Sequence[RuleRecord], tables: Sequence[TableRecord]
) -> Iterator[RuleRecord]:
    """Definition records for every glossary-style table, in table order."""
    owners = {rule.uid: rule for rule in rules}
    used = {rule.uid for rule in rules}
    for table in tables:
        owner = owners[table.rule_uid]
        for entry in table_entries(table.rows):
            yield definition_record(
                source_id,
                owner,
                entry.term,
                entry.text,
                [table.page],
                used,
                title=entry.title,
                table_uid=table.uid,
            )


def _sort_key(term: str) -> str:
    """Dictionary order, as glossaries are sorted: case and punctuation are ignored, so
    "International-Level Athlete" sorts before "International Standard"."""
    return " ".join(_NON_ALNUM.sub(" ", term.casefold()).split())


def _is_definition_header(row: Sequence[str | None]) -> bool:
    return len(row) >= 2 and _matches(_TERM_HEADER, row[0]) and _matches(_DEFINITION_HEADER, row[1])


def _matches(pattern: re.Pattern[str], cell: str | None) -> bool:
    return cell is not None and pattern.fullmatch(cell.strip()) is not None


def _pair(row: Sequence[str | None], term: int, text: int) -> tuple[str | None, str | None]:
    return (row[term] if term < len(row) else None, row[text] if text < len(row) else None)
