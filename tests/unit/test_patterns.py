import pytest

from issf_rules.parse.patterns import (
    ends_sentence,
    find_inline_items,
    match_appendix_start,
    match_group_start,
    match_item_start,
    match_rule_start,
    next_label,
    parent_rule_id,
    rule_level,
)


@pytest.mark.parametrize(
    ("text", "rule_id", "printed", "rest"),
    [
        ("6.11.3\tInterruptions", "6.11.3", "6.11.3", "Interruptions"),
        ("6.16.6    Appeals", "6.16.6", "6.16.6", "Appeals"),  # spaces instead of a tab
        ("6.17.5 \tFINALS", "6.17.5", "6.17.5", "FINALS"),  # space before the tab
        ("1\tGENERAL", "1", "1", "GENERAL"),  # annex top level
        ("ARTICLE 2\tVIOLATIONS", "2", "ARTICLE 2", "VIOLATIONS"),
        ("1.9.1.5.\tChairs the meetings", "1.9.1.5", "1.9.1.5.", "Chairs the meetings"),
        ("4.\tELECTION", "4", "4.", "ELECTION"),
    ],
)
def test_rule_start_variants(text: str, rule_id: str, printed: str, rest: str) -> None:
    start = match_rule_start(text)
    assert start is not None
    assert (start.rule_id, start.printed, text[start.rest_offset :].strip()) == (
        rule_id,
        printed,
        rest,
    )
    assert not start.malformed


def test_double_dot_is_normalized_and_flagged() -> None:
    start = match_rule_start("6.11.10..2\tTeam:")
    assert start is not None
    assert (start.rule_id, start.printed, start.malformed) == ("6.11.10.2", "6.11.10..2", True)


@pytest.mark.parametrize(
    "text",
    [
        "1 apple per athlete",  # bare integer without a tab is ordinary text
        "The athlete",
        "6.11.3",  # a number alone is not enough
        "a) item",
    ],
)
def test_not_a_rule_start(text: str) -> None:
    assert match_rule_start(text) is None


def test_item_with_tab_is_marked_tabbed() -> None:
    item = match_item_start("a)\tThe Jury checks")
    assert item is not None
    assert (item.label, item.tabbed) == ("a", True)


def test_item_with_space_is_not_tabbed() -> None:
    # "d) and decisions ..." can be a wrapped line, so only a tab is trusted on its own.
    item = match_item_start("d) and decisions by the RTS Jury")
    assert item is not None
    assert not item.tabbed


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("scored as a miss.", True),
        ("the following:", True),
        ("Range Incident Report; and", False),
        ("must be recorded as a", False),
        ("“HIT.”", True),
    ],
)
def test_ends_sentence(text: str, expected: bool) -> None:
    assert ends_sentence(text) is expected


def test_levels_and_parents() -> None:
    assert rule_level("6.11.3.1") == 4
    assert parent_rule_id("6.11.3.1") == "6.11.3"
    assert parent_rule_id("2") is None


@pytest.mark.parametrize(
    ("text", "label", "marker", "rest", "dotted"),
    [
        ("b). A written protest", "b", "b).", "A written protest", False),
        ("c)It fails to eject", "c", "c)", "It fails to eject", False),  # no space
        ("d)_There is an allowable", "d", "d)_", "There is an allowable", False),
        ("a. Intentional body contact", "a", "a.", "Intentional body contact", True),
    ],
)
def test_printed_item_variants(text: str, label: str, marker: str, rest: str, dotted: bool) -> None:
    item = match_item_start(text)
    assert item is not None
    assert (item.label, item.marker, text[item.rest_offset :], item.dotted) == (
        label,
        marker,
        rest,
        dotted,
    )


@pytest.mark.parametrize("text", ["c)the", "a.b", "e.g. the athlete", "ab"])
def test_not_an_item(text: str) -> None:
    assert match_item_start(text) is None


def test_inline_items_after_semicolon_or_colon() -> None:
    text = "points from his score; and d) If a third violation occurs. See Rules: a) Text"
    found = find_inline_items(text)
    assert [(i.label, i.cued, text[i.rest_offset :][:4]) for i in found] == [
        ("d", True, "If a"),
        ("a", False, "Text"),
    ]


def test_inline_item_needs_a_semicolon_or_colon() -> None:
    assert find_inline_items("as described in a) above") == []


def test_group_start_and_next_label() -> None:
    assert match_group_start("(B) The offences listed below") == "B"
    assert match_group_start("(See drawing)") is None
    assert [next_label(None), next_label("c"), next_label("A.c")] == ["a", "d", "d"]


@pytest.mark.parametrize(
    ("text", "key", "printed"),
    [
        ("APPENDIX 1\tDEFINITIONS", "appendix-1", "APPENDIX 1"),
        ("Appendix 2: Examples", "appendix-2", "Appendix 2:"),
        ("ATTACHMENT B", "attachment-b", "ATTACHMENT B"),
    ],
)
def test_appendix_headings(text: str, key: str, printed: str) -> None:
    start = match_appendix_start(text)
    assert start is not None
    assert (start.key, start.printed) == (key, printed)


@pytest.mark.parametrize("text", ["Appendix of the rules", "APPENDIXES", "Appendix12345"])
def test_not_an_appendix_heading(text: str) -> None:
    assert match_appendix_start(text) is None
