"""A source document as declared in `manifest.toml`."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class SourceDocument(BaseModel):
    """One immutable published file. A new print is a new SourceDocument, never an edit."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    """Short stable identifier, used as the prefix of every record uid."""
    document: str
    title: str
    edition: str
    print_run: str
    effective: dt.date
    url: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
