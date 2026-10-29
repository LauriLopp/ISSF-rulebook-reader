"""Figure links: every figure belongs to a record, and that record lists it.

A figure attaches to whichever record is open where it appears on the page. A broken link in
either direction is an error. A figure owned by a division's introduction rather than a
numbered rule is worth a look (usually a logo or title artwork), so it is reported as a note.
"""

from __future__ import annotations

from collections.abc import Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument
from issf_rules.models.report import Finding

CHECK = "figure-link"


def check_figures(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    records = {rule.uid: rule for rule in parsed.rules}
    figures = {figure.uid for figure in parsed.figures}
    findings: list[Finding] = []
    for figure in parsed.figures:
        owner = records.get(figure.rule_uid)
        page = figure.page.pdf_page
        if owner is None:
            message = f"{figure.uid} belongs to {figure.rule_uid}, which does not exist"
        elif figure.uid not in owner.figure_uids:
            message = f"{figure.uid} names {owner.uid} as its rule, but that rule does not list it"
        elif owner.rule_id is None:
            findings.append(
                Finding(
                    check=CHECK,
                    severity="info",
                    uid=figure.uid,
                    pdf_page=page,
                    message=f"{figure.uid} is not in a numbered rule but in {owner.uid} "
                    "(logo or title artwork?)",
                )
            )
            continue
        else:
            continue
        findings.append(
            Finding(check=CHECK, severity="error", uid=figure.uid, pdf_page=page, message=message)
        )
    for rule in parsed.rules:
        for uid in rule.figure_uids:
            if uid not in figures:
                findings.append(
                    Finding(
                        check=CHECK,
                        severity="error",
                        uid=rule.uid,
                        pdf_page=rule.pages[0].pdf_page if rule.pages else None,
                        message=f"{rule.uid} lists {uid}, which does not exist",
                    )
                )
    return findings
