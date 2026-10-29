"""The draft-building state machine, fed with hand-made rows (odd page: numbers at x=85)."""

from helpers import line, row
from issf_rules.parse.builder import DivisionBuilder, Draft, RuleColumns
from issf_rules.parse.rows import PageItem

COLUMNS = RuleColumns(odd=85.0, even=42.5)
NUM, TEXT = 85.0, 141.7
STEP, GAP = 13.0, 19.5  # line step within a paragraph, and between paragraphs


def build(items: list[PageItem]) -> list[Draft]:
    builder = DivisionBuilder(COLUMNS)
    builder.feed(items)
    return builder.finish()


def rule_row(page: int, y: float, number: str, text: str, bold: bool = False) -> PageItem:
    return row(page, line(number + "\t", NUM, y), line(text, TEXT, y, bold=bold))


def test_bold_text_after_number_is_heading() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "6.11.4", "Late Arrival By Athlete", bold=True),
            row(3, line("If an athlete arrives late, he may participate.", TEXT, 100 + GAP)),
        ]
    )
    assert draft.rule_id == "6.11.4"
    assert draft.heading == "Late Arrival By Athlete"
    assert [b.text for b in draft.blocks] == ["If an athlete arrives late, he may participate."]


def test_multi_line_bold_heading() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "6.11.3", "Interruptions in 10m Events and 300m Rifle", bold=True),
            row(3, line("Events", TEXT, 100 + STEP, bold=True)),
        ]
    )
    assert draft.heading == "Interruptions in 10m Events and 300m Rifle Events"
    assert draft.blocks == []


def test_short_plain_text_followed_by_paragraph_is_heading() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "6.16.6", "Appeals"),
            row(
                3, line("If there is a disagreement, the matter may be appealed.", TEXT, 100 + GAP)
            ),
        ]
    )
    assert draft.heading == "Appeals"
    assert "heading-not-bold" in draft.flags


def test_short_plain_text_followed_by_next_rule_is_content() -> None:
    drafts = build(
        [rule_row(3, 100, "1.4.1", "Rifle shooting (1)"), rule_row(3, 100 + GAP, "1.4.2", "Pistol")]
    )
    assert drafts[0].heading is None
    assert drafts[0].blocks[0].text == "Rifle shooting (1)"


def test_items_and_continuation_lines() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "6.11.3.2", "If an athlete is interrupted:"),
            row(3, line("a)\tRange Officers must record a complete", TEXT, 100 + GAP)),
            row(3, line("explanation; and", TEXT, 100 + GAP + STEP)),
            row(3, line("b)\tAny extension must be documented.", TEXT, 100 + 2 * GAP + STEP)),
        ]
    )
    assert [(b.label, b.text) for b in draft.blocks] == [
        (None, "If an athlete is interrupted:"),
        ("a", "Range Officers must record a complete explanation; and"),
        ("b", "Any extension must be documented."),
    ]


def test_wrapped_line_starting_with_letter_paren_is_not_an_item() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "6.16.6", "Decisions by a Finals Protest Jury (6.17.1.10"),
            row(3, line("d) and decisions by the RTS Jury are final.", TEXT, 100 + STEP)),
        ]
    )
    assert len(draft.blocks) == 1
    assert draft.blocks[0].label is None
    assert draft.blocks[0].text.endswith("(6.17.1.10 d) and decisions by the RTS Jury are final.")


def test_unfinished_sentence_continues_on_next_page() -> None:
    (draft,) = build(
        [
            rule_row(3, 700, "6.11.2.4", "If the athlete is aware, a Range Officer must"),
            row(4, line("then supervise the unloading of the gun.", 99.2, 60)),
        ]
    )
    assert [b.text for b in draft.blocks] == [
        "If the athlete is aware, a Range Officer must then supervise the unloading of the gun."
    ]


def test_finished_sentence_ends_paragraph_at_page_break() -> None:
    (draft,) = build(
        [
            rule_row(3, 700, "6.11.5", "Extra shots must be annulled."),
            row(4, line("The athlete must also be penalized.", 99.2, 60)),
        ]
    )
    assert len(draft.blocks) == 2


def test_number_outside_rule_column_is_text() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "6.3.1", "Targets are scored as follows:"),
            row(3, line("10.2 or higher counts as a hit.", TEXT, 100 + STEP)),
        ]
    )
    assert draft.rule_id == "6.3.1"
    assert draft.blocks[0].text.endswith("10.2 or higher counts as a hit.")


def test_text_before_first_rule_becomes_preamble() -> None:
    drafts = build(
        [
            row(3, line("Introduction to these rules.", NUM, 80)),
            rule_row(3, 100, "6.1", "GENERAL", bold=True),
        ]
    )
    assert [d.rule_id for d in drafts] == [None, "6.1"]
    assert drafts[0].blocks[0].text == "Introduction to these rules."


def test_every_row_line_is_recorded_for_coverage() -> None:
    (draft,) = build([rule_row(3, 100, "6.1.1", "Text.")])
    assert len(draft.line_refs) == 2


def item_row(page: int, y: float, text: str) -> PageItem:
    return row(page, line(text, TEXT, y))


def labels(draft: Draft) -> list[str | None]:
    return [b.label for b in draft.blocks]


def test_item_starting_mid_line_after_and_is_split_out() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "8.7.4", "Ready Position Violations", bold=True),
            item_row(3, 100 + GAP, "a) The athlete must be warned;"),
            item_row(3, 100 + 2 * GAP, "b) The series is repeated; and d) If a third"),
            item_row(3, 100 + 2 * GAP + STEP, "violation occurs, he is disqualified."),
        ]
    )
    # b) is followed by d), not c): the letters do not run in sequence, so nothing is split.
    assert labels(draft) == ["a", "b"]

    (draft,) = build(
        [
            rule_row(3, 100, "8.7.4", "Ready Position Violations", bold=True),
            item_row(3, 100 + GAP, "c) The fault is repeated; and d) If a third"),
            item_row(3, 100 + GAP + STEP, "violation occurs, he is disqualified."),
        ]
    )
    assert labels(draft) == ["c", "d"]
    assert draft.blocks[0].text == "The fault is repeated; and"
    assert draft.blocks[1].text == "If a third violation occurs, he is disqualified."


def test_first_item_after_colon_needs_the_next_item_to_confirm_it() -> None:
    (confirmed,) = build(
        [
            rule_row(3, 100, "9.8.4.3", "No Target", bold=True),
            item_row(3, 100 + GAP, "A NO TARGET is one not thrown: a) A decision is the"),
            item_row(3, 100 + GAP + STEP, "Referee's;"),
            item_row(3, 100 + 2 * GAP + STEP, "b) It is declared when the target breaks."),
        ]
    )
    assert labels(confirmed) == [None, "a", "b"]
    (unconfirmed,) = build(
        [
            rule_row(3, 100, "6.1.1", "Scope", bold=True),
            item_row(3, 100 + GAP, "As explained in the note: a) applies to all events."),
        ]
    )
    assert labels(unconfirmed) == [None]


def test_dotted_items_only_in_sequence_and_grouped() -> None:
    (draft,) = build(
        [
            rule_row(3, 100, "11.8.2.5", "Penalties", bold=True),
            item_row(3, 100 + GAP, "(A) These lead to a Red Card:"),
            item_row(3, 100 + 2 * GAP, "a. Body contact is prohibited."),
            item_row(3, 100 + 3 * GAP, "b. Starting early."),
            item_row(3, 100 + 4 * GAP, "e. g. this is prose, not item e."),
            item_row(3, 100 + 5 * GAP, "(B) These lead to a Blue Card:"),
            item_row(3, 100 + 6 * GAP, "a. Discarding a magazine."),
        ]
    )
    assert labels(draft) == [None, "A.a", "A.b", None, None, "B.a"]
    assert draft.blocks[1].marker == "a."


def test_bold_appendix_heading_in_the_number_column_ends_the_rule() -> None:
    drafts = build(
        [
            rule_row(3, 100, "24.7.6", "Changes to the Prohibited List."),
            row(
                3,
                line("APPENDIX 1\t", NUM, 100 + GAP, bold=True),
                line("DEFINITIONS", 170, 100 + GAP, bold=True),
            ),
            row(3, line("ADAMS: The administration system.", NUM, 100 + 2 * GAP)),
        ]
    )
    rule, appendix = drafts
    assert [b.text for b in rule.blocks] == ["Changes to the Prohibited List."]
    assert (appendix.rule_id, appendix.key, appendix.printed_number, appendix.heading) == (
        None,
        "appendix-1",
        "APPENDIX 1",
        "DEFINITIONS",
    )
    assert [b.text for b in appendix.blocks] == ["ADAMS: The administration system."]


def test_appendix_word_in_plain_text_is_not_a_heading() -> None:
    drafts = build(
        [
            rule_row(3, 100, "24.7.6", "See the definitions."),
            row(3, line("Appendix 1 lists the definitions.", NUM, 100 + GAP)),
        ]
    )
    assert len(drafts) == 1
