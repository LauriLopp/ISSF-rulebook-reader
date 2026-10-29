"""The whole pipeline, through the CLI, on the synthetic rulebook (safe for CI)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from issf_rules.cli import main
from issf_rules.fetch import sha256_of
from issf_rules.jsonl import read_json, read_jsonl
from issf_rules.models.records import RuleRecord, TableRecord
from issf_rules.models.report import ValidationReport
from issf_rules.models.retrieval import RetrievalRecord
from issf_rules.paths import ArtefactPaths

MANIFEST = """
[[source]]
id = "synthetic"
document = "test-book"
title = "Test Rule Book"
edition = "Edition 2030"
print_run = "First Print 01/2030"
effective = "2030-01-01"
url = "https://example.invalid/book.pdf"
filename = "book.pdf"
sha256 = "{sha}"
"""


@pytest.fixture(scope="module")
def run_dir(synthetic_pdf: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("run")
    (root / "data/sources").mkdir(parents=True)
    shutil.copy(synthetic_pdf, root / "data/sources/book.pdf")
    (root / "manifest.toml").write_text(MANIFEST.format(sha=sha256_of(synthetic_pdf)))
    return root


def run(root: Path, *command: str) -> int:
    return main(
        [*command, "--manifest", str(root / "manifest.toml"), "--data-dir", str(root / "data")]
    )


@pytest.fixture(scope="module")
def paths(run_dir: Path) -> ArtefactPaths:
    assert run(run_dir, "run") == 0
    sha = sha256_of(run_dir / "data/sources/book.pdf")
    return ArtefactPaths(data_dir=run_dir / "data", sha256=sha)


@pytest.fixture(scope="module")
def rules(paths: ArtefactPaths) -> dict[str, RuleRecord]:
    return {
        rule.uid.removeprefix("synthetic:"): rule for rule in read_jsonl(paths.rules, RuleRecord)
    }


def test_rules_are_parsed_with_structure(rules: dict[str, RuleRecord]) -> None:
    rule = rules["part-1:1.1.1"]
    assert rule.heading_path == ("Alpha Rules", "1.1 GENERAL", "1.1.1")
    assert [item.label for item in rule.items] == ["a", "b"]
    assert rules["part-1:1.1.2"].heading == "Appeals"


def test_text_continues_across_pages(rules: dict[str, RuleRecord]) -> None:
    rule = rules["part-1:1.1.3"]
    assert rule.official_text.endswith("wide and the athlete must stay inside it.")
    assert [page.pdf_page for page in rule.pages] == [2, 3]


def test_table_is_attached_to_its_rule(paths: ArtefactPaths, rules: dict[str, RuleRecord]) -> None:
    (table,) = read_jsonl(paths.tables, TableRecord)
    assert table.rule_uid == rules["part-1:1.2.1"].uid
    assert table.rows[1] == ("10m", "75 min")


def test_annex_has_own_namespace_and_is_citable(rules: dict[str, RuleRecord]) -> None:
    assert "part-2/annex-X:1.1" in rules
    (ref,) = rules["part-2:2.1.6"].cross_refs
    assert ref.target_uid is not None and ":part-2/annex-X:" in ref.target_uid


def test_cross_reference_into_another_part(rules: dict[str, RuleRecord]) -> None:
    (ref,) = rules["part-1:1.1.2"].cross_refs
    assert ref.target_uid == "synthetic:part-2:2.1.1"


def test_validation_flags_source_problems(paths: ArtefactPaths) -> None:
    report = read_json(paths.report_json, ValidationReport)
    by_check = {(f.check, f.severity) for f in report.findings}
    assert ("part-prefix", "error") in by_check  # 1.3.1 printed inside Part 2
    assert ("numbering-gap", "warning") in by_check  # 2.1.3 missing
    assert not [f for f in report.findings if f.check == "coverage"]
    assert report.counts["assigned_lines"] == report.counts["body_lines"]


def test_retrieval_records_exist_for_rules_with_text(paths: ArtefactPaths) -> None:
    records = read_jsonl(paths.retrieval, RetrievalRecord)
    uids = {r.rule_uid.removeprefix("synthetic:") for r in records}
    assert {"part-1:1.1.1", "part-1:1.2.1", "part-2:2.1.1", "part-2/annex-X:1.1"} <= uids
    assert "part-1:1.1" not in uids  # heading-only section


def test_rerun_is_byte_identical(run_dir: Path, paths: ArtefactPaths) -> None:
    files = sorted(p for p in paths.root.rglob("*") if p.is_file() and p.suffix != ".png")
    before = {p: p.read_bytes() for p in files}
    assert run(run_dir, "run") == 0
    assert {p: p.read_bytes() for p in files} == before


def test_stage_without_its_input_fails_cleanly(tmp_path: Path, synthetic_pdf: Path) -> None:
    (tmp_path / "manifest.toml").write_text(MANIFEST.format(sha=sha256_of(synthetic_pdf)))
    (tmp_path / "data/sources").mkdir(parents=True)
    shutil.copy(synthetic_pdf, tmp_path / "data/sources/book.pdf")
    assert run(tmp_path, "parse") == 1  # extract has not run
