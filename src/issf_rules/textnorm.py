"""The only text normalizations allowed on official text.

Rule text must stay verbatim, so this module is deliberately small. It removes control characters
that carry no content (InDesign leaves BEL characters in the text layer), collapses whitespace,
and joins wrapped lines. No words are ever changed, added, or dropped.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# C0 control characters except tab (\t marks the gap after a rule number), plus DEL.
_CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")
_SPACES = re.compile(r"[ \t\u00a0]+")  # \u00a0: no-break space
SOFT_HYPHEN = "\u00ad"


def strip_controls(text: str) -> str:
    return _CONTROL.sub("", text)


def collapse_spaces(text: str) -> str:
    """Collapse runs of spaces/tabs/NBSP to one space and trim the ends."""
    return _SPACES.sub(" ", text).strip()


def join_lines(lines: Iterable[str]) -> str:
    """Join wrapped lines of one paragraph into a single string.

    A line ending in a hyphen is joined without a space and the hyphen is kept ("anti-" +
    "doping" → "anti-doping"): the hyphen may be part of the word, and dropping it would alter
    the text. A line ending in a soft hyphen (U+00AD, a break point the typesetter used) is
    joined the same way; the invisible soft hyphen is kept, so no character is lost. So is a line
    ending in a slash ("Men/" + "Women" → "Men/Women").
    """
    result = ""
    for raw in lines:
        line = collapse_spaces(raw)
        if not line:
            continue
        if not result:
            result = line
        elif result.endswith((SOFT_HYPHEN, "/")) or (
            result.endswith("-") and not result.endswith(" -")
        ):
            result += line
        else:
            result += " " + line
    return result
