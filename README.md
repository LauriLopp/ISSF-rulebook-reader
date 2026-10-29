# issf-rules

Document-preparation pipeline for the ISSF rulebook assistant. It turns the official ISSF rulebook
PDF into verbatim, structured, validated rule records ready for search.

```
fetch → extract → parse → validate → prepare
```

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run issf-rules run          # downloads the PDF listed in manifest.toml, then all stages
uv run issf-rules spotcheck    # review sheet: PDF pages next to the parsed records (HTML)
uv run pytest
```

Outputs go to `data/raw/derived/<sha256>/`. Start with `validation.md`. The ISSF PDF and
everything derived from it stay in the gitignored `data/raw/` until licensing is clarified.

## Layout

| Path | Content |
|---|---|
| `src/issf_rules/` | One subpackage per stage (`fetch`, `extract`, `parse`, `validate`, `prepare`), plus `models` (record schemas) and `review` (the spot-check sheet) |
| `tests/unit/`, `tests/integration/` | Tests on hand-made layouts and a generated synthetic rulebook; tests against the real PDF are skipped when it is absent |
| `manifest.toml` | Source documents: download URL and sha256 |
