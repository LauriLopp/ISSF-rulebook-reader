"""Splitting long rules into search-sized chunks.

Most rules are short (median ~40 words) and become a single chunk. Long ones, mainly finals
procedures, are split at paragraph and item boundaries so each chunk stays within the input
size of small embedding models. Every chunk repeats the heading path, so it still says which
rule it comes from.
"""

from __future__ import annotations

from collections.abc import Sequence

MAX_WORDS = 250
"""About 330 tokens: fits the 512-token limit of the candidate embedding models with room for
the heading path."""


def split_text(blocks: Sequence[str], max_words: int = MAX_WORDS) -> list[str]:
    """Group consecutive blocks into chunks of at most `max_words` words.

    A single block longer than the limit is cut into word windows.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for block in blocks:
        words = block.split()
        if not words:
            continue
        if len(words) > max_words:
            if current:
                chunks.append("\n".join(current))
                current, current_words = [], 0
            chunks.extend(
                " ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)
            )
            continue
        if current and current_words + len(words) > max_words:
            chunks.append("\n".join(current))
            current, current_words = [], 0
        current.append(block)
        current_words += len(words)
    if current:
        chunks.append("\n".join(current))
    return chunks


def table_text(rows: Sequence[Sequence[str | None]]) -> list[str]:
    """Flatten a table to one line per row, cells separated by " | "."""
    return [" | ".join(cell for cell in row if cell) for row in rows if any(cell for cell in row)]
