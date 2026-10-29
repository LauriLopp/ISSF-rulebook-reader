"""Finding and resolving references from one rule to another.

The book writes references in many forms: "see Rule 6.4.11.10.c", "Rules 6.17.1.6, 6.17.4.m and
6.17.5.l", "(6.16.6)", "6.17.4.o)", "G.T.R. 6.3.6.1", "Article 2.1". Bare numbers such as
"10.2" (a score) or "1.00m" also appear, so a number only counts as a reference when it follows a
cue word, or stands inside parentheses that hold nothing but references.

Some references name another document: "Article 14.5 ISSF Constitution" (printed in this book as
Part 1, with every number prefixed by "1.", so it resolves to rule 1.14.5), or "Article 20.7.10 of
the Code" (the WADA Code, not part of this book, so it is external and left unresolved).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from issf_rules.models.records import CrossRef, Division

_ID = r"\d{1,2}(?:\.\d{1,3}){1,3}"
_TOKEN = re.compile(
    rf"(?<![\d.])(?P<id>{_ID})(?:(?:\.|\s)(?P<item>[a-z])\)?(?![A-Za-z]))?(?![\d])(?!\s?(?:mm|cm|m|kg|g|sec|s|%)\b)"
)
_CUE = re.compile(
    r"(?:\bRules?|\bArticles?|\bG\.?\s?T\.?\s?R\.?|\b[Ss]ee(?:\s+[Aa]lso)?|\bSEE(?:\s+ALSO)?|\bRegulations,)\s*$"
)
_LIST_GLUE = re.compile(r"^(?:\s|,|and|or|to|\u2013|-|/|&|\.|[a-z]\))*$")  # \u2013: en dash
_DOCUMENT = re.compile(
    # Used with .match(text, pos), which anchors at pos (a "^" would only match at 0).
    # Optional list continuation ("and 7.0", "-3") before the document name.
    r"(?:\s*(?:,|and|or|-|\u2013)\s*\d[\d.]*)*\s*"
    r"(?:(?P<constitution>(?:of\s+the\s+)?ISSF\s+Constitution)"
    r"|(?P<code>of\s+the\s+(?:World\s+Anti-Doping\s+)?Code)\b"
    r"|(?P<standard>of\s+the\s+International\s+Standard))"
)
CONSTITUTION = "ISSF Constitution"
_DOCUMENT_TITLES = {CONSTITUTION: re.compile(r"\bConstitution\b", re.IGNORECASE)}
"""How to recognize, by its title, the part of the book that prints a cited document."""
_PAREN_ONLY = re.compile(
    r"^\(\s*(?:(?:Rules?|see|See|and|or|,|\u2013|-|/|\s)*" + _ID + r"[\s.a-z)]*)+\)$"
)


@dataclass(frozen=True)
class FoundRef:
    raw: str
    rule_id: str
    item: str | None
    document: str | None = None
    """Set when the reference names another document, e.g. "ISSF Constitution"."""


def find_references(text: str) -> list[FoundRef]:
    found: list[FoundRef] = []
    seen: set[tuple[str, str | None]] = set()
    previous_end: int | None = None
    previous_was_ref = False
    for match in _TOKEN.finditer(text):
        before = text[: match.start()]
        is_ref = bool(_CUE.search(before[-30:]))
        if not is_ref and previous_was_ref and previous_end is not None:
            is_ref = bool(_LIST_GLUE.match(text[previous_end : match.start()]))
        if not is_ref:
            is_ref = _inside_reference_parentheses(text, match.start(), match.end())
        if is_ref and _is_part_or_decimal(match.group("id")):
            is_ref = False
        previous_was_ref = is_ref
        previous_end = match.end()
        if not is_ref:
            continue
        key = (match.group("id"), match.group("item"))
        if key in seen:
            continue
        seen.add(key)
        found.append(
            FoundRef(
                raw=match.group(0).strip(),
                rule_id=key[0],
                item=key[1],
                document=_document_after(text, match.end()),
            )
        )
    return found


def _document_after(text: str, end: int) -> str | None:
    match = _DOCUMENT.match(text, end)
    if match is None:
        return None
    if match.group("constitution"):
        return CONSTITUTION
    return "WADA Code" if match.group("code") else "International Standard"


def documents_in_book(divisions: Sequence[Division]) -> dict[str, tuple[str, str]]:
    """Cited documents that the book itself prints as a part, found by the part's title:
    document → (namespace, prefix the book adds to its article numbers, e.g. "1.")."""
    found: dict[str, tuple[str, str]] = {}
    for document, title in _DOCUMENT_TITLES.items():
        for division in divisions:
            if division.kind == "part" and division.number and title.search(division.title):
                found.setdefault(document, (division.namespace, f"{division.number}."))
    return found


def resolve(
    refs: list[FoundRef],
    namespace: str,
    index: Mapping[tuple[str, str], str],
    documents: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[CrossRef, ...]:
    """Look each reference up in its own namespace first, then in the part its number names.

    References to a document printed inside the book (`documents`, see `documents_in_book`)
    are looked up there; references to other documents are external and not looked up.
    `index` maps (namespace, rule_id) to the uid of the first rule with that number.
    """
    documents = documents or {}
    resolved: list[CrossRef] = []
    for ref in refs:
        rule_id = ref.rule_id
        uid: str | None = None
        if ref.document is not None and ref.document in documents:
            # Citations use either the document's own numbering ("Article 14.5 ISSF
            # Constitution" = rule 1.14.5) or the book's ("Article 1.1.4.1 ISSF Constitution").
            doc_namespace, prefix = documents[ref.document]
            if not rule_id.startswith(prefix):
                rule_id = prefix + rule_id
            uid = index.get((doc_namespace, rule_id))
        elif ref.document is None:
            part_namespace = f"part-{rule_id.split('.')[0]}"
            uid = index.get((namespace, rule_id)) or index.get((part_namespace, rule_id))
        resolved.append(
            CrossRef(
                raw=ref.raw,
                target_rule_id=rule_id,
                target_item=ref.item,
                target_uid=uid,
                document=ref.document,
                external=ref.document is not None and ref.document not in documents,
            )
        )
    return tuple(resolved)


def _is_part_or_decimal(rule_id: str) -> bool:
    """True for numbers that are not rule numbers: "7.0" cites a whole part, and rule number
    components never start with 0 ("1.05" is a measurement)."""
    return any(component.startswith("0") for component in rule_id.split(".")[1:])


def _inside_reference_parentheses(text: str, start: int, end: int) -> bool:
    """True for "(6.16.6)" or "(3.12.3.7, 6.16.6 and 6.17.1.10.d.)", but not "(1.50)".

    A lone two-level number in parentheses is too often a measurement, so at least three
    levels are required here (references with a cue word, like "Rule 6.2", need not).
    """
    if text[start:end].count(".") < 2:
        return False
    open_at = text.rfind("(", 0, start)
    close_at = text.find(")", end)
    if open_at == -1 or close_at == -1 or ")" in text[open_at + 1 : start]:
        return False
    # Allow a trailing item paren like "(6.17.1.10 d)" by extending to the last ")" nearby.
    extended = text.find(")", close_at + 1)
    for candidate in (close_at, extended):
        if candidate != -1 and _PAREN_ONLY.match(text[open_at : candidate + 1]):
            return True
    return False
