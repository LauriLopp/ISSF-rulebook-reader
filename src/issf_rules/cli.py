"""Command-line entry point: `issf-rules <stage>`, `issf-rules run` for all stages, or
`issf-rules spotcheck` for the review sheet."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from issf_rules.fetch import ChecksumError, ManifestError
from issf_rules.parse import ParseError
from issf_rules.parse.contents import ContentsError
from issf_rules.paths import DEFAULT_DATA_DIR
from issf_rules.pipeline import (
    Context,
    MissingArtefactError,
    run_extract,
    run_fetch,
    run_parse,
    run_prepare,
    run_spotcheck,
    run_validate,
)

STAGES = ("fetch", "extract", "parse", "validate", "prepare")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        ctx = Context.load(args.manifest, args.data_dir, args.source)
        if args.command == "spotcheck":
            count = run_spotcheck(ctx, parse_pages(args.pages) if args.pages else None)
            print(f"[spotcheck] {count} pages; open {ctx.paths.spotcheck_dir / 'index.html'}")
            return 0
        stages = STAGES if args.command == "run" else (args.command,)
        for stage in stages:
            _run_stage(stage, ctx, render_figures=not args.no_figures)
    except (ManifestError, ChecksumError, MissingArtefactError, ContentsError, ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _run_stage(stage: str, ctx: Context, render_figures: bool) -> None:
    started = time.monotonic()
    actions: dict[str, Callable[[], str]] = {
        "fetch": lambda: f"source at {run_fetch(ctx)}",
        "extract": lambda: f"{len(run_extract(ctx, render_figures))} pages",
        "parse": lambda: _parse_summary(ctx),
        "validate": lambda: _validate_summary(ctx),
        "prepare": lambda: f"{run_prepare(ctx)} retrieval records",
    }
    summary = actions[stage]()
    print(f"[{stage}] {summary} ({time.monotonic() - started:.1f}s)")


def _parse_summary(ctx: Context) -> str:
    parsed = run_parse(ctx)
    return (
        f"{len(parsed.divisions)} divisions, {len(parsed.rules)} records, "
        f"{len(parsed.tables)} tables, {len(parsed.figures)} figures"
    )


def _validate_summary(ctx: Context) -> str:
    report = run_validate(ctx)
    return (
        f"{report.count('error')} errors, {report.count('warning')} warnings, "
        f"{report.count('info')} notes; see {ctx.paths.report_md}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="issf-rules", description=__doc__)
    parser.add_argument(
        "command",
        choices=(*STAGES, "run", "spotcheck"),
        help="stage to run, 'run' for all, or 'spotcheck' for the review sheet",
    )
    parser.add_argument("--manifest", type=Path, default=Path("manifest.toml"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--source", default=None, help="source id (default: last in manifest)")
    parser.add_argument("--no-figures", action="store_true", help="skip rendering figure images")
    parser.add_argument(
        "--pages", default=None, help="spotcheck only these PDF pages, e.g. '340-345,398'"
    )
    return parser


def parse_pages(spec: str) -> list[int]:
    """'340-342,398' → [340, 341, 342, 398]."""
    pages: list[int] = []
    for part in spec.split(","):
        first, _, last = part.strip().partition("-")
        pages.extend(range(int(first), int(last or first) + 1))
    return pages


if __name__ == "__main__":
    raise SystemExit(main())
