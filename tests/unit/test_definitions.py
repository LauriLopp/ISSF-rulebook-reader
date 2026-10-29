"""Glossaries, recognized by their shape, become one definition record per term."""

import pytest

from issf_rules.models.records import PageRef, RuleRecord, TableRecord
from issf_rules.parse.definitions import (
    Entry,
    paragraph_entries,
    table_definitions,
    table_entries,
)

PAGE = PageRef(pdf_page=183, printed_page="183", bbox=(0, 0, 1, 1))


@pytest.mark.parametrize(
    "header", [("Term", "Definition"), ("Terms", "Definitions"), ("TERM", "Meaning")]
)
def test_term_definition_table(header: tuple[str, str]) -> None:
    rows = (header, ("FOP", "Field of Play."), ("MQS", "Minimum Qualification Score"))
    assert table_entries(rows) == [
        Entry("FOP", "Field of Play.", header[1]),
        Entry("MQS", "Minimum Qualification Score", header[1]),
    ]


def test_event_table_maps_abbreviation_to_event_name() -> None:
    rows = (
        ("EVENTS FOR MEN AND MEN JUNIOR", None, None),
        ("Event Name", "Abbrev.", "Status"),
        ("10m Air Rifle (standing)", "ARM", "M, MJ, Olympic"),
    )
    assert table_entries(rows) == [
        Entry("ARM", "10m Air Rifle (standing)", "EVENTS FOR MEN AND MEN JUNIOR")
    ]
    renamed = (("Event", "Abbreviation"), ("Skeet Men", "SKM"))
    assert table_entries(renamed) == [Entry("SKM", "Skeet Men", None)]


def test_list_of_codes() -> None:
    rows = (("DNF", "Did not Finish"), ("DNS", "Did not Start"), ("DSQ", "Disqualified"))
    assert [e.term for e in table_entries(rows)] == ["DNF", "DNS", "DSQ"]


def test_other_tables_have_no_entries() -> None:
    assert table_entries((("Event", "Time"), ("10m Air Rifle", "75 min"))) == []
    assert table_entries((("DNF", "Did not Finish"), ("DNS", "Did not Start"))) == []  # too few
    assert table_entries((("DNF", "x"), ("DNS", "y"), ("Total", "z"))) == []  # not all codes


GLOSSARY = [
    "Introduction to the definitions.",
    "ADAMS: The administration system.",
    "Athlete: Any Person who competes.",
    "Event: A series of individual Competitions.",
    "Nota bene: For the purpose of these rules, an Event still means a match.",
    "Event Period: The time between the beginning and end of an Event.",
    "International-Level Athlete: Athletes who compete at international level.",
    "International Standard: A standard adopted by WADA.",
    "(a) a numbered continuation paragraph of the standard;",
    "WADA: The World Anti-Doping Agency.",
]


def test_glossary_paragraphs_in_dictionary_order() -> None:
    entries = paragraph_entries(GLOSSARY)
    assert [e.term for e in entries] == [
        "ADAMS",
        "Athlete",
        "Event",  # "Nota bene" is out of order, so it continues "Event"
        "Event Period",
        "International-Level Athlete",  # hyphen sorts like a space
        "International Standard",
        "WADA",
    ]
    event = entries[2]
    assert event.text == (
        "A series of individual Competitions.\n"
        "Nota bene: For the purpose of these rules, an Event still means a match."
    )
    assert (entries[5].first, entries[5].last) == (7, 8)


@pytest.mark.parametrize(
    "paragraphs",
    [
        GLOSSARY[:4],  # too few entries
        ["NOTE: First form.", "NOTE: Second form.", "NOTE: Third.", "NOTE: 4.", "NOTE: 5."],
        ["Zeta: z", "Delta: d", "Beta: b", "Alpha: a", "Gamma: g", "Epsilon: e"],  # unordered
    ],
)
def test_text_with_colons_is_no_glossary(paragraphs: list[str]) -> None:
    assert paragraph_entries(paragraphs) == []


def test_table_definitions_and_repeated_terms() -> None:
    owner = RuleRecord(
        uid="book:part-6:preamble",
        kind="preamble",
        namespace="part-6",
        rule_id=None,
        printed_number=None,
        parent_id=None,
        level=0,
        heading=None,
        heading_path=("General Technical Rules",),
        official_text="Definitions and Abbreviations",
        pages=(PAGE,),
    )
    table = TableRecord(
        uid="book:table:p0183-0",
        rule_uid=owner.uid,
        page=PAGE,
        rows=(("Term", "Definition"), ("FOP", "Field of Play."), ("FOP", "Again.")),
    )
    records = list(table_definitions("book", [owner], [table]))
    assert [r.uid for r in records] == ["book:part-6:term:FOP", "book:part-6:term:FOP#2"]
    first = records[0]
    assert (first.kind, first.heading, first.official_text, first.table_uids) == (
        "definition",
        "FOP",
        "Field of Play.",
        ("book:table:p0183-0",),
    )
    assert first.defined_in == owner.uid
    assert first.heading_path == ("General Technical Rules", "Definition", "FOP")
    assert records[1].parse_flags == ("duplicate-id",)
