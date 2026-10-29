from helpers import line, page
from issf_rules.models.layout import TableRegion
from issf_rules.parse.rows import Row, TableMark, group_rows, page_items


def test_lines_on_same_baseline_form_one_row_left_to_right() -> None:
    rows = group_rows(3, [line("Heading", 141.7, 100.4), line("6.1\t", 85.0, 100.0)])
    assert len(rows) == 1
    assert rows[0].text == "6.1\tHeading"


def test_rows_are_ordered_top_to_bottom() -> None:
    rows = group_rows(3, [line("second", 141.7, 120), line("first", 141.7, 100)])
    assert [r.text for r in rows] == ["first", "second"]


def test_text_join_adds_space_only_when_needed() -> None:
    rows = group_rows(3, [line("6.16.6", 85.0, 100), line("Appeals", 141.7, 100)])
    assert rows[0].text == "6.16.6 Appeals"


def test_spans_from_offset_follow_joined_text() -> None:
    (r,) = group_rows(3, [line("6.1\t", 85.0, 100), line("GENERAL", 141.7, 100, bold=True)])
    assert [s.text for s in r.spans_from(len("6.1\t"))] == ["GENERAL"]


def test_lines_inside_a_table_belong_to_the_table() -> None:
    table = TableRegion(index=0, bbox=(140.0, 200.0, 500.0, 260.0), rows=(("a", "b"),))
    layout = page(
        3,
        [line("Before the table.", 141.7, 150), line("a", 150, 210), line("b", 320, 210)],
        tables=(table,),
    )
    items = page_items(layout)
    assert isinstance(items[0], Row)
    assert isinstance(items[1], TableMark)
    assert len(items[1].line_indices) == 2
    assert len(items) == 2
