import pytest

from issf_rules.models.records import Division
from issf_rules.parse.crossrefs import FoundRef, documents_in_book, find_references, resolve


def refs(text: str) -> list[tuple[str, str | None]]:
    return [(ref.rule_id, ref.item) for ref in find_references(text)]


def test_reference_with_cue_and_item_letter() -> None:
    assert refs("(see Rule 6.4.11.10.c, maximum bench height is 1.00m)") == [("6.4.11.10", "c")]


def test_list_of_references_after_one_cue() -> None:
    text = "found in Rules 6.17.1.6, 6.17.4.m and 6.17.5.l."
    assert refs(text) == [("6.17.1.6", None), ("6.17.4", "m"), ("6.17.5", "l")]


def test_parenthesized_references_without_cue() -> None:
    assert refs("may be appealed to the Jury of Appeal (6.16.6).") == [("6.16.6", None)]
    assert refs("by the Finals Protest Jury (3.12.3.7, 6.16.6 and 6.17.1.10.d.).") == [
        ("3.12.3.7", None),
        ("6.16.6", None),
        ("6.17.1.10", "d"),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Any shot scoring 10.2 or higher counts as a hit.",
        "between one and a half (1.50) and two (2.00) metres wide",
        "in the Rifle, Pistol and Shotgun Rules (7.0, 8.0 and 9.0)",
        "loading stands of approximately one (1.0) metre",
        "Ring thickness: 0.1mm to 0.2mm.",
    ],
)
def test_numbers_that_are_not_references(text: str) -> None:
    assert refs(text) == []


def test_duplicates_reported_once() -> None:
    assert refs("see Rule 6.2.1 and again Rule 6.2.1") == [("6.2.1", None)]


def test_resolve_prefers_own_namespace_then_part() -> None:
    index = {
        ("part-3/annex-J", "1.4"): "uid-annex-1.4",
        ("part-1", "1.4"): "uid-constitution-1.4",
        ("part-6", "6.16.6"): "uid-6.16.6",
    }
    found = [
        FoundRef(raw="1.4", rule_id="1.4", item=None),
        FoundRef(raw="6.16.6", rule_id="6.16.6", item=None),
        FoundRef(raw="6.22", rule_id="6.22", item=None),
    ]
    resolved = resolve(found, "part-3/annex-J", index)
    assert [r.target_uid for r in resolved] == ["uid-annex-1.4", "uid-6.16.6", None]


CONSTITUTION_IN_PART_1 = {"ISSF Constitution": ("part-1", "1.")}


def test_the_constitution_is_found_by_the_title_of_its_part() -> None:
    def part(number: str, title: str) -> Division:
        return Division(
            namespace=f"part-{number}",
            kind="part",
            number=number,
            title=title,
            first_page=1,
            last_page=1,
        )

    divisions = [part("1", "Rifle Rules"), part("2", "Constitution of the ISSF")]
    assert documents_in_book(divisions) == {"ISSF Constitution": ("part-2", "2.")}
    assert documents_in_book(divisions[:1]) == {}


def test_constitution_is_external_if_the_book_does_not_print_it() -> None:
    (ref,) = find_references("in accordance with Article 14.5 ISSF Constitution, the Council")
    (resolved,) = resolve([ref], "part-3", {})
    assert resolved.external


def test_constitution_citation_in_its_own_numbering() -> None:
    (ref,) = find_references("in accordance with Article 14.5 ISSF Constitution, the Council")
    assert ref.document == "ISSF Constitution"
    (resolved,) = resolve(
        [ref], "part-3/annex-AC", {("part-1", "1.14.5"): "uid-1.14.5"}, CONSTITUTION_IN_PART_1
    )
    assert (resolved.target_rule_id, resolved.target_uid) == ("1.14.5", "uid-1.14.5")


def test_constitution_citation_in_book_numbering_is_not_prefixed_twice() -> None:
    (ref,) = find_references("as set out in Article 1.1.4.1 ISSF Constitution")
    (resolved,) = resolve(
        [ref], "part-3", {("part-1", "1.1.4.1"): "uid-1.1.4.1"}, CONSTITUTION_IN_PART_1
    )
    assert resolved.target_uid == "uid-1.1.4.1"


def test_constitution_range_citation() -> None:
    assert [
        r.document for r in find_references("In accordance with Articles 14.1-3 ISSF Constitution")
    ] == ["ISSF Constitution"]


@pytest.mark.parametrize(
    ("text", "document"),
    [
        ("authority as set out in Article 20.7.10 of the Code.", "WADA Code"),
        (
            "pursuant to Articles 5.8 and 7.0 of the International Standard for TUEs",
            "International Standard",
        ),
    ],
)
def test_external_documents_are_marked_and_not_resolved(text: str, document: str) -> None:
    (ref,) = find_references(text)
    assert ref.document == document
    (resolved,) = resolve([ref], "part-5", {("part-5", ref.rule_id): "would-be-wrong"})
    assert resolved.external
    assert resolved.target_uid is None


def test_plain_reference_has_no_document() -> None:
    (ref,) = find_references("see Rule 6.2.1 for details")
    assert ref.document is None
