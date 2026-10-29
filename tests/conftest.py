from __future__ import annotations

from pathlib import Path

import pytest

from issf_rules.extract import extract_pdf
from issf_rules.models.layout import PageLayout
from synthetic_pdf import build_rulebook

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_PDF = REPO_ROOT / "data/raw/sources/ISSF-Rule-Book-2026-Edition-2025-Third-Print-10-2026.pdf"


@pytest.fixture(scope="session")
def synthetic_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_rulebook(tmp_path_factory.mktemp("synthetic") / "book.pdf")


@pytest.fixture(scope="session")
def synthetic_pages(synthetic_pdf: Path) -> list[PageLayout]:
    return extract_pdf(synthetic_pdf)


@pytest.fixture(scope="session")
def real_pdf() -> Path:
    if not REAL_PDF.exists():
        pytest.skip("real rulebook PDF not present in data/raw/sources (not committed)")
    return REAL_PDF
