"""Reading the source manifest (`manifest.toml`)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from issf_rules.models.source import SourceDocument


class ManifestError(ValueError):
    """The manifest is missing, malformed, or does not contain the requested source."""


def load_manifest(path: Path) -> tuple[SourceDocument, ...]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"manifest is not valid TOML: {exc}") from exc

    entries = data.get("source", [])
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest has no [[source]] entries")
    try:
        sources = tuple(SourceDocument.model_validate(entry) for entry in entries)
    except ValidationError as exc:
        raise ManifestError(f"invalid manifest entry: {exc}") from exc

    ids = [source.id for source in sources]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ManifestError(f"duplicate source ids: {', '.join(duplicates)}")
    return sources


def find_source(sources: tuple[SourceDocument, ...], source_id: str | None) -> SourceDocument:
    """Return the source with `source_id`, or the last entry (the newest) when None."""
    if source_id is None:
        return sources[-1]
    for source in sources:
        if source.id == source_id:
            return source
    known = ", ".join(source.id for source in sources)
    raise ManifestError(f"unknown source id {source_id!r} (known: {known})")
