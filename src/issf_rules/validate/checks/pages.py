"""Page-level checks: running footer, edition consistency, and pages with little text."""

from __future__ import annotations

from collections.abc import Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument
from issf_rules.models.report import Finding
from issf_rules.validate.checks.coverage import count_visible

CHECK_FOOTER = "page-footer"
CHECK_LOW_TEXT = "low-text-page"
LOW_TEXT_CHARS = 200
"""Body pages with fewer visible characters than this are listed for review."""


def check_footers(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    """Every page should carry this source's edition and print, and its own page number."""
    findings: list[Finding] = []
    edition = parsed.source.edition.lower()
    print_run = parsed.source.print_run.lower()
    for page in pages:
        footer = page.footer
        if footer is None:
            findings.append(
                Finding(
                    check=CHECK_FOOTER,
                    severity="info",
                    pdf_page=page.pdf_page,
                    message="page has no running footer",
                )
            )
            continue
        text = footer.text.lower()
        if edition not in text or print_run not in text:
            findings.append(
                Finding(
                    check=CHECK_FOOTER,
                    severity="error",
                    pdf_page=page.pdf_page,
                    message=f"footer does not match {parsed.source.edition} "
                    f"({parsed.source.print_run}): {footer.text!r}",
                )
            )
        if footer.printed_page != str(page.pdf_page):
            findings.append(
                Finding(
                    check=CHECK_FOOTER,
                    severity="warning",
                    pdf_page=page.pdf_page,
                    message=f"printed page number {footer.printed_page!r} differs from PDF page",
                )
            )
    return findings


def check_low_text(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    findings: list[Finding] = []
    consumers: dict[int, set[str]] = {}
    for a in parsed.assignments:
        consumers.setdefault(a.pdf_page, set()).add(a.consumer)
    for page in pages:
        chars = sum(count_visible(line.text) for line in page.lines)
        if chars >= LOW_TEXT_CHARS:
            continue
        if chars == 0 and not page.figures and not page.tables:
            findings.append(
                Finding(
                    check=CHECK_LOW_TEXT,
                    severity="info",
                    pdf_page=page.pdf_page,
                    message="blank page",
                )
            )
            continue
        has_title = any(line.size >= 20 for line in page.lines)
        what = []
        if consumers.get(page.pdf_page) == {"contents"}:
            what.append("contents page")
        if has_title:
            what.append("title page")
        if page.figures:
            what.append(f"{len(page.figures)} figure(s)")
        if page.tables:
            what.append(f"{len(page.tables)} table(s)")
        explained = ", ".join(what) if what else "nothing else on the page"
        findings.append(
            Finding(
                check=CHECK_LOW_TEXT,
                severity="info" if what else "warning",
                pdf_page=page.pdf_page,
                message=f"only {chars} characters of text ({explained})",
            )
        )
    return findings
