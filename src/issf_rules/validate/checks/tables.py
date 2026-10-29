"""Table extraction quality: mostly-empty tables, text the table finder dropped, and damaged
words.

Damaged words are found by comparing with the body text, which is read differently and is
reliable: a table word that is unknown in the body but becomes a known word by swapping two
neighbouring letters ("Rifel"), possibly after joining it with the next word ("Offci er"), or
that splits into two known words ("Maximumweight"), is reported. On a correct extraction the
only hits are real words that the body text never uses ("Eyewear", "Tiebreak"), so findings are
notes; a regression shows up as a jump to dozens of tables.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator, Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument
from issf_rules.models.report import Finding
from issf_rules.validate.checks.coverage import count_visible

CHECK = "table-quality"
CHECK_TEXT = "table-text"
MAX_EMPTY_SHARE = 0.5
MIN_TEXT_KEPT = 0.9
MIN_WORD = 4
"""Shorter words are too often codes or abbreviations to judge."""
MIN_PART = 3
_WORD = re.compile(r"[A-Za-z]+")


def check_tables(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    line_text = {(page.pdf_page, line.index): line.text for page in pages for line in page.lines}
    in_table: dict[str, int] = defaultdict(int)
    for a in parsed.assignments:
        in_table[a.consumer] += count_visible(line_text.get((a.pdf_page, a.line_index), ""))

    findings: list[Finding] = []
    for table in parsed.tables:
        cells = [cell for row in table.rows for cell in row]
        empty = sum(1 for cell in cells if not cell)
        if cells and empty / len(cells) > MAX_EMPTY_SHARE:
            findings.append(
                Finding(
                    check=CHECK,
                    severity="warning",
                    uid=table.uid,
                    pdf_page=table.page.pdf_page,
                    message=f"{empty} of {len(cells)} cells empty: possible layout table or "
                    "merged cells",
                )
            )
        source_chars = in_table.get(table.uid, 0)
        kept = sum(count_visible(cell or "") for cell in cells)
        if source_chars and kept < MIN_TEXT_KEPT * source_chars:
            findings.append(
                Finding(
                    check=CHECK,
                    severity="warning",
                    uid=table.uid,
                    pdf_page=table.page.pdf_page,
                    message=f"cells hold {kept} of {source_chars} characters in the table area",
                )
            )
    return findings


def check_table_text(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    vocabulary = {
        word.lower()
        for rule in parsed.rules
        if rule.kind != "definition"
        for text in (rule.official_text, rule.heading or "")
        for word in _WORD.findall(text)
    }
    findings = []
    for table in parsed.tables:
        damaged = sorted(
            {
                word
                for row in table.rows
                for cell in row
                if cell
                for word in damaged_words(cell, vocabulary)
            }
        )
        if damaged:
            findings.append(
                Finding(
                    check=CHECK_TEXT,
                    severity="info",
                    uid=table.uid,
                    pdf_page=table.page.pdf_page,
                    message=f"possibly damaged words: {', '.join(damaged)}",
                )
            )
    return findings


def damaged_words(text: str, vocabulary: set[str]) -> Iterator[str]:
    matches = list(_WORD.finditer(text))
    for i, match in enumerate(matches):
        word = match.group().lower()
        if len(word) < MIN_WORD or word in vocabulary:
            continue
        following = matches[i + 1] if i + 1 < len(matches) else None
        if following is not None and text[match.end() : following.start()] == " ":
            joined = word + following.group().lower()
            if joined in vocabulary or _swapped_known(joined, vocabulary):
                yield f"{match.group()} {following.group()}"
                continue
        if _swapped_known(word, vocabulary) or _split_known(word, vocabulary):
            yield match.group()


def _swapped_known(word: str, vocabulary: set[str]) -> bool:
    return any(
        word[:i] + word[i + 1] + word[i] + word[i + 2 :] in vocabulary for i in range(len(word) - 1)
    )


def _split_known(word: str, vocabulary: set[str]) -> bool:
    return any(
        word[:i] in vocabulary and word[i:] in vocabulary
        for i in range(MIN_PART, len(word) - MIN_PART + 1)
    )
