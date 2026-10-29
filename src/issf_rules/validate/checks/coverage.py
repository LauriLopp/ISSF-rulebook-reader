"""Text coverage: every body line is used exactly once, and no text is lost or invented.

This is the pipeline's key invariant. If a parser change drops a line, assigns it twice, or
alters characters while joining text, this check reports it. Definition records repeat text
from a table or a glossary paragraph rather than consuming lines, so for them the check is that
the term and its text appear unchanged in their source.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument, RuleRecord
from issf_rules.models.report import Finding

CHECK = "coverage"


def check_coverage(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    return (
        _line_assignment(parsed, pages)
        + _character_balance(parsed, pages)
        + _definitions_match_source(parsed)
    )


def _line_assignment(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    findings: list[Finding] = []
    assigned = Counter((a.pdf_page, a.line_index) for a in parsed.assignments)
    for page in pages:
        unassigned = [line for line in page.lines if (page.pdf_page, line.index) not in assigned]
        if unassigned:
            sample = " / ".join(line.text.strip() for line in unassigned[:3])
            findings.append(
                Finding(
                    check=CHECK,
                    severity="error",
                    pdf_page=page.pdf_page,
                    message=f"{len(unassigned)} line(s) not assigned to any record: {sample[:150]}",
                )
            )
    for (pdf_page, index), count in sorted(assigned.items()):
        if count > 1:
            findings.append(
                Finding(
                    check=CHECK,
                    severity="error",
                    pdf_page=pdf_page,
                    message=f"line {index} assigned {count} times",
                )
            )
    return findings


def _character_balance(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    """A rule record must hold exactly the non-space characters of the lines it consumed."""
    line_text = {(page.pdf_page, line.index): line.text for page in pages for line in page.lines}
    consumed: dict[str, int] = defaultdict(int)
    for a in parsed.assignments:
        consumed[a.consumer] += count_visible(line_text.get((a.pdf_page, a.line_index), ""))

    findings: list[Finding] = []
    for rule in parsed.rules:
        if rule.kind == "definition":
            continue
        produced = record_visible(rule)
        if produced != consumed.get(rule.uid, 0):
            findings.append(
                Finding(
                    check=CHECK,
                    severity="error",
                    uid=rule.uid,
                    pdf_page=rule.pages[0].pdf_page if rule.pages else None,
                    message=(
                        f"text mismatch: source lines hold {consumed.get(rule.uid, 0)} "
                        f"characters, record holds {produced}"
                    ),
                )
            )
    return findings


def _definitions_match_source(parsed: ParsedDocument) -> list[Finding]:
    tables = {table.uid: table for table in parsed.tables}
    records = {rule.uid: rule for rule in parsed.rules}
    findings = []
    for rule in parsed.rules:
        if rule.kind != "definition":
            continue
        if rule.table_uids:
            cells = {cell for uid in rule.table_uids for row in tables[uid].rows for cell in row}
            intact = rule.heading in cells and rule.official_text in cells
        else:
            source = records.get(rule.defined_in or "")
            entry = f"{rule.heading}: {rule.official_text}"
            intact = source is not None and entry in source.official_text
        if not intact:
            findings.append(
                Finding(
                    check=CHECK,
                    severity="error",
                    uid=rule.uid,
                    pdf_page=rule.pages[0].pdf_page if rule.pages else None,
                    message=f"definition of {rule.heading!r} differs from its table",
                )
            )
    return findings


def count_visible(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def record_visible(rule: RuleRecord) -> int:
    """Visible characters of what the record shows: printed number, heading, text (with labels)."""
    return (
        count_visible(rule.printed_number or "")
        + count_visible(rule.heading or "")
        + count_visible(rule.official_text)
    )
