from helpers import line, row
from issf_rules.models.layout import Line
from issf_rules.models.records import Division
from issf_rules.parse.builder import RuleColumns
from issf_rules.parse.rows import PageItem
from issf_rules.parse.sections import split_sections

COLUMNS = RuleColumns(odd=85.0, even=42.5)
ANNEX = Division(
    namespace="part-3/annex-AC",
    kind="annex",
    number="AC",
    title="Athletes Committee",
    first_page=107,
    last_page=110,
)


def rule(page: int, number: str) -> PageItem:
    x = 85.0 if page % 2 else 42.5
    return row(page, line(f"{number}\t", x, 300), line("Text.", x + 56.7, 300))


def title(text: str) -> list[Line]:
    return [line(text, 42.5, 52, size=24, bold=True)]


def test_title_followed_by_restarted_numbering_starts_a_section() -> None:
    items = {107: [rule(107, "1.1")], 108: [rule(108, "1.2")], 110: [rule(110, "1.1")]}
    titles = {110: title("Election Regulations")}
    pieces = split_sections(ANNEX, items, titles, COLUMNS)
    assert [(p.namespace, p.first_page, p.last_page) for p in pieces] == [
        ("part-3/annex-AC", 107, 109),
        ("part-3/annex-AC/p110", 110, 110),
    ]
    assert pieces[1].title == "Election Regulations"
    assert pieces[1].kind == "section"


def test_title_with_continuing_numbering_is_not_a_section() -> None:
    items = {107: [rule(107, "1.1")], 110: [rule(110, "1.2")]}
    titles = {110: title("PROTEST FORM")}
    assert split_sections(ANNEX, items, titles, COLUMNS) == [ANNEX]


def test_title_on_first_page_belongs_to_the_division() -> None:
    items = {107: [rule(107, "1.1")]}
    assert split_sections(ANNEX, items, {107: title("Athletes Committee")}, COLUMNS) == [ANNEX]
