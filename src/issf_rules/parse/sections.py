"""Sub-documents inside a division that restart the rule numbering.

Some annexes contain a second document under its own large title, e.g. "Election Regulations
for the ISSF Athletes Committee" inside Annex AC, which starts again at rule 1. Its rules need
their own namespace, or their uids would collide with the annex's. Many other large titles
(forms, "FINALS FOR SHOTGUN EVENTS") do *not* restart the numbering; their content simply
continues the current rule, so they are left alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from issf_rules.models.layout import Line
from issf_rules.models.records import Division
from issf_rules.parse.builder import RuleColumns, rule_start_at
from issf_rules.parse.rows import PageItem, Row
from issf_rules.textnorm import join_lines


def split_sections(
    division: Division,
    items_by_page: Mapping[int, Sequence[PageItem]],
    titles_by_page: Mapping[int, Sequence[Line]],
    columns: RuleColumns,
) -> list[Division]:
    """Return `division`, cut at every titled page where the numbering restarts."""
    starts: list[tuple[int, float, str]] = []  # (page, y, rule_id) of every rule start
    for page in range(division.first_page, division.last_page + 1):
        for item in items_by_page.get(page, ()):
            if isinstance(item, Row) and (start := rule_start_at(item, columns)) is not None:
                starts.append((page, item.y0, start.rule_id))

    cut_pages: list[tuple[int, str]] = []
    section_from = (division.first_page, -1.0)
    for page in range(division.first_page + 1, division.last_page + 1):
        titles = titles_by_page.get(page)
        if not titles:
            continue
        title_at = (page, min(line.y0 for line in titles))
        seen = {rid for p, y, rid in starts if section_from <= (p, y) < title_at}
        following = next((rid for p, y, rid in starts if (p, y) > title_at), None)
        if following is not None and following in seen:
            cut_pages.append((page, join_lines(line.text for line in titles)))
            section_from = title_at

    if not cut_pages:
        return [division]
    pieces = [division.model_copy(update={"last_page": cut_pages[0][0] - 1})]
    for i, (page, title) in enumerate(cut_pages):
        end = cut_pages[i + 1][0] - 1 if i + 1 < len(cut_pages) else division.last_page
        pieces.append(
            Division(
                namespace=f"{division.namespace}/p{page}",
                kind="section",
                number=None,
                title=title,
                first_page=page,
                last_page=end,
            )
        )
    return pieces
