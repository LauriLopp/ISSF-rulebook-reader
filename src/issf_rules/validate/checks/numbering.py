"""Rule-number checks: misprints, duplicates, gaps, missing parents, missing headings.

One misprinted number in the source (e.g. "8.7.3" printed in the Shotgun rules where 9.7.3
belongs) would otherwise trigger several confusing findings: a missing parent "8.7", a gap
before "8.7.3", and a gap before the next rule "9.7.4". So the intended number of each rule is
worked out first, from its neighbours in reading order. Misprints are reported once, and the
gap and parent checks then use the intended numbers.

All checks run per namespace (part, annex or section), because numbers restart there.
Messages name the division, so "8.7 not found" cannot be mistaken for Pistol rule 8.7.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import Division, ParsedDocument, RuleRecord
from issf_rules.models.report import Finding
from issf_rules.parse.patterns import parent_rule_id

CHECK_MISNUMBERED = "misnumbered"
CHECK_DUPLICATE = "duplicate-id"
CHECK_MALFORMED = "malformed-number"
CHECK_GAP = "numbering-gap"
CHECK_PREFIX = "part-prefix"
CHECK_PARENT = "missing-parent"
CHECK_HEADING = "missing-heading"
PREFIX_MAJORITY = 0.8
"""A part "uses its number as prefix" if at least this share of its rules do (e.g. Part 6 → 6.x)."""
MAX_LEVELS = 4


@dataclass(frozen=True)
class _Context:
    namespace: str
    label: str
    """Human-readable division name for messages, e.g. "Shotgun Rules (part-9)"."""
    part_number: str | None
    rules: list[RuleRecord]
    intended: dict[str, str]
    """uid → the number the rule most likely should have, for rules judged misnumbered."""

    def number(self, rule: RuleRecord) -> str:
        assert rule.rule_id is not None
        return self.intended.get(rule.uid, rule.rule_id)


def check_numbering(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    divisions = {division.namespace: division for division in parsed.divisions}
    grouped: dict[str, list[RuleRecord]] = defaultdict(list)
    for rule in parsed.rules:
        if rule.rule_id is not None:
            grouped[rule.namespace].append(rule)

    findings: list[Finding] = []
    for namespace, rules in grouped.items():
        division = divisions.get(namespace)
        ctx = _Context(
            namespace=namespace,
            label=f"{division.title} ({namespace})" if division else namespace,
            part_number=_part_number(division),
            rules=rules,
            intended=find_misnumbered(rules),
        )
        findings += _misnumbered(ctx)
        findings += _wrong_prefix(ctx)
        findings += _duplicates(ctx)
        findings += _malformed(ctx)
        findings += _gaps(ctx)
        findings += _missing_parents(ctx)
        findings += _missing_headings(ctx)
    return findings


def plausible_next(number: str) -> set[str]:
    """Numbers that may directly follow `number`: its first child, its next sibling, or the
    next sibling of any ancestor ("9.7.2" → 9.7.2.1, 9.7.3, 9.8, 10)."""
    parts = [int(p) for p in number.split(".")]
    following = {
        ".".join(map(str, [*parts[:depth], parts[depth] + 1])) for depth in range(len(parts))
    }
    if len(parts) < MAX_LEVELS:
        following.add(f"{number}.1")
    return following


def find_misnumbered(rules: Sequence[RuleRecord]) -> dict[str, str]:
    """Rules whose number does not fit between their neighbours, but would if exactly one
    component were different (9.7.2 → "8.7.3" → 9.7.4 gives 9.7.3)."""
    intended: dict[str, str] = {}
    previous: str | None = None
    for i, rule in enumerate(rules):
        assert rule.rule_id is not None
        number = rule.rule_id
        following = rules[i + 1].rule_id if i + 1 < len(rules) else None
        # Both neighbours must confirm the guess; at either end of a division there is too
        # little evidence, and the gap/parent checks report the problem instead.
        if (
            previous is not None
            and following is not None
            and number not in plausible_next(previous)
        ):
            candidates = [
                candidate
                for candidate in sorted(plausible_next(previous))
                if _differs_in_one_component(candidate, number)
                and following in plausible_next(candidate)
            ]
            if len(candidates) == 1:
                intended[rule.uid] = candidates[0]
                number = candidates[0]
        previous = number
    return intended


def _misnumbered(ctx: _Context) -> list[Finding]:
    findings = []
    for i, rule in enumerate(ctx.rules):
        if rule.uid not in ctx.intended:
            continue
        before = ctx.number(ctx.rules[i - 1])
        after = ctx.number(ctx.rules[i + 1]) if i + 1 < len(ctx.rules) else "the end"
        intended = ctx.intended[rule.uid]
        last_differs = intended.split(".")[-1] != (rule.rule_id or "").split(".")[-1]
        # A different *last* component can also be a deleted rule; any other component is a
        # near-certain typo (a wrong part or section number).
        findings.append(
            Finding(
                check=CHECK_MISNUMBERED,
                severity="warning" if last_differs else "error",
                uid=rule.uid,
                pdf_page=_page(rule),
                message=(
                    f"in {ctx.label}: number printed as {rule.printed_number!r} between "
                    f"{before} and {after}; probably a misprint of {intended}"
                    + (f" (or {intended} was removed)" if last_differs else "")
                ),
            )
        )
    return findings


def _wrong_prefix(ctx: _Context) -> list[Finding]:
    """Rules outside the part's numbering that the neighbour check could not explain."""
    if ctx.part_number is None:
        return []
    rules = ctx.rules
    matching = [r for r in rules if (r.rule_id or "").split(".")[0] == ctx.part_number]
    if len(matching) < PREFIX_MAJORITY * len(rules):
        return []  # this part has its own numbering scheme (e.g. anti-doping articles)
    return [
        Finding(
            check=CHECK_PREFIX,
            severity="error",
            uid=rule.uid,
            pdf_page=_page(rule),
            message=f"in {ctx.label}: rule {rule.printed_number} does not start with "
            f"{ctx.part_number}: misprint in the source or a misparse",
        )
        for rule in rules
        if rule.uid not in ctx.intended and ctx.number(rule).split(".")[0] != ctx.part_number
    ]


def _duplicates(ctx: _Context) -> list[Finding]:
    return [
        Finding(
            check=CHECK_DUPLICATE,
            severity="error",
            uid=rule.uid,
            pdf_page=_page(rule),
            message=f"in {ctx.label}: rule {rule.printed_number} appears more than once",
        )
        for rule in ctx.rules
        if "duplicate-id" in rule.parse_flags
    ]


def _malformed(ctx: _Context) -> list[Finding]:
    return [
        Finding(
            check=CHECK_MALFORMED,
            severity="warning",
            uid=rule.uid,
            pdf_page=_page(rule),
            message=f"in {ctx.label}: number printed as {rule.printed_number!r}, "
            f"read as {rule.rule_id}",
        )
        for rule in ctx.rules
        if "malformed-number" in rule.parse_flags
    ]


def _gaps(ctx: _Context) -> list[Finding]:
    """Numbers whose previous sibling is missing (6.11.5 present, 6.11.4 absent)."""
    present = {ctx.number(rule) for rule in ctx.rules}
    findings = []
    for rule in ctx.rules:
        number = ctx.number(rule)
        head, _, last = number.rpartition(".")
        if int(last) <= 1:
            continue
        previous = f"{head}.{int(last) - 1}" if head else str(int(last) - 1)
        if previous not in present:
            findings.append(
                Finding(
                    check=CHECK_GAP,
                    severity="warning",
                    uid=rule.uid,
                    pdf_page=_page(rule),
                    message=f"in {ctx.label}: {number} found but {previous} is missing",
                )
            )
    return findings


def _missing_parents(ctx: _Context) -> list[Finding]:
    """A rule's parent number should exist, except the part itself ("6" for rule 6.1)."""
    present = {ctx.number(rule) for rule in ctx.rules}
    findings = []
    for rule in ctx.rules:
        parent = parent_rule_id(ctx.number(rule))
        if parent is not None and parent not in present and parent != ctx.part_number:
            findings.append(
                Finding(
                    check=CHECK_PARENT,
                    severity="warning",
                    uid=rule.uid,
                    pdf_page=_page(rule),
                    message=f"in {ctx.label}: parent {parent} of {ctx.number(rule)} not found",
                )
            )
    return findings


def _missing_headings(ctx: _Context) -> list[Finding]:
    """A rule with sub-rules should introduce them with a heading or some text."""
    parents = {parent_rule_id(ctx.number(rule)) for rule in ctx.rules}
    return [
        Finding(
            check=CHECK_HEADING,
            severity="warning",
            uid=rule.uid,
            pdf_page=_page(rule),
            message=f"in {ctx.label}: {rule.rule_id} has sub-rules but neither heading nor text",
        )
        for rule in ctx.rules
        if ctx.number(rule) in parents and not rule.heading and not rule.official_text
    ]


def _differs_in_one_component(a: str, b: str) -> bool:
    pa, pb = a.split("."), b.split(".")
    return len(pa) == len(pb) and sum(x != y for x, y in zip(pa, pb, strict=True)) == 1


def _part_number(division: Division | None) -> str | None:
    if division is None or division.kind != "part":
        return None
    return division.number


def _page(rule: RuleRecord) -> int | None:
    return rule.pages[0].pdf_page if rule.pages else None
