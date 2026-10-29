"""Contents pages and the book's divisions (parts and annexes).

The main contents page (page 3) lists every part and annex with its first page. Rule numbers
restart inside annexes, so these divisions become the namespaces of rule uids. Each part also
has its own contents page; those entries repeat rule numbers and headings, and must not be
mistaken for rules.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from issf_rules.models.layout import Line, PageLayout
from issf_rules.models.records import Division

TITLE_FONT_SIZE = 20.0
"""Text this large is a page title ("CONTENTS", "6 GENERAL TECHNICAL RULES")."""
MIN_CONTENTS_ENTRIES = 3

_ENTRY = re.compile(r"\S\s{2,}(?P<page>\d{1,3})\s*$")
_MAIN_ENTRY = re.compile(r"^(?:(?P<number>\d{1,2})\.)?\s*(?P<title>.+?)\s{2,}(?P<page>\d{1,3})\s*$")
_ANNEX = re.compile(
    r"^Article\s+(?P<article>[\d.]+?)\s+Annex\s+[“\"](?P<letter>[A-Z]{1,3})[”\"]\s*:\s*(?P<title>.+)$"
)


class ContentsError(ValueError):
    """The main contents page could not be found or understood."""


@dataclass(frozen=True)
class _Entry:
    number: str | None
    title: str
    page: int


def block_texts(lines: Sequence[Line]) -> dict[int, str]:
    """Text of each MuPDF block, lines joined with a space (multiple spaces preserved)."""
    blocks: dict[int, list[str]] = {}
    for line in lines:
        blocks.setdefault(line.block, []).append(line.text)
    return {block: " ".join(texts) for block, texts in blocks.items()}


def contents_blocks(page: PageLayout) -> set[int]:
    """Blocks that are contents entries ("1.1  PURPOSE    9"); empty if not a contents page."""
    entries = {
        block
        for block, text in block_texts(page.lines).items()
        if _ENTRY.search(text.replace("\t", "  "))
    }
    return entries if len(entries) >= MIN_CONTENTS_ENTRIES else set()


def is_title_line(line: Line) -> bool:
    return line.size >= TITLE_FONT_SIZE


def find_divisions(pages: Sequence[PageLayout], search_pages: int = 10) -> tuple[Division, ...]:
    """Read the main contents page and return divisions covering every page of the book."""
    contents_page = next(
        (
            page
            for page in pages[:search_pages]
            if any(
                is_title_line(line) and line.text.strip().upper() == "CONTENTS"
                for line in page.lines
            )
        ),
        None,
    )
    if contents_page is None:
        raise ContentsError(f"no CONTENTS page within the first {search_pages} pages")
    entries = _main_entries(contents_page)
    return _divisions(entries, last_page=pages[-1].pdf_page)


def _main_entries(page: PageLayout) -> list[_Entry]:
    entries: list[_Entry] = []
    for block in sorted(contents_blocks(page)):
        text = block_texts(page.lines)[block].replace("\t", "  ").strip()
        match = _MAIN_ENTRY.match(text)
        if match is None:
            continue
        title = " ".join(match.group("title").split())
        entries.append(_Entry(match.group("number"), title, int(match.group("page"))))
    if not any(entry.number for entry in entries):
        raise ContentsError(f"no numbered parts found on contents page {page.pdf_page}")
    return sorted(entries, key=lambda entry: entry.page)


def _divisions(entries: Sequence[_Entry], last_page: int) -> tuple[Division, ...]:
    """Each division runs from its first page to the page before the next one starts."""
    starts: list[Division] = []
    current_part: str | None = None
    for entry in entries:
        annex = _ANNEX.match(entry.title)
        if entry.number is not None:
            current_part = entry.number
            starts.append(
                _division(f"part-{entry.number}", "part", entry.number, entry.title, entry.page)
            )
        elif annex is not None and current_part is not None:
            letter = annex.group("letter")
            starts.append(
                _division(
                    f"part-{current_part}/annex-{letter}",
                    "annex",
                    letter,
                    annex.group("title").strip(),
                    entry.page,
                    annex.group("article"),
                )
            )
        # Other unnumbered entries (e.g. the fees summary) belong to the front matter.

    divisions: list[Division] = []
    if not starts or starts[0].first_page > 1:
        first = starts[0].first_page if starts else last_page + 1
        divisions.append(_division("front", "front", None, "Front matter", 1, last_page=first - 1))
    for i, division in enumerate(starts):
        end = starts[i + 1].first_page - 1 if i + 1 < len(starts) else last_page
        divisions.append(division.model_copy(update={"last_page": end}))
    return tuple(divisions)


def _division(
    namespace: str,
    kind: Literal["front", "part", "annex"],
    number: str | None,
    title: str,
    first_page: int,
    reference_number: str | None = None,
    last_page: int = 0,
) -> Division:
    return Division(
        namespace=namespace,
        kind=kind,
        number=number,
        title=title,
        first_page=first_page,
        last_page=last_page,
        reference_number=reference_number,
    )
