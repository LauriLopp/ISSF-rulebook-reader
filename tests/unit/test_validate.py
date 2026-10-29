"""Each check must catch the defect it exists for. Documents are built by hand."""

from helpers import SOURCE, line, page
from issf_rules.models.layout import PageLayout
from issf_rules.models.records import (
    CrossRef,
    Division,
    FigureRecord,
    LineAssignment,
    PageRef,
    ParsedDocument,
    RuleRecord,
    TableRecord,
)
from issf_rules.validate import validate
from issf_rules.validate.checks.coverage import check_coverage
from issf_rules.validate.checks.crossrefs import check_cross_references
from issf_rules.validate.checks.figures import check_figures
from issf_rules.validate.checks.numbering import check_numbering
from issf_rules.validate.checks.pages import check_footers
from issf_rules.validate.checks.tables import damaged_words

PART9 = Division(
    namespace="part-9", kind="part", number="9", title="Shotgun Rules", first_page=1, last_page=1
)


def rule(rule_id: str, text: str = "Text.", **extra: object) -> RuleRecord:
    return RuleRecord(
        uid=f"test-book:part-9:{rule_id}",
        kind="rule",
        namespace="part-9",
        rule_id=rule_id,
        printed_number=rule_id,
        parent_id=rule_id.rpartition(".")[0] or None,
        level=rule_id.count(".") + 1,
        heading=None,
        heading_path=("Shotgun Rules",),
        official_text=text,
        pages=(PageRef(pdf_page=1, printed_page="1", bbox=(0, 0, 1, 1)),),
        **extra,  # type: ignore[arg-type]
    )


def doc(rules: list[RuleRecord], assignments: list[LineAssignment] | None = None) -> ParsedDocument:
    return ParsedDocument(
        source=SOURCE,
        divisions=(PART9,),
        rules=tuple(rules),
        tables=(),
        figures=(),
        assignments=tuple(assignments or ()),
    )


def checks_named(findings: list, name: str) -> list:  # type: ignore[type-arg]
    return [f for f in findings if f.check == name]


def test_coverage_reports_unassigned_and_doubly_assigned_lines() -> None:
    pages = [page(1, [line("9.1\t", 85, 100), line("Orphan line.", 141.7, 120)])]
    assignments = [
        LineAssignment(pdf_page=1, line_index=0, consumer="test-book:part-9:9.1"),
        LineAssignment(pdf_page=1, line_index=0, consumer="contents"),
    ]
    findings = check_coverage(doc([rule("9.1", "")], assignments), pages)
    messages = [f.message for f in findings]
    assert any("not assigned" in m for m in messages)
    assert any("assigned 2 times" in m for m in messages)


def test_coverage_detects_text_lost_while_joining() -> None:
    pages = [page(1, [line("9.1\t", 85, 100), line("Shots are scored.", 141.7, 100)])]
    assignments = [
        LineAssignment(pdf_page=1, line_index=i, consumer="test-book:part-9:9.1") for i in (0, 1)
    ]
    ok = check_coverage(doc([rule("9.1", "Shots are scored.")], assignments), pages)
    broken = check_coverage(doc([rule("9.1", "Shots are")], assignments), pages)
    assert ok == []
    assert len(broken) == 1 and "text mismatch" in broken[0].message


def test_misprinted_number_is_reported_once_with_the_likely_number() -> None:
    # Real case, p. 398: 9.7.2, "8.7.3", 9.7.4 in the Shotgun rules.
    rules = [rule("9.7"), rule("9.7.1"), rule("9.7.2"), rule("8.7.3"), rule("9.7.4")]
    findings = check_numbering(doc(rules), [])
    (misprint,) = checks_named(findings, "misnumbered")
    assert misprint.severity == "error"
    assert "probably a misprint of 9.7.3" in misprint.message
    assert "Shotgun Rules (part-9)" in misprint.message
    # No follow-on findings: no missing parent 8.7, no gaps around 8.7.3 / 9.7.4.
    assert [
        f for f in findings if f is not misprint and ("8.7" in f.message or "9.7.3" in f.message)
    ] == []


def test_misprint_in_a_middle_component() -> None:
    # Real case, p. 431: 9.16.4, "9.14.4.1", 9.16.4.2.
    rules = [rule("9.16"), rule("9.16.4"), rule("9.14.4.1"), rule("9.16.4.2")]
    findings = check_numbering(doc(rules), [])
    (misprint,) = checks_named(findings, "misnumbered")
    assert "probably a misprint of 9.16.4.1" in misprint.message
    assert [f for f in findings if "9.14" in f.message or "9.16.4.1" in f.message] == [misprint]


def test_deleted_rule_is_a_gap_not_a_misprint() -> None:
    rules = [rule("9.1"), rule("9.2"), rule("9.4"), rule("9.5"), rule("9.6")]
    findings = check_numbering(doc(rules), [])
    assert [f.message for f in findings] == [
        "in Shotgun Rules (part-9): 9.4 found but 9.3 is missing"
    ]


def test_unexplained_wrong_prefix_and_duplicate() -> None:
    rules = [rule(f"9.{n}") for n in (1, 2, 3, 4, 5)] + [
        rule("7.1.1.1"),  # neighbours give no single-component explanation
        rule("9.6", parse_flags=("duplicate-id",)).model_copy(update={"uid": "x#2"}),
    ]
    findings = check_numbering(doc(rules), [])
    assert len(checks_named(findings, "part-prefix")) == 1
    assert len(checks_named(findings, "duplicate-id")) == 1


def test_parent_equal_to_part_number_is_not_missing() -> None:
    findings = check_numbering(doc([rule("9.1"), rule("9.2.1")]), [])
    assert [f.message for f in checks_named(findings, "missing-parent")] == [
        "in Shotgun Rules (part-9): parent 9.2 of 9.2.1 not found"
    ]


def test_footer_from_another_print_is_an_error() -> None:
    wrong = page(1, [], footer="EDITION 2030 (Second Print 07/2030)  Effective 1 July 2030")
    findings = check_footers(doc([]), [wrong])
    assert [f.severity for f in findings] == ["error"]


def test_unresolved_reference_is_reported() -> None:
    broken = CrossRef(raw="Rule 6.22", target_rule_id="6.22", target_item=None, target_uid=None)
    findings = check_cross_references(doc([rule("9.1", cross_refs=(broken,))]), [])
    assert [(f.severity, f.message) for f in findings] == [
        ("warning", "9.1 cites 'Rule 6.22': no rule 6.22 in part-9 or part-6")
    ]


def test_external_reference_is_only_a_note() -> None:
    wada = CrossRef(
        raw="20.7.10",
        target_rule_id="20.7.10",
        target_item=None,
        target_uid=None,
        document="WADA Code",
        external=True,
    )
    findings = check_cross_references(doc([rule("9.1", cross_refs=(wada,))]), [])
    assert [(f.check, f.severity) for f in findings] == [("external-reference", "info")]


def test_report_counts_and_ordering() -> None:
    pages: list[PageLayout] = [page(1, [line("9.1\t", 85, 100)])]
    report = validate(doc([rule("9.1", "")]), pages)
    assert report.counts["rules"] == 1
    severities = [f.severity for f in report.findings]
    assert severities == sorted(severities, key=["error", "warning", "info"].index)


def test_definition_must_repeat_its_table_cells() -> None:
    table = TableRecord(
        uid="test-book:table:p0001-0",
        rule_uid="test-book:part-9:9.1",
        page=PageRef(pdf_page=1, printed_page="1", bbox=(0, 0, 1, 1)),
        rows=(("DNS", "Did not Start"), ("DSQ", "Disqualified")),
    )

    def definition(term: str, text: str) -> RuleRecord:
        return rule("9.1").model_copy(
            update={
                "uid": f"test-book:part-9:term:{term}",
                "kind": "definition",
                "rule_id": None,
                "heading": term,
                "official_text": text,
                "table_uids": (table.uid,),
            }
        )

    parsed = doc([definition("DNS", "Did not Start"), definition("DSQ", "Disqualifed")])
    parsed = parsed.model_copy(update={"tables": (table,)})
    findings = checks_named(check_coverage(parsed, []), "coverage")
    assert [f.uid for f in findings] == ["test-book:part-9:term:DSQ"]


def test_damaged_table_words_are_found_from_body_vocabulary() -> None:
    vocabulary = {"rifle", "officer", "maximum", "weight", "chief", "range"}
    text = "10m Air Rifel, Chief Range Offci er, Maximumweight, Rifle"
    assert list(damaged_words(text, vocabulary)) == ["Rifel", "Offci er", "Maximumweight"]


def test_every_figure_must_be_linked_to_its_rule_both_ways() -> None:
    def figure(name: str, owner: str) -> FigureRecord:
        return FigureRecord(
            uid=f"test-book:figure:{name}",
            rule_uid=owner,
            page=PageRef(pdf_page=1, printed_page="1", bbox=(0, 0, 1, 1)),
            image_file=None,
            text="",
        )

    linked = rule("9.1", figure_uids=("test-book:figure:p0001-0", "test-book:figure:gone"))
    preamble = rule("9.2").model_copy(
        update={
            "uid": "test-book:part-9:preamble",
            "kind": "preamble",
            "rule_id": None,
            "figure_uids": ("test-book:figure:logo",),
        }
    )
    parsed = doc([linked, preamble]).model_copy(
        update={
            "figures": (
                figure("p0001-0", linked.uid),  # fine
                figure("orphan", "test-book:part-9:9.99"),  # owner does not exist
                figure("unlisted", linked.uid),  # owner does not list it
                figure("logo", preamble.uid),  # not in a numbered rule: a note
            )
        }
    )
    findings = check_figures(parsed, [])
    errors = sorted((f.uid or "").rsplit(":", 1)[-1] for f in findings if f.severity == "error")
    notes = [(f.uid or "").rsplit(":", 1)[-1] for f in findings if f.severity == "info"]
    assert errors == ["9.1", "orphan", "unlisted"]  # 9.1 lists the missing "gone"
    assert notes == ["logo"]
