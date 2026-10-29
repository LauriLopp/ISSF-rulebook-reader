from helpers import SOURCE
from issf_rules.models.records import Division, PageRef, ParsedDocument, RuleRecord, TableRecord
from issf_rules.prepare import prepare_records
from issf_rules.prepare.chunking import split_text, table_text
from issf_rules.prepare.disciplines import disciplines_for, part_discipline


def record(namespace: str, text: str, **extra: object) -> RuleRecord:
    return RuleRecord(
        uid=f"b:{namespace}:6.2.1",
        kind="rule",
        namespace=namespace,
        rule_id="6.2.1",
        printed_number="6.2.1",
        parent_id="6.2",
        level=3,
        heading=None,
        heading_path=("General Technical Rules", "6.2 SAFETY", "6.2.1"),
        official_text=text,
        pages=(PageRef(pdf_page=191, printed_page="191", bbox=(0, 0, 1, 1)),),
        **extra,  # type: ignore[arg-type]
    )


def test_short_text_is_one_chunk() -> None:
    assert split_text(["one two", "three"], max_words=10) == ["one two\nthree"]


def test_blocks_are_grouped_up_to_the_limit() -> None:
    assert split_text(["a b c", "d e", "f g h"], max_words=5) == ["a b c\nd e", "f g h"]


def test_oversized_block_is_cut_into_windows() -> None:
    assert split_text(["w1 w2 w3 w4 w5"], max_words=2) == ["w1 w2", "w3 w4", "w5"]


def test_table_rows_are_flattened() -> None:
    assert table_text([("Event", "Time"), (None, None), ("10m", None)]) == ["Event | Time", "10m"]


def test_discipline_from_part_and_from_mentions() -> None:
    assert disciplines_for(record("part-8", "Anything"), "Pistol Rule") == ("pistol",)
    assert disciplines_for(record("part-12", "Rifle ranges"), "Moving Target Rules") == (
        "moving-target",
    )
    assert disciplines_for(record("part-6", "Rifle and pistol ranges")) == ("rifle", "pistol")
    assert disciplines_for(record("part-6", "Applies to Trap and Skeet")) == ("shotgun",)
    assert disciplines_for(record("part-6", "Safety first.")) == ("general",)


def test_part_discipline_comes_from_the_title() -> None:
    assert [
        part_discipline(title)
        for title in (
            "Rifle Rules",
            "Shotgun Rules",
            "Target Sprint Rules",
            "General Technical Rules for all Shooting Disciplines",
            "Rifle and Pistol Rules",
            "Rifle Training Manual",
        )
    ] == ["rifle", "shotgun", "target-sprint", None, None, None]


def test_retrieval_records_carry_text_tables_and_citation() -> None:
    table = TableRecord(
        uid="b:table:p0191-0",
        rule_uid="b:part-6:6.2.1",
        page=PageRef(pdf_page=191, printed_page="191", bbox=(0, 0, 1, 1)),
        rows=(("Event", "Time"),),
    )
    parsed = ParsedDocument(
        source=SOURCE,
        divisions=(
            Division(
                namespace="part-6",
                kind="part",
                number="6",
                title="General Technical Rules",
                first_page=181,
                last_page=318,
            ),
        ),
        rules=(
            record("part-6", "Guns must be unloaded.", table_uids=(table.uid,)),
            record("part-6", "").model_copy(update={"uid": "b:part-6:6.2"}),  # heading only
        ),
        tables=(table,),
        figures=(),
        assignments=(),
    )
    (chunk,) = prepare_records(parsed)
    assert chunk.chunk_id == "b:part-6:6.2.1#0"
    assert chunk.search_text == (
        "General Technical Rules > 6.2 SAFETY > 6.2.1\nGuns must be unloaded.\nEvent | Time"
    )
    assert chunk.display_ref == (
        "General Technical Rules, Rule 6.2.1, p. 191, Test Rule Book, Edition 2030 "
        "(First Print 01/2030)"
    )
