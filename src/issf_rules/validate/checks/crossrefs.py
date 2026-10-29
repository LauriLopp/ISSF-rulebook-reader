"""Cross-references that point nowhere, or to an item the target rule does not have.

References to documents outside the book (the WADA Code, International Standards) cannot
resolve by design; they are listed as notes, not warnings.
"""

from __future__ import annotations

from collections.abc import Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import CrossRef, ParsedDocument, RuleRecord
from issf_rules.models.report import Finding

CHECK = "cross-reference"
CHECK_EXTERNAL = "external-reference"


def check_cross_references(parsed: ParsedDocument, pages: Sequence[PageLayout]) -> list[Finding]:
    by_uid = {rule.uid: rule for rule in parsed.rules}
    findings: list[Finding] = []
    for rule in parsed.rules:
        page = rule.pages[0].pdf_page if rule.pages else None
        source = rule.printed_number or "preamble"
        for ref in rule.cross_refs:
            if ref.external:
                findings.append(
                    Finding(
                        check=CHECK_EXTERNAL,
                        severity="info",
                        uid=rule.uid,
                        pdf_page=page,
                        message=f"{source} cites {ref.raw!r} of the {ref.document} "
                        "(not part of this book)",
                    )
                )
            elif ref.target_uid is None:
                findings.append(
                    Finding(
                        check=CHECK,
                        severity="warning",
                        uid=rule.uid,
                        pdf_page=page,
                        message=f"{source} cites {ref.raw!r}: {_not_found(ref, rule)}",
                    )
                )
            else:
                target = by_uid[ref.target_uid]
                labels = {item.label for item in target.items}
                if ref.target_item and labels and ref.target_item not in labels:
                    findings.append(
                        Finding(
                            check=CHECK,
                            severity="warning",
                            uid=rule.uid,
                            pdf_page=page,
                            message=f"{source} cites {ref.raw!r}: {target.rule_id} has no "
                            f"item {ref.target_item})",
                        )
                    )
    return findings


def _not_found(ref: CrossRef, rule: RuleRecord) -> str:
    if ref.document is not None:
        return f"no rule {ref.target_rule_id} in the {ref.document} as printed in this book"
    part = f"part-{ref.target_rule_id.split('.')[0]}"
    places = rule.namespace if rule.namespace == part else f"{rule.namespace} or {part}"
    return f"no rule {ref.target_rule_id} in {places}"
