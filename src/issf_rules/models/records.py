"""Output of the parse stage: the canonical, verbatim rule records (ADR 0003).

These records are the source of truth for everything downstream. `official_text` and item texts
are verbatim from the PDF; only whitespace, control characters and line-break joins are
normalized.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from issf_rules.models.layout import BBox
from issf_rules.models.source import SourceDocument


class Division(BaseModel):
    """A top-level part of the book (e.g. Part 6) or an annex, covering a page range.

    Rule numbers are only unique within one division, so the division's namespace is part of
    every rule uid.
    """

    model_config = ConfigDict(frozen=True)

    namespace: str
    """e.g. "front", "part-6", "part-3/annex-J", "part-3/annex-AC/p110"."""
    kind: Literal["front", "part", "annex", "section"]
    number: str | None
    """Part number ("6") or annex letter ("J"); None for front matter and sections."""
    title: str
    first_page: int
    last_page: int
    reference_number: str | None = None
    """The number other rules use to cite this division, e.g. "3.13.3.6" for Annex R."""


class PageRef(BaseModel):
    """Where a record's content sits in the PDF."""

    model_config = ConfigDict(frozen=True)

    pdf_page: int
    printed_page: str | None
    bbox: BBox


class CrossRef(BaseModel):
    """A reference from one rule to another, as written in the text."""

    model_config = ConfigDict(frozen=True)

    raw: str
    """The reference exactly as matched in the text (e.g. "Rule 6.4.11.10.c")."""
    target_rule_id: str
    target_item: str | None
    target_uid: str | None
    """uid of the resolved rule; None if the target was not found or is external."""
    document: str | None = None
    """The document the reference names when it is not this book's own numbering, e.g.
    "ISSF Constitution" (printed in the book as Part 1) or "WADA Code" (external)."""
    external: bool = False
    """The target is in a document that is not part of this book, so it cannot resolve."""


class RuleItem(BaseModel):
    """A lettered sub-clause, e.g. "a) ...". The book uses letters below the fourth level."""

    model_config = ConfigDict(frozen=True)

    label: str
    text: str


class RuleRecord(BaseModel):
    """One numbered rule, the unnumbered preamble text at the start of a division, or one
    term of a glossary-style table (kind "definition", see `parse.definitions`)."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    uid: str
    kind: Literal["rule", "preamble", "definition"]
    namespace: str
    rule_id: str | None
    """The rule number, e.g. "6.11.3.1" or "2" for "ARTICLE 2"; None for preambles and
    definitions."""
    printed_number: str | None
    """The number exactly as printed, e.g. "6.11.3.1" or "ARTICLE 2"."""
    parent_id: str | None
    """For a definition: the rule whose table holds it (None for a preamble's table)."""
    level: int
    """Number of numeric levels in rule_id (1-4); 0 for preambles."""
    heading: str | None
    """For a definition: the term, e.g. "FOP"."""
    heading_path: tuple[str, ...]
    """Headings of the division and all ancestors, outermost first, ending with this rule's own."""
    official_text: str
    """Full verbatim text in reading order. Paragraphs are separated by newlines, and items
    appear as "a) ..." lines."""
    items: tuple[RuleItem, ...] = ()
    cross_refs: tuple[CrossRef, ...] = ()
    table_uids: tuple[str, ...] = ()
    figure_uids: tuple[str, ...] = ()
    pages: tuple[PageRef, ...]
    parse_flags: tuple[str, ...] = ()
    defined_in: str | None = None
    """For a definition: uid of the record whose text or table it was taken from."""


class TableRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    uid: str
    rule_uid: str
    page: PageRef
    rows: tuple[tuple[str | None, ...], ...]


class FigureRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    uid: str
    rule_uid: str
    page: PageRef
    image_file: str | None
    text: str
    """Text printed inside the figure area (labels, dimensions). Verbatim; may be empty."""


class LineAssignment(BaseModel):
    """Which record consumed a body line. Used by the coverage check."""

    model_config = ConfigDict(frozen=True)

    pdf_page: int
    line_index: int
    consumer: str
    """A record uid, or a marker such as "contents" or "division-title"."""


class ParsedDocument(BaseModel):
    """Everything the parse stage produces for one source document."""

    model_config = ConfigDict(frozen=True)

    source: SourceDocument
    divisions: tuple[Division, ...]
    rules: tuple[RuleRecord, ...]
    tables: tuple[TableRecord, ...]
    figures: tuple[FigureRecord, ...]
    assignments: tuple[LineAssignment, ...]
