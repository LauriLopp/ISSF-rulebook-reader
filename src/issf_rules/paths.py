"""Where the pipeline reads and writes files.

Everything lives under `data/raw/`, which is gitignored: source PDFs and every derived artefact
stay out of version control until licensing is clear (see CLAUDE.md). Derived artefacts are
keyed by the source's sha256, so versions never overwrite each other (ADR 0003). The files are
described in docs/contracts/artefacts.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path("data/raw")


@dataclass(frozen=True)
class ArtefactPaths:
    data_dir: Path
    sha256: str

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def root(self) -> Path:
        return self.data_dir / "derived" / self.sha256

    # extract
    @property
    def layout(self) -> Path:
        return self.root / "layout.jsonl"

    @property
    def figures_dir(self) -> Path:
        return self.root / "figures"

    # parse
    @property
    def source(self) -> Path:
        return self.root / "source.json"

    @property
    def divisions(self) -> Path:
        return self.root / "divisions.jsonl"

    @property
    def rules(self) -> Path:
        return self.root / "rules.jsonl"

    @property
    def tables(self) -> Path:
        return self.root / "tables.jsonl"

    @property
    def figures(self) -> Path:
        return self.root / "figures.jsonl"

    @property
    def coverage(self) -> Path:
        return self.root / "coverage.jsonl"

    # validate
    @property
    def report_json(self) -> Path:
        return self.root / "validation.json"

    @property
    def report_md(self) -> Path:
        return self.root / "validation.md"

    # prepare
    @property
    def retrieval(self) -> Path:
        return self.root / "retrieval.jsonl"

    # review (not a stage)
    @property
    def spotcheck_dir(self) -> Path:
        return self.root / "spotcheck"
