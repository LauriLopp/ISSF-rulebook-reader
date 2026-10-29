"""Recognizing rule numbers and lettered items at the start of a row.

The book's own numbering protocol (GTR p. 182): at most four numeric levels ("6.10.3.5"), then
letters "a)", "b)", ... The anti-doping part uses "ARTICLE 2" for its top level, and annexes start
at "1". Text patterns alone are not trusted: callers also check where the row sits on the page.

Lettered items are also printed as "b).", "c)It" (no space), "d)_There" and, in the Target
Sprint rules, "a.". The marker is kept as printed so the official text stays verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RULE_START = re.compile(
    r"^(?P<article>ARTICLE\s+)?(?P<id>\d{1,2}(?:\.{1,2}\d{1,3}){0,3})\.?(?P<sep>[ \t]+|$)"
)
_ITEM_START = re.compile(
    r"^(?P<label>[a-z]{1,2})"
    r"(?:(?P<paren>\)\.?)(?P<sep>[ \t_]+|(?=[A-Z]))|(?P<dot>\.)(?P<dot_sep>[ \t]+))"
)
_INLINE_ITEM = re.compile(r"(?<=[;:])\s+(?P<cue>(?:and|or)\s+)?(?P<label>[a-z])\)\s+")
"""An item starting mid-line, after a semicolon or colon: "...his score; and d) If a third"."""
_APPENDIX_START = re.compile(
    r"^(?P<word>APPENDIX|Appendix|ANNEX|Annex|ATTACHMENT|Attachment)\s+(?P<id>[0-9A-Z]{1,3})\b"
    r"[.:]?(?P<sep>\s+|$)"
)
_GROUP_START = re.compile(r"^\((?P<group>[A-Z])\)\s")
"""A group heading inside a rule, "(A) The offences listed below...", whose items restart at a."""
_TERMINAL = re.compile(r"[.;:!?][\"'\u201d\u2019)\]]*$")  # closing quotes may follow


@dataclass(frozen=True)
class RuleStart:
    rule_id: str
    printed: str
    """The number exactly as printed, e.g. "6.11.3" or "ARTICLE 2"."""
    rest_offset: int
    """Index in the row text where the text after the number begins."""
    malformed: bool = False
    """The printed number has a typo the parser corrected (e.g. "6.11.10..2")."""


@dataclass(frozen=True)
class ItemStart:
    label: str
    marker: str
    """The label as printed, e.g. "a)", "b).", "d)_" or "a."."""
    rest_offset: int
    tabbed: bool
    """True if the label is followed by a tab, which marks a real item even mid-paragraph."""
    dotted: bool = False
    """Printed as "a." rather than "a)". Easily confused with prose, so callers must check
    that the letter continues the rule's item sequence."""


@dataclass(frozen=True)
class InlineItem:
    label: str
    start: int
    """Where the item's marker begins in the text."""
    rest_offset: int
    cued: bool
    """Introduced by "and" or "or" after the semicolon, which the list's last item usually is."""


def match_rule_start(text: str) -> RuleStart | None:
    """Match a rule number at the start of `text`.

    A single-level number ("1", "ARTICLE 2") only counts when followed by a tab or introduced
    by ARTICLE, because bare integers also start ordinary sentences. The printed form may end
    in a dot ("4.", "1.9.1.5.") or contain a doubled dot ("6.11.10..2"); the rule id is
    normalized, the printed form is kept as is.
    """
    match = _RULE_START.match(text)
    if match is None:
        return None
    printed_id = match.group("id")
    rule_id = printed_id.replace("..", ".")
    single_level = "." not in rule_id
    if single_level and not match.group("article") and "\t" not in match.group("sep"):
        return None
    if not match.group("sep") and not match.group("article"):
        return None  # number alone on the row with nothing after it is not enough
    printed = " ".join(text[: match.start("sep")].split())
    return RuleStart(
        rule_id=rule_id,
        printed=printed,
        rest_offset=match.end(),
        malformed=rule_id != printed_id,
    )


def match_item_start(text: str) -> ItemStart | None:
    match = _ITEM_START.match(text)
    if match is None:
        return None
    sep = match.group("sep") if match.group("paren") else match.group("dot_sep")
    return ItemStart(
        label=match.group("label"),
        marker=text[: match.end()].rstrip(" \t"),
        rest_offset=match.end(),
        tabbed="\t" in sep,
        dotted=match.group("dot") is not None,
    )


def find_inline_items(text: str) -> list[InlineItem]:
    """Candidate items inside a paragraph. Callers must check the letter sequence."""
    return [
        InlineItem(
            label=m.group("label"),
            start=m.start("label"),
            rest_offset=m.end(),
            cued=m.group("cue") is not None,
        )
        for m in _INLINE_ITEM.finditer(text)
    ]


@dataclass(frozen=True)
class AppendixStart:
    key: str
    """Used in the record uid, e.g. "appendix-1"."""
    printed: str
    """As printed, e.g. "APPENDIX 1"."""
    rest_offset: int


def match_appendix_start(text: str) -> AppendixStart | None:
    """An unnumbered sub-document heading such as "APPENDIX 1  DEFINITIONS". Callers check that
    it is bold and sits in the rule-number column."""
    match = _APPENDIX_START.match(text)
    if match is None:
        return None
    return AppendixStart(
        key=f"{match.group('word').lower()}-{match.group('id').lower()}",
        printed=" ".join(text[: match.start("sep")].split()),
        rest_offset=match.end(),
    )


def match_group_start(text: str) -> str | None:
    """The group letter of "(A) ..." at the start of `text`, if any."""
    match = _GROUP_START.match(text)
    return match.group("group") if match else None


def next_label(label: str | None) -> str:
    """The item letter that follows `label` ("a" at the start of a list)."""
    if label is None:
        return "a"
    letter = label.rpartition(".")[2]
    return chr(ord(letter[-1]) + 1) if len(letter) == 1 else ""


def ends_sentence(text: str) -> bool:
    """True if `text` ends like a finished sentence or clause (".", ";", ":", "?" ...)."""
    stripped = text.rstrip()
    if stripped.endswith((" and", " or")):
        return False
    return bool(_TERMINAL.search(stripped))


def rule_level(rule_id: str) -> int:
    return rule_id.count(".") + 1


def parent_rule_id(rule_id: str) -> str | None:
    head, sep, _ = rule_id.rpartition(".")
    return head if sep else None
