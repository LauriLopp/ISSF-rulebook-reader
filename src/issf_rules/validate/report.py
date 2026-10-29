"""Human-readable rendering of a validation report."""

from __future__ import annotations

from collections import defaultdict

from issf_rules.models.report import Finding, ValidationReport

MAX_EXAMPLES = 25
"""Findings listed per check; the full list is in validation.json."""


def render_markdown(report: ValidationReport) -> str:
    lines = [
        f"# Validation report: {report.source_id}",
        "",
        f"**{report.count('error')} errors, {report.count('warning')} warnings, "
        f"{report.count('info')} notes.**",
        "",
        "| Measure | Value |",
        "|---|---|",
        *(f"| {name} | {value} |" for name, value in report.counts.items()),
        "",
    ]
    by_check: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for finding in report.findings:
        by_check[(finding.severity, finding.check)].append(finding)

    for (severity, check), findings in by_check.items():
        lines += [f"## {severity}: {check} ({len(findings)})", ""]
        for finding in findings[:MAX_EXAMPLES]:
            where = []
            if finding.pdf_page is not None:
                where.append(f"p. {finding.pdf_page}")
            if finding.uid is not None:
                where.append(f"`{finding.uid}`")
            prefix = f"{', '.join(where)}: " if where else ""
            lines.append(f"- {prefix}{finding.message}")
        if len(findings) > MAX_EXAMPLES:
            lines.append(f"- … {len(findings) - MAX_EXAMPLES} more in validation.json")
        lines.append("")
    return "\n".join(lines)
