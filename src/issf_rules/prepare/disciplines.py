"""Tagging records with the shooting discipline(s) they apply to.

A discipline's own part ("Rifle Rules", "Pistol Rule") is recognized by its title: it names
exactly one discipline and the word "Rule(s)". Its records apply to that discipline. Records
elsewhere (mainly the General Technical Rules) are tagged by the disciplines they mention, or
"general" if none.
Used for filtering and for asking "which discipline?" on ambiguous questions.
"""

from __future__ import annotations

import re

from issf_rules.models.records import RuleRecord
from issf_rules.models.retrieval import Discipline

_MENTIONS: tuple[tuple[Discipline, re.Pattern[str]], ...] = (
    ("rifle", re.compile(r"\brifles?\b", re.IGNORECASE)),
    ("pistol", re.compile(r"\bpistols?\b", re.IGNORECASE)),
    ("shotgun", re.compile(r"\b(?:shotguns?|trap|skeet|clay targets?)\b", re.IGNORECASE)),
    ("moving-target", re.compile(r"\b(?:moving|running) targets?\b", re.IGNORECASE)),
    ("target-sprint", re.compile(r"\btarget sprint\b", re.IGNORECASE)),
)


_RULES_TITLE = re.compile(r"\brules?\b", re.IGNORECASE)


def part_discipline(title: str) -> Discipline | None:
    """The discipline whose own rules a division with this title holds, if any."""
    named = [name for name, pattern in _MENTIONS if pattern.search(title)]
    return named[0] if len(named) == 1 and _RULES_TITLE.search(title) else None


def disciplines_for(
    rule: RuleRecord, division_title: str = "", extra_text: str = ""
) -> tuple[Discipline, ...]:
    part = part_discipline(division_title)
    if part is not None:
        return (part,)
    text = " ".join((*rule.heading_path, rule.official_text, extra_text))
    found = tuple(name for name, pattern in _MENTIONS if pattern.search(text))
    return found or ("general",)
