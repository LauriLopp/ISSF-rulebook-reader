from pathlib import Path

import pytest

from helpers import line
from issf_rules.jsonl import read_jsonl, write_jsonl
from issf_rules.models.layout import Line


def test_round_trip_is_exact(tmp_path: Path) -> None:
    lines = [line("6.1\t", 85.0, 57.8, index=0), line("GENERAL", 141.7, 57.8, bold=True, index=1)]
    path = tmp_path / "lines.jsonl"
    assert write_jsonl(path, lines) == 2
    assert read_jsonl(path, Line) == lines


def test_output_is_byte_identical_across_writes(tmp_path: Path) -> None:
    lines = [line("text", 1.0, 2.0, index=0)]
    write_jsonl(tmp_path / "a.jsonl", lines)
    write_jsonl(tmp_path / "b.jsonl", lines)
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_failed_write_keeps_previous_file(tmp_path: Path) -> None:
    path = tmp_path / "lines.jsonl"
    write_jsonl(path, [line("old", 1.0, 2.0, index=0)])

    def broken() -> object:
        yield line("new", 1.0, 2.0, index=0)
        raise RuntimeError("stage crashed")

    with pytest.raises(RuntimeError):
        write_jsonl(path, broken())  # type: ignore[arg-type]
    assert [ln.text for ln in read_jsonl(path, Line)] == ["old"]
    assert not path.with_name("lines.jsonl.tmp").exists()
