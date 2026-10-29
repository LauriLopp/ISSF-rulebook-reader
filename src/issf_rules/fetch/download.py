"""Downloading source PDFs and verifying that they are byte-identical to the manifest."""

from __future__ import annotations

import hashlib
import urllib.request
from collections.abc import Callable
from pathlib import Path

from issf_rules.models.source import SourceDocument

Downloader = Callable[[str, Path], None]


class ChecksumError(RuntimeError):
    """The file's sha256 differs from the manifest: wrong or changed file."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def http_download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "issf-rules-pipeline"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)


def ensure_source(
    source: SourceDocument, sources_dir: Path, download: Downloader = http_download
) -> Path:
    """Return the local path of `source`, downloading it first if it is not present.

    An existing file is never trusted blindly: its checksum is verified every time. A failed or
    mismatching download leaves no file behind.
    """
    target = sources_dir / source.filename
    if target.exists():
        _verify(target, source)
        return target

    sources_dir.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        download(source.url, partial)
        _verify(partial, source)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(target)
    return target


def _verify(path: Path, source: SourceDocument) -> None:
    actual = sha256_of(path)
    if actual != source.sha256:
        raise ChecksumError(
            f"{path.name}: sha256 {actual} does not match manifest {source.sha256} "
            f"(source {source.id}). If ISSF published a new print, add a new manifest entry."
        )
