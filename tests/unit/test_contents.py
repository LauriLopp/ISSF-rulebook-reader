import pytest

from helpers import line, page
from issf_rules.models.layout import Line
from issf_rules.parse.contents import ContentsError, contents_blocks, find_divisions


def contents_page() -> list[Line]:
    return [
        line("CONTENTS", 85, 43, size=48, bold=True, block=0),
        line("Summary of Fees    5", 141.7, 116, block=1),
        line("1.\tConstitution    7", 85, 135, block=2),
        line("3.\tGeneral Regulations    35", 85, 175, block=3),
        line("Article 3.13.3.9 Annex “J”: Guidelines for Judges    79", 141.7, 400, block=4),
        line("6.\tGeneral Technical Rules    181", 85, 565, block=5),
    ]


def test_contents_page_entries_are_detected() -> None:
    layout = page(3, contents_page())
    assert contents_blocks(layout) == {1, 2, 3, 4, 5}


def test_ordinary_page_has_no_contents_blocks() -> None:
    layout = page(10, [line("Euro", 85, 100, block=0), line("170.00", 400, 100, block=1)])
    assert contents_blocks(layout) == set()


def test_divisions_cover_the_book_with_annex_namespaces() -> None:
    pages = [page(n, contents_page() if n == 3 else []) for n in range(1, 201)]
    divisions = find_divisions(pages)
    assert [(d.namespace, d.first_page, d.last_page) for d in divisions] == [
        ("front", 1, 6),
        ("part-1", 7, 34),
        ("part-3", 35, 78),
        ("part-3/annex-J", 79, 180),
        ("part-6", 181, 200),
    ]
    annex = divisions[3]
    assert (annex.number, annex.title, annex.reference_number) == (
        "J",
        "Guidelines for Judges",
        "3.13.3.9",
    )


def test_missing_contents_page_is_an_error() -> None:
    with pytest.raises(ContentsError):
        find_divisions([page(1, [line("Some text", 85, 100)])])
