"""Deterministic reading and writing of artefacts.

Outputs must be byte-identical between runs on the same input, so models are serialized with a
fixed field order and files are written atomically (a crash never leaves half a file).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from pydantic import BaseModel


def write_jsonl(path: Path, records: Iterable[BaseModel]) -> int:
    count = 0
    with _atomic(path) as handle:
        for record in records:
            handle.write(record.model_dump_json())
            handle.write("\n")
            count += 1
    return count


def read_jsonl[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    with path.open(encoding="utf-8") as handle:
        return [model.model_validate_json(line) for line in handle if line.strip()]


def write_json(path: Path, record: BaseModel) -> None:
    with _atomic(path) as handle:
        handle.write(record.model_dump_json(indent=1))
        handle.write("\n")


def read_json[M: BaseModel](path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    with _atomic(path) as handle:
        handle.write(text)


@contextmanager
def _atomic(path: Path) -> Iterator[TextIO]:
    """Write to `<path>.tmp`, then rename over `path` only if the block succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            yield handle
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)
