from issf_rules.models.records import Division
from issf_rules.parse.assemble import assemble_division
from issf_rules.parse.builder import Block, Draft

PART6 = Division(
    namespace="part-6",
    kind="part",
    number="6",
    title="General Technical Rules",
    first_page=181,
    last_page=318,
)


def draft(rule_id: str | None, heading: str | None = None, *blocks: Block) -> Draft:
    d = Draft(rule_id=rule_id, printed_number=rule_id)
    if heading:
        d.heading_parts.append(heading)
    d.blocks.extend(blocks)
    d.boxes[246] = [(85.0, 100.0, 500.0, 113.0)]
    return d


def test_records_get_namespaced_uids_and_heading_paths() -> None:
    out = assemble_division(
        "book",
        PART6,
        [
            draft("6.11", "COMPETITION PROCEDURES"),
            draft("6.11.3", "Interruptions"),
            draft("6.11.3.1", None, Block(None, ["If an athlete must stop firing."])),
        ],
        {246: "246"},
    )
    leaf = out.rules[-1]
    assert leaf.uid == "book:part-6:6.11.3.1"
    assert leaf.parent_id == "6.11.3"
    assert leaf.level == 4
    assert leaf.heading_path == (
        "General Technical Rules",
        "6.11 COMPETITION PROCEDURES",
        "6.11.3 Interruptions",
        "6.11.3.1",
    )
    assert leaf.pages[0].printed_page == "246"


def test_items_are_kept_separately_and_inline() -> None:
    out = assemble_division(
        "book",
        PART6,
        [
            draft(
                "6.1.2",
                None,
                Block(None, ["Intro:"]),
                Block("a", ["First;"]),
                Block("b", ["Second."]),
            )
        ],
        {},
    )
    rule = out.rules[0]
    assert rule.official_text == "Intro:\na) First;\nb) Second."
    assert [(i.label, i.text) for i in rule.items] == [("a", "First;"), ("b", "Second.")]


def test_duplicate_numbers_get_unique_uids_and_a_flag() -> None:
    out = assemble_division("book", PART6, [draft("6.1"), draft("6.1")], {})
    assert [r.uid for r in out.rules] == ["book:part-6:6.1", "book:part-6:6.1#2"]
    assert out.rules[1].parse_flags == ("duplicate-id",)


def test_preamble_record() -> None:
    out = assemble_division("book", PART6, [draft(None, None, Block(None, ["Definitions."]))], {})
    rule = out.rules[0]
    assert (rule.uid, rule.kind, rule.level, rule.heading_path) == (
        "book:part-6:preamble",
        "preamble",
        0,
        ("General Technical Rules",),
    )


def test_printed_item_markers_are_kept_in_the_official_text() -> None:
    out = assemble_division(
        "book",
        PART6,
        [
            draft(
                "11.8.2.5",
                None,
                Block(None, ["(A) Red Card:"]),
                Block("A.a", ["Body contact."], "a."),
                Block("b", ["Late."], "b)."),
            )
        ],
        {},
    )
    rule = out.rules[0]
    assert rule.official_text == "(A) Red Card:\na. Body contact.\nb). Late."
    assert [i.label for i in rule.items] == ["A.a", "b"]
