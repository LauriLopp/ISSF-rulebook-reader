import hashlib
from pathlib import Path

import pytest

from helpers import SOURCE
from issf_rules.fetch import ChecksumError, ManifestError, ensure_source, find_source, load_manifest

CONTENT = b"%PDF-1.4 test"
SHA = hashlib.sha256(CONTENT).hexdigest()
SRC = SOURCE.model_copy(update={"sha256": SHA})


def fake_download(content: bytes):  # type: ignore[no-untyped-def]
    calls: list[str] = []

    def download(url: str, target: Path) -> None:
        calls.append(url)
        target.write_bytes(content)

    download.calls = calls  # type: ignore[attr-defined]
    return download


def test_downloads_and_verifies(tmp_path: Path) -> None:
    download = fake_download(CONTENT)
    path = ensure_source(SRC, tmp_path, download)
    assert path.read_bytes() == CONTENT
    assert download.calls == [SRC.url]


def test_existing_file_is_verified_not_downloaded(tmp_path: Path) -> None:
    (tmp_path / SRC.filename).write_bytes(CONTENT)
    download = fake_download(b"never used")
    ensure_source(SRC, tmp_path, download)
    assert download.calls == []


def test_wrong_download_leaves_nothing_behind(tmp_path: Path) -> None:
    with pytest.raises(ChecksumError):
        ensure_source(SRC, tmp_path, fake_download(b"a different print"))
    assert list(tmp_path.iterdir()) == []


def test_changed_local_file_is_rejected(tmp_path: Path) -> None:
    (tmp_path / SRC.filename).write_bytes(b"tampered")
    with pytest.raises(ChecksumError):
        ensure_source(SRC, tmp_path, fake_download(CONTENT))


MANIFEST = """
[[source]]
id = "{id}"
document = "issf-rulebook"
title = "Book"
edition = "Edition 2025"
print_run = "Third Print 10/2026"
effective = "2026-10-19"
url = "https://example.invalid/a.pdf"
filename = "a.pdf"
sha256 = "{sha}"
"""


def test_manifest_round_trip_and_lookup(tmp_path: Path) -> None:
    path = tmp_path / "manifest.toml"
    path.write_text(MANIFEST.format(id="one", sha=SHA) + MANIFEST.format(id="two", sha=SHA))
    sources = load_manifest(path)
    assert [s.id for s in sources] == ["one", "two"]
    assert find_source(sources, None).id == "two"  # default: newest (last) entry
    assert find_source(sources, "one").effective.isoformat() == "2026-10-19"
    with pytest.raises(ManifestError, match="unknown source id"):
        find_source(sources, "three")


@pytest.mark.parametrize(
    "content",
    [
        "",  # no entries
        MANIFEST.format(id="Bad Id", sha=SHA),
        MANIFEST.format(id="one", sha="not-a-hash"),
        MANIFEST.format(id="one", sha=SHA) * 2,  # duplicate id
        "this is = not [ toml",
    ],
)
def test_invalid_manifests(tmp_path: Path, content: str) -> None:
    path = tmp_path / "manifest.toml"
    path.write_text(content)
    with pytest.raises(ManifestError):
        load_manifest(path)
