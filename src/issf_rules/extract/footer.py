"""Separating the running footer from body text.

Every page of the rulebook carries a footer such as
"EDITION 2025 (Third Print 10/2026)    Effective 19 October 2026    © ISSF    189". The page
number sits at the start on even pages and at the end on odd pages.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from issf_rules.models.layout import Line, PageFooter

FOOTER_ZONE = 0.9
"""Only lines starting in the bottom 10 % of the page can be the footer."""

_FOOTER_MARK = re.compile(r"\bEDITION\s+\d{4}\b", re.IGNORECASE)
_LEADING_NUMBER = re.compile(r"^\s*(\d{1,4})\s")
_TRAILING_NUMBER = re.compile(r"\s(\d{1,4})\s*$")


def split_footer(lines: Sequence[Line], page_height: float) -> tuple[PageFooter | None, list[Line]]:
    """Return the footer (if any) and the remaining body lines, in their original order."""
    footer_lines = [
        line
        for line in lines
        if line.y0 >= page_height * FOOTER_ZONE and _FOOTER_MARK.search(line.text)
    ]
    if not footer_lines:
        return None, list(lines)
    footer_ids = {line.index for line in footer_lines}
    body = [line for line in lines if line.index not in footer_ids]
    text = " ".join(line.text for line in footer_lines)
    return PageFooter(text=" ".join(text.split()), printed_page=_printed_page(text)), body


def _printed_page(text: str) -> str | None:
    match = _LEADING_NUMBER.search(text) or _TRAILING_NUMBER.search(text)
    return match.group(1) if match else None
