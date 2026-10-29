"""Individual validation checks. Each takes the parsed document and the page layouts."""

from collections.abc import Callable, Sequence

from issf_rules.models.layout import PageLayout
from issf_rules.models.records import ParsedDocument
from issf_rules.models.report import Finding
from issf_rules.validate.checks.coverage import check_coverage
from issf_rules.validate.checks.crossrefs import check_cross_references
from issf_rules.validate.checks.figures import check_figures
from issf_rules.validate.checks.numbering import check_numbering
from issf_rules.validate.checks.pages import check_footers, check_low_text
from issf_rules.validate.checks.tables import check_table_text, check_tables

Check = Callable[[ParsedDocument, Sequence[PageLayout]], list[Finding]]

ALL_CHECKS: tuple[Check, ...] = (
    check_coverage,
    check_footers,
    check_low_text,
    check_numbering,
    check_tables,
    check_table_text,
    check_cross_references,
    check_figures,
)
