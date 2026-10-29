"""Output of the validate stage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["error", "warning", "info"]


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: str
    severity: Severity
    message: str
    pdf_page: int | None = None
    uid: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    counts: dict[str, int]
    """Summary numbers (records, tables, coverage, ...), for quick comparison between runs."""
    findings: tuple[Finding, ...]

    def count(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity == severity)
