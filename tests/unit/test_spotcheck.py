"""Which pages the spot-check sheet shows, and why."""

from helpers import SOURCE
from issf_rules.cli import parse_pages
from issf_rules.models.records import (
    FigureRecord,
    PageRef,
    ParsedDocument,
    RuleRecord,
    TableRecord,
)
from issf_rules.models.report import Finding, ValidationReport
from issf_rules.review import page_reasons


def ref(page: int) -> PageRef:
    return PageRef(pdf_page=page, printed_page=str(page), bbox=(0, 0, 1, 1))


def record(rule_id: str, pages: list[int], **extra: object) -> RuleRecord:
    return RuleRecord(
        uid=f"b:part-6:{rule_id}",
        kind="rule",
        namespace="part-6",
        rule_id=rule_id,
        printed_number=rule_id,
        parent_id=None,
        level=2,
        heading=None,
        heading_path=(),
        official_text="Text.",
        pages=tuple(ref(p) for p in pages),
        **extra,  # type: ignore[arg-type]
    )


def test_pages_are_selected_by_what_is_on_them() -> None:
    parsed = ParsedDocument(
        source=SOURCE,
        divisions=(),
        rules=(
            record("6.1", [10]),  # nothing notable
            record("6.2", [11, 12]),  # continues on 12
            record("6.3", [13], parse_flags=("heading-not-bold",)),
        ),
        tables=(
            TableRecord(uid="b:table:p0014-0", rule_uid="b:part-6:6.3", page=ref(14), rows=()),
        ),
        figures=(
            FigureRecord(
                uid="b:figure:p0013-0",
                rule_uid="b:part-6:6.3",
                page=ref(13),
                image_file=None,
                text="",
            ),
        ),
        assignments=(),
    )
    report = ValidationReport(
        source_id="b",
        counts={},
        findings=(
            Finding(check="table-quality", severity="warning", message="m", pdf_page=14),
            Finding(check="numbering-gap", severity="warning", message="m", pdf_page=15),
            Finding(check="table-text", severity="info", message="m", pdf_page=16),  # a note
        ),
    )
    assert page_reasons(parsed, report) == {
        12: {"page break"},
        13: {"guessed heading", "figure"},
        14: {"table", "table warning"},
        15: {"finding"},
    }


def test_page_ranges() -> None:
    assert parse_pages("340-342, 398") == [340, 341, 342, 398]
