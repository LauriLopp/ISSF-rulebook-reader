"""Checks against the real ISSF rulebook (Edition 2025, Third Print 10/2026).

The PDF is not committed (licensing), so these tests skip unless it is in data/raw/sources.
The expected facts below were verified by hand against the printed pages.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from issf_rules.extract import extract_pdf
from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument, RuleRecord
from issf_rules.models.report import ValidationReport
from issf_rules.models.source import SourceDocument
from issf_rules.parse import parse_document
from issf_rules.validate import validate

pytestmark = pytest.mark.real_pdf


@pytest.fixture(scope="module")
def source() -> SourceDocument:
    from issf_rules.fetch import find_source, load_manifest

    return find_source(load_manifest(Path("manifest.toml")), "issf-rulebook-2025-p3")


@pytest.fixture(scope="module")
def pages(real_pdf: Path) -> list[PageLayout]:
    return extract_pdf(real_pdf)  # ~1 minute


@pytest.fixture(scope="module")
def parsed(source: SourceDocument, pages: list[PageLayout]) -> ParsedDocument:
    return parse_document(source, pages)


@pytest.fixture(scope="module")
def report(parsed: ParsedDocument, pages: list[PageLayout]) -> ValidationReport:
    return validate(parsed, pages)


def get(parsed: ParsedDocument, key: str) -> RuleRecord:
    uid = f"{parsed.source.id}:{key}"
    return next(rule for rule in parsed.rules if rule.uid == uid)


def test_every_line_is_used_exactly_once_and_text_is_intact(report: ValidationReport) -> None:
    assert report.counts["assigned_lines"] == report.counts["body_lines"]
    assert [f for f in report.findings if f.check == "coverage"] == []


def test_uids_are_unique(parsed: ParsedDocument) -> None:
    uids = [rule.uid for rule in parsed.rules]
    assert len(uids) == len(set(uids))


def test_divisions_include_annexes_and_restarted_sections(parsed: ParsedDocument) -> None:
    namespaces = {d.namespace for d in parsed.divisions}
    assert {"part-6", "part-9", "part-3/annex-J", "part-3/annex-AC/p110"} <= namespaces


def test_known_rules(parsed: ParsedDocument) -> None:
    assert get(parsed, "part-6:6.16.6").heading == "Appeals"  # heading not in bold
    assert get(parsed, "part-5:2").printed_number == "ARTICLE 2"
    assert get(parsed, "part-6:6.11.10.2").printed_number == "6.11.10..2"
    finals = get(parsed, "part-6:6.17.5")
    assert len(finals.table_uids) == 3  # including the borderless continuation on p. 284
    assert get(parsed, "part-8:8.7.2").figure_uids  # the READY position drawing


def test_source_misprints_are_reported_once(report: ValidationReport) -> None:
    misprints = {
        (f.pdf_page, f.message.rsplit(" ", 1)[-1])
        for f in report.findings
        if f.check == "misnumbered"
    }
    assert misprints == {(398, "9.7.3"), (431, "9.16.4.1")}  # "8.7.3" and "9.14.4.1" in print
    follow_on = [
        f
        for f in report.findings
        if f.check in ("missing-parent", "numbering-gap", "part-prefix")
        and f.pdf_page in (398, 431)
    ]
    assert follow_on == []


def test_only_genuinely_broken_references_are_warnings(report: ValidationReport) -> None:
    """Each of these was checked against the PDF: the cited rule is printed nowhere."""
    broken = {
        (f.pdf_page, f.message.split("'")[1])
        for f in report.findings
        if f.check == "cross-reference"
    }
    assert broken == {
        (262, "3.12.3.6"),  # annexes are numbered 3.13.3.x now
        (268, "3.12.3.7"),
        (390, "8.3.1 d)"),  # cited from the Shotgun rules; Pistol 8.3 has no 8.3.1
        (415, "6.18.4.7"),  # printed only in this citation; 6.18.4 ends at 6.18.4.4
        (502, "6.22"),  # the dress code is 6.20; there is no 6.22
        (502, "6.22.6.3"),
    }


def test_constitution_citations_resolve(parsed: ParsedDocument) -> None:
    refs = [
        ref
        for rule in parsed.rules
        for ref in rule.cross_refs
        if ref.document == "ISSF Constitution"
    ]
    assert refs and all(ref.target_uid for ref in refs)
    assert any(ref.target_rule_id == "1.14.5" for ref in refs)  # "Article 14.5 ISSF Constitution"


def test_items_in_unusual_printed_forms(parsed: ParsedDocument) -> None:
    """Each of these was checked against the PDF (see docs/tasks/003-parser-fixes.md)."""
    expected = {
        "part-6:6.13.2.2": "abcdef",  # "...trigger; or e) The malfunction" on one line
        "part-8:8.7.4": "abcd",
        "part-9:9.8.4.3": "abc",  # "...these Rules: a) A NO TARGET"
        "part-9:9.8.4.5": "abcde",  # "d)_There" and "...; or e)"
        "part-9:9.13.2.4": "abcd",
        "part-6:6.4.3.3": "abcdefgh",  # "a).", "c).", "g)."
        "part-9:9.16.3": "abc",  # "b)."
        "part-6:6.4.6.3": "abc",  # "c)The" without a space
        "part-6:6.4.16.1": "abcd",
        "part-9:9.9.5.4": "abcd",
        "part-9:9.11.4.1": "abcd",
        "part-11:11.10.2.2": "abcdef",  # "a." style
        "part-11:11.10.4.1": "abcdef",
    }
    for key, letters in expected.items():
        assert "".join(item.label for item in get(parsed, key).items) == letters, key
    groups = [item.label for item in get(parsed, "part-11:11.8.2.5").items]
    assert groups == [f"A.{c}" for c in "abcdefghi"] + [f"B.{c}" for c in "abcd"]


def test_definitions_and_abbreviations(parsed: ParsedDocument) -> None:
    definitions = {r.heading: r for r in parsed.rules if r.kind == "definition"}
    assert definitions["FOP"].official_text.startswith("Field of Play.")
    assert definitions["FOP"].uid == "issf-rulebook-2025-p3:part-6:term:FOP"
    assert definitions["ARM"].official_text == "10m Air Rifle (standing)"
    assert definitions["DNS"].official_text == "Did not Start"
    assert definitions["DNS"].parent_id == "6.14.4.2"
    sources = Counter(r.defined_in for r in parsed.rules if r.kind == "definition")
    prefix = "issf-rulebook-2025-p3:"
    assert sources == {
        prefix + "part-6:preamble": 70,  # definitions table + event tables
        prefix + "part-6:6.14.4.2": 19,  # results-list codes
        prefix + "part-5:appendix-1": 81,  # anti-doping glossary
    }


def test_anti_doping_appendix_is_its_own_record(parsed: ParsedDocument) -> None:
    last_rule = get(parsed, "part-5:24.7.6")
    assert [p.pdf_page for p in last_rule.pages] == [172]
    appendix = get(parsed, "part-5:appendix-1")
    assert (appendix.printed_number, appendix.heading) == ("APPENDIX 1", "DEFINITIONS")
    adams = get(parsed, "part-5:term:ADAMS")
    assert adams.official_text.startswith("The Anti-Doping Administration and Management System")
    assert [p.pdf_page for p in adams.pages] == [172, 173]
    event = get(parsed, "part-5:term:Event")  # "Nota bene: ..." is part of it, not a term
    assert "Nota bene:" in event.official_text


def test_table_text_is_not_damaged(parsed: ParsedDocument, report: ValidationReport) -> None:
    cells = " ".join(cell for t in parsed.tables for row in t.rows for cell in row if cell)
    for artefact in ("Rifel", "Offci", "Defni", "Qualifci", "fri e", "Maximumweight"):
        assert artefact not in cells
    spec = next(t for t in parsed.tables if t.uid.endswith("p0343-0"))  # rule 7.7.5
    assert spec.rows[0][:2] == ("Event", "Maximum weight")
    assert spec.rows[1][:2] == ("10m Air Rifle", "5.5kg (Men/Women)")
    # Real words that only occur in tables; reviewed by hand. More hits mean a regression.
    noted = {f.pdf_page for f in report.findings if f.check == "table-text"}
    assert noted == {49, 57, 124, 183, 253, 254, 255, 256, 281, 330, 458}


def test_every_figure_is_linked_to_a_rule(report: ValidationReport) -> None:
    """Broken links are errors and fail here with the figures named; figures outside numbered
    rules are notes, and here they are exactly the two logos (checked against the PDF)."""
    links = [f for f in report.findings if f.check == "figure-link"]
    assert [f.message for f in links if f.severity == "error"] == []
    assert {f.uid for f in links if f.severity == "info"} == {
        "issf-rulebook-2025-p3:figure:p0001-0",  # ISSF logo on the cover
        "issf-rulebook-2025-p3:figure:p0483-0",  # Target Sprint logo on its title page
    }


def test_parse_is_deterministic(source: SourceDocument, pages: list[PageLayout]) -> None:
    first = parse_document(source, pages)
    second = parse_document(source, pages)
    assert first.model_dump_json() == second.model_dump_json()
