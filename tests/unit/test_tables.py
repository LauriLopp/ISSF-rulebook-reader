"""Cell text is rebuilt from the page's own lines, not from the table finder's text."""

from helpers import line
from issf_rules.extract.tables import cell_text


def test_cell_text_joins_the_lines_inside_the_cell() -> None:
    lines = [
        line("Maximum", 100, 50, index=0),
        line("weight", 100, 63, index=1),
        line("Trigger", 200, 50, index=2),  # next cell
        line("Men/", 100, 76, index=3),
        line("Women", 100, 89, index=4),
    ]
    assert cell_text(lines, (95, 45, 190, 100)) == "Maximum weight Men/Women"
    assert cell_text(lines, (195, 45, 290, 100)) == "Trigger"


def test_empty_cell_is_none() -> None:
    assert cell_text([line("Text", 100, 50)], (300, 300, 400, 400)) is None
