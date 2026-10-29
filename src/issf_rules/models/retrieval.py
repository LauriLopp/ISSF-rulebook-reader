"""Output of the prepare stage: chunks for lexical and semantic search (ADR 0004)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Discipline = Literal["general", "rifle", "pistol", "shotgun", "moving-target", "target-sprint"]


class RetrievalRecord(BaseModel):
    """One searchable chunk. Long rules are split into several chunks that share `rule_uid`."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    chunk_id: str
    rule_uid: str
    namespace: str
    rule_id: str | None
    heading_path: tuple[str, ...]
    search_text: str
    """Heading path plus the chunk's verbatim text (and flattened table text). Search only:
    display always uses the rule record's official_text."""
    display_ref: str
    disciplines: tuple[Discipline, ...]
    pdf_pages: tuple[int, ...]
