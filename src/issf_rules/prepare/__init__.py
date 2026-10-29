"""Prepare stage: rule records → retrieval records (chunks for lexical and semantic search)."""

from __future__ import annotations

from collections.abc import Iterator

from issf_rules.models.records import ParsedDocument, RuleRecord
from issf_rules.models.retrieval import RetrievalRecord
from issf_rules.prepare.chunking import split_text, table_text
from issf_rules.prepare.disciplines import disciplines_for


def prepare_records(parsed: ParsedDocument) -> Iterator[RetrievalRecord]:
    tables = {table.uid: table for table in parsed.tables}
    figures = {figure.uid: figure for figure in parsed.figures}
    titles = {division.namespace: division.title for division in parsed.divisions}
    for rule in parsed.rules:
        blocks = rule.official_text.split("\n") if rule.official_text else []
        if rule.kind != "definition":  # a definition is one row of its table, not all of it
            for uid in rule.table_uids:
                blocks.extend(table_text(tables[uid].rows))
        blocks.extend(figures[uid].text for uid in rule.figure_uids if figures[uid].text)
        if not any(block.strip() for block in blocks):
            continue  # heading-only section; its children carry the heading in their path

        path = " > ".join(rule.heading_path)
        disciplines = disciplines_for(rule, titles.get(rule.namespace, ""), " ".join(blocks))
        ref = _display_ref(rule, parsed, titles.get(rule.namespace, rule.namespace))
        pdf_pages = tuple(page.pdf_page for page in rule.pages)
        for n, chunk in enumerate(split_text(blocks)):
            yield RetrievalRecord(
                chunk_id=f"{rule.uid}#{n}",
                rule_uid=rule.uid,
                namespace=rule.namespace,
                rule_id=rule.rule_id,
                heading_path=rule.heading_path,
                search_text=f"{path}\n{chunk}",
                display_ref=ref,
                disciplines=disciplines,
                pdf_pages=pdf_pages,
            )


def _display_ref(rule: RuleRecord, parsed: ParsedDocument, division_title: str) -> str:
    pages = sorted({page.printed_page or str(page.pdf_page) for page in rule.pages}, key=_page_key)
    page_text = f"p. {pages[0]}" if len(pages) == 1 else f"pp. {pages[0]}\u2013{pages[-1]}"
    if rule.kind == "definition":
        what = f"{division_title}, definition of \u201c{rule.heading}\u201d"
    elif rule.rule_id is not None:
        what = f"{division_title}, {_number_label(rule)}"
    elif rule.printed_number:  # an appendix
        what = f"{division_title}, {rule.printed_number}"
    else:
        what = f"{division_title}, introduction"
    source = parsed.source
    return f"{what}, {page_text}, {source.title}, {source.edition} ({source.print_run})"


def _number_label(rule: RuleRecord) -> str:
    printed = rule.printed_number or rule.rule_id or ""
    return printed.title() if printed.upper().startswith("ARTICLE") else f"Rule {printed}"


def _page_key(page: str) -> tuple[int, str]:
    return (int(page), page) if page.isdigit() else (10**6, page)
