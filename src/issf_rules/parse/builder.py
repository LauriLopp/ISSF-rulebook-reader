"""The state machine that turns a division's reading-order items into draft rule records.

Walking the rows top to bottom:

* a rule number in the rule-number column starts a new rule; so does an unnumbered bold
  heading there such as "APPENDIX 1  DEFINITIONS", which becomes a record without a number;
* a lettered label ("a)") starts a new item of the current rule; a group heading "(A) ..."
  makes the following items "A.a", "A.b", ... because the letters restart in each group;
* any other row continues the current paragraph or item, or starts a new paragraph after a
  vertical gap;
* tables and figures attach to whichever rule is open where they appear.

Text before the first rule of a division goes into a "preamble" draft. When a division is
finished, items that start mid-line ("...; and d) If ...") are split out of their paragraph.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from issf_rules.models.layout import BBox, Span
from issf_rules.parse.patterns import (
    RuleStart,
    ends_sentence,
    find_inline_items,
    match_appendix_start,
    match_group_start,
    match_item_start,
    match_rule_start,
    next_label,
)
from issf_rules.parse.rows import FigureMark, PageItem, Row, TableMark
from issf_rules.textnorm import collapse_spaces, join_lines

RULE_COLUMN_TOLERANCE = 4.0
"""How far (points) a row may start from the rule-number column and still be a rule start."""
PARAGRAPH_GAP = 1.35
"""A vertical step larger than this many font sizes starts a new paragraph."""
MAX_PLAIN_HEADING_WORDS = 6
"""A non-bold text after a rule number is only treated as a heading if it is this short."""


@dataclass
class Block:
    """A paragraph (label None) or a lettered item, as lines still to be joined."""

    label: str | None
    parts: list[str] = field(default_factory=list)
    marker: str | None = None
    """The label as printed ("b)", "b).", "a."); None means "<label>)"."""
    boxes: dict[int, list[BBox]] = field(default_factory=dict)
    """Where the block's lines are, per page (used to place definitions taken from it)."""

    @property
    def text(self) -> str:
        return join_lines(self.parts)


@dataclass
class Draft:
    """A rule (or preamble) being assembled. Turned into a RuleRecord by the assembler."""

    rule_id: str | None
    printed_number: str | None = None
    key: str | None = None
    """uid part for an unnumbered record other than the preamble, e.g. "appendix-1"."""
    heading_parts: list[str] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    boxes: dict[int, list[BBox]] = field(default_factory=dict)
    line_refs: list[tuple[int, int]] = field(default_factory=list)
    tables: list[TableMark] = field(default_factory=list)
    figures: list[FigureMark] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    heading_open: bool = False
    """Bold rows directly below a bold heading extend it ("Interruptions in ... / Events")."""
    plain_heading_candidate: bool = False
    """The text after the number is short and not bold; decided when the next row arrives."""
    group: str | None = None
    """The current "(A)"-style group, which prefixes item labels."""

    @property
    def heading(self) -> str | None:
        heading = join_lines(self.heading_parts)
        return heading or None

    def last_letter(self) -> str | None:
        """The letter of the last item in the current group, or None if there is none yet."""
        prefix = f"{self.group}." if self.group else ""
        for block in reversed(self.blocks):
            if block.label is not None:
                in_group = block.label.startswith(prefix) and "." not in block.label[len(prefix) :]
                return block.label[len(prefix) :] if in_group else None
        return None

    def add_row(self, row: Row) -> None:
        for line in row.lines:
            self.boxes.setdefault(row.pdf_page, []).append(line.bbox)
            self.line_refs.append((row.pdf_page, line.index))
            if self.blocks:
                self.blocks[-1].boxes.setdefault(row.pdf_page, []).append(line.bbox)


@dataclass(frozen=True)
class RuleColumns:
    """x-position of the rule-number column on odd and even pages (mirrored margins)."""

    odd: float
    even: float

    def at(self, pdf_page: int) -> float:
        return self.odd if pdf_page % 2 else self.even


def rule_start_at(row: Row, columns: RuleColumns) -> RuleStart | None:
    """The rule number starting `row`, if the row starts in the rule-number column."""
    if abs(row.x0 - columns.at(row.pdf_page)) > RULE_COLUMN_TOLERANCE:
        return None
    return match_rule_start(row.text)


class DivisionBuilder:
    def __init__(self, columns: RuleColumns) -> None:
        self.columns = columns
        self.drafts: list[Draft] = [Draft(rule_id=None)]
        self._previous_row: Row | None = None
        self._after_region = False

    @property
    def current(self) -> Draft:
        return self.drafts[-1]

    def feed(self, items: Sequence[PageItem]) -> None:
        for item in items:
            if isinstance(item, Row):
                self._row(item)
            elif isinstance(item, TableMark):
                self._settle_plain_heading(confirmed=False)
                self.current.tables.append(item)
                self._after_region = True
            else:
                self._settle_plain_heading(confirmed=False)
                self.current.figures.append(item)
                self._after_region = True

    def finish(self) -> list[Draft]:
        self._settle_plain_heading(confirmed=False)
        drafts = [
            d for d in self.drafts if d.rule_id is not None or d.line_refs or d.tables or d.figures
        ]
        for draft in drafts:
            draft.blocks = split_inline_items(draft.blocks)
        return drafts

    # -- rows ---------------------------------------------------------------------------------

    def _row(self, row: Row) -> None:
        text = row.text
        rule = rule_start_at(row, self.columns)
        new_paragraph = self._starts_paragraph(row)
        appendix = None
        if rule is None and abs(row.x0 - self.columns.at(row.pdf_page)) <= RULE_COLUMN_TOLERANCE:
            appendix = match_appendix_start(text)
        if rule is not None:
            self._settle_plain_heading(confirmed=False)
            self._start_rule(row, rule)
        elif appendix is not None and _all_bold(row.spans):
            self._settle_plain_heading(confirmed=False)
            draft = Draft(rule_id=None, printed_number=appendix.printed, key=appendix.key)
            draft.add_row(row)
            heading = collapse_spaces(text[appendix.rest_offset :])
            if heading:
                draft.heading_parts.append(heading)
                draft.heading_open = True
            self.drafts.append(draft)
        else:
            item = match_item_start(text)
            if (
                item is not None
                and item.dotted
                and item.label != next_label(self.current.last_letter())
            ):
                item = None  # "a." is only an item where the letters run in sequence
            if item is not None and (item.tabbed or new_paragraph):
                draft = self.current
                self._settle_plain_heading(confirmed=True)
                draft.heading_open = False
                label = f"{draft.group}.{item.label}" if draft.group else item.label
                draft.blocks.append(
                    Block(label=label, parts=[text[item.rest_offset :]], marker=item.marker)
                )
                draft.add_row(row)
            else:
                self._continue(row, text, new_paragraph)
        self._previous_row = row
        self._after_region = False

    def _start_rule(self, row: Row, rule: RuleStart) -> None:
        draft = Draft(rule_id=rule.rule_id, printed_number=rule.printed)
        if rule.malformed:
            draft.flags.append("malformed-number")
        draft.add_row(row)
        rest_clean = collapse_spaces(row.text[rule.rest_offset :])
        if rest_clean:
            if _all_bold(row.spans_from(rule.rest_offset)):
                draft.heading_parts.append(rest_clean)
                draft.heading_open = True
            else:
                draft.blocks.append(Block(label=None, parts=[rest_clean]))
                draft.plain_heading_candidate = len(
                    rest_clean.split()
                ) <= MAX_PLAIN_HEADING_WORDS and not ends_sentence(rest_clean)
        self.drafts.append(draft)

    def _continue(self, row: Row, text: str, new_paragraph: bool) -> None:
        draft = self.current
        self._settle_plain_heading(confirmed=new_paragraph)
        if draft.heading_open:
            if not new_paragraph and _all_bold(row.spans):
                draft.heading_parts.append(text)
                draft.add_row(row)
                return
            draft.heading_open = False
            if not new_paragraph:
                # Bold text that runs on into normal text was a sentence, not a heading.
                draft.blocks.insert(0, Block(label=None, parts=list(draft.heading_parts)))
                draft.heading_parts.clear()
        if new_paragraph or not draft.blocks:
            group = match_group_start(text) if new_paragraph else None
            if group is not None:
                draft.group = group
            draft.blocks.append(Block(label=None, parts=[text]))
        else:
            draft.blocks[-1].parts.append(text)
        draft.add_row(row)

    def _settle_plain_heading(self, confirmed: bool) -> None:
        """Decide whether short, non-bold text after a rule number was its heading.

        It is a heading only if the same rule continues with a new paragraph below it (as in
        "6.16.6  Appeals"). If the rule ends right there ("1.4.1  Rifle shooting (1)"), the
        short text is the rule's content.
        """
        draft = self.current
        if not draft.plain_heading_candidate:
            return
        draft.plain_heading_candidate = False
        if confirmed and len(draft.blocks) == 1 and draft.blocks[0].label is None:
            draft.heading_parts.extend(draft.blocks.pop().parts)
            draft.flags.append("heading-not-bold")

    # -- geometry -----------------------------------------------------------------------------

    def _starts_paragraph(self, row: Row) -> bool:
        previous = self._previous_row
        if previous is None or self._after_region:
            return True
        if previous.pdf_page != row.pdf_page:
            last = self.current.blocks[-1].parts[-1] if self.current.blocks else ""
            return ends_sentence(last)
        return row.y0 - previous.y0 > PARAGRAPH_GAP * max(previous.size, 1.0)


def _all_bold(spans: Sequence[Span]) -> bool:
    visible = [span for span in spans if span.text.strip()]
    return bool(visible) and all(span.bold for span in visible)


def split_inline_items(blocks: Sequence[Block]) -> list[Block]:
    """Split out items that start mid-line, after a semicolon or colon.

    A candidate is accepted only if its letter continues the sequence of items before it, and
    either "and"/"or" introduces it (the usual way a list's last item is printed) or the next
    item in the rule has the following letter. This keeps references like "see a) above" in
    the text.
    """
    labels_after = [_next_labelled(blocks, i) for i in range(len(blocks))]
    result: list[Block] = []
    last: str | None = None
    for i, block in enumerate(blocks):
        if block.label is not None:
            last = None if "." in block.label else block.label
        text = block.text
        candidates = find_inline_items(text)
        cuts = []
        for n, candidate in enumerate(candidates):
            if candidate.label != next_label(last):
                continue
            following = candidates[n + 1].label if n + 1 < len(candidates) else labels_after[i]
            if candidate.cued or following == next_label(candidate.label):
                cuts.append(candidate)
                last = candidate.label
        if not cuts:
            result.append(block)
            continue
        result.append(
            Block(block.label, [text[: cuts[0].start].rstrip()], block.marker, block.boxes)
        )
        for n, cut in enumerate(cuts):
            end = cuts[n + 1].start if n + 1 < len(cuts) else len(text)
            piece = text[cut.rest_offset : end].rstrip()
            result.append(Block(cut.label, [piece], f"{cut.label})", block.boxes))
    return result


def _next_labelled(blocks: Sequence[Block], index: int) -> str | None:
    return next((b.label for b in blocks[index + 1 :] if b.label is not None), None)
