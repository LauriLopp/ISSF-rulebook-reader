"""Validate stage: run all checks over the parsed document and summarize the results."""

from __future__ import annotations

from collections.abc import Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument
from issf_rules.models.report import Finding, ValidationReport
from issf_rules.validate.checks import ALL_CHECKS, Check
from issf_rules.validate.report import render_markdown

__all__ = ["render_markdown", "validate"]

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def validate(
    parsed: ParsedDocument, pages: Sequence[PageLayout], checks: Sequence[Check] = ALL_CHECKS
) -> ValidationReport:
    findings: list[Finding] = []
    for check in checks:
        findings.extend(check(parsed, pages))
    findings.sort(
        key=lambda f: (
            _SEVERITY_ORDER[f.severity],
            f.check,
            f.pdf_page or 0,
            f.uid or "",
            f.message,
        )
    )
    return ValidationReport(
        source_id=parsed.source.id, counts=_counts(parsed, pages), findings=tuple(findings)
    )


def _counts(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> dict[str, int]:
    body_lines = sum(len(page.lines) for page in pages)
    # Definitions repeat text of other records, so their references would be counted twice.
    refs = [ref for r in parsed.rules if r.kind != "definition" for ref in r.cross_refs]
    return {
        "pages": len(pages),
        "body_lines": body_lines,
        "assigned_lines": len({(a.pdf_page, a.line_index) for a in parsed.assignments}),
        "divisions": len(parsed.divisions),
        "rules": sum(1 for rule in parsed.rules if rule.kind == "rule"),
        "preambles": sum(1 for rule in parsed.rules if rule.kind == "preamble"),
        "definitions": sum(1 for rule in parsed.rules if rule.kind == "definition"),
        "items": sum(len(rule.items) for rule in parsed.rules),
        "tables": len(parsed.tables),
        "figures": len(parsed.figures),
        "cross_refs": len(refs),
        "cross_refs_external": sum(1 for ref in refs if ref.external),
        "cross_refs_unresolved": sum(
            1 for ref in refs if ref.target_uid is None and not ref.external
        ),
    }
