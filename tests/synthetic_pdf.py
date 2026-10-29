"""A small, made-up rulebook PDF that mimics the real book's layout.

It reproduces the features the parser relies on (main contents page with an annex, mirrored
margins, rule numbers in their own column, bold headings, lettered items, a ruled table, running
footers) and the quirks it must survive (a non-bold heading, a misprinted rule number, a
numbering gap, text continuing onto the next page). All text is invented, so the file is safe
to generate in tests and CI.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

FOOTER = "EDITION 2030 (First Print 01/2030)    Effective 1 January 2030    © TEST"
ODD = (85.0, 141.7)  # (rule-number column, text column) on odd pages
EVEN = (42.5, 99.2)


def _footer(page: pymupdf.Page, number: int) -> None:
    text = f"{FOOTER}    {number}" if number % 2 else f"{number}    {FOOTER}"
    page.insert_text((60, 805), text, fontsize=9, fontname="helv")


def _rule(page: pymupdf.Page, y: float, number: str, text: str, bold: bool = False) -> None:
    rule_x, text_x = ODD if (page.number + 1) % 2 else EVEN
    page.insert_text((rule_x, y), number, fontsize=11.8, fontname="helv")
    page.insert_text((text_x, y), text, fontsize=11.8, fontname="hebo" if bold else "helv")


def _text(page: pymupdf.Page, y: float, text: str, bold: bool = False) -> None:
    text_x = ODD[1] if (page.number + 1) % 2 else EVEN[1]
    page.insert_text((text_x, y), text, fontsize=11.8, fontname="hebo" if bold else "helv")


def build_rulebook(path: Path) -> Path:
    doc = pymupdf.open()

    # p1: main contents
    p = doc.new_page()
    p.insert_text((85, 80), "CONTENTS", fontsize=48, fontname="hebo")
    for i, entry in enumerate(
        (
            "1.    Alpha Rules    2",
            "2.    Beta Rules    4",
            'Article 2.9 Annex "X": Extra Annex    5',
        )
    ):
        p.insert_text((85, 160 + 40 * i), entry, fontsize=11.8, fontname="hebo")
    _footer(p, 1)

    # p2 (even): Part 1 starts
    p = doc.new_page()
    _rule(p, 60, "1.1", "GENERAL", bold=True)
    _rule(p, 90, "1.1.1", "Athletes must report to the range on time.")
    _text(p, 120, "a)  The Jury checks the equipment;", bold=False)
    _text(p, 150, "b)  The Range Officer records the time.")
    _rule(p, 180, "1.1.2", "Appeals")
    _text(p, 210, "An appeal must be filed in writing, see Rule 2.1.1.")
    _rule(p, 240, "1.1.3", "Each firing point should be about (1.50) metres wide and the")
    _footer(p, 2)

    # p3 (odd): continuation, then a table
    p = doc.new_page()
    _text(p, 60, "athlete must stay inside it.")
    _rule(p, 90, "1.2", "TABLES", bold=True)
    _rule(p, 120, "1.2.1", "The following times apply:")
    x0, x1, x2 = 141.7, 300.0, 500.0
    for r, (left, right) in enumerate((("Event", "Time"), ("10m", "75 min"), ("50m", "90 min"))):
        y0 = 140 + 22 * r
        p.draw_rect(pymupdf.Rect(x0, y0, x1, y0 + 22), width=0.8)
        p.draw_rect(pymupdf.Rect(x1, y0, x2, y0 + 22), width=0.8)
        p.insert_text((x0 + 4, y0 + 15), left, fontsize=10, fontname="helv")
        p.insert_text((x1 + 4, y0 + 15), right, fontsize=10, fontname="helv")
    _footer(p, 3)

    # p4 (even): Part 2 with a misprint (1.3.1 inside Part 2) and a gap (2.1.3 missing)
    p = doc.new_page()
    _rule(p, 60, "2.1", "SCORING", bold=True)
    _rule(p, 90, "2.1.1", "Shots are scored by the electronic targets.")
    _rule(p, 120, "1.3.1", "This number is misprinted in the source.")
    _rule(p, 150, "2.1.4", "Ties are broken by the last series (Rule 2.1.1).")
    _rule(p, 180, "2.1.5", "Results are published after the Jury approves them.")
    _rule(p, 210, "2.1.6", "Protests follow the annex procedure (see Article 2.9).")
    _footer(p, 4)

    # p5 (odd): annex with its own numbering
    p = doc.new_page()
    _rule(p, 60, "1.1", "Annex rules restart their numbering.")
    _rule(p, 90, "1.2", "Second annex rule.")
    _footer(p, 5)

    doc.save(path)
    doc.close()
    return path
