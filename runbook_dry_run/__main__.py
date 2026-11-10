"""Command line entry point: `python -m runbook_dry_run <runbook.md>`."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .checker import check, format_report, has_errors, parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runbook-dry-run",
        description="Prove a written procedure is executable before a human follows it.",
    )
    parser.add_argument("runbook", help="path to the runbook markdown file")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="resolve relative paths from here instead of the document's own "
        "'Working directory:' line (use it in CI, where the checkout lives elsewhere)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="actually run each 'Run:' command and read its exit code. "
        "Steps marked 'Run (destructive):' are never executed, with or without this flag",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="seconds any single command may take before it counts as failed (default 60)",
    )
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    return parser


def _never_fail_to_print() -> None:
    """Escape what the output's encoding cannot hold, instead of crashing.

    Redirected, Python writes in the locale's encoding (cp1252 on Windows), and a
    report quoting Chinese text crashed with exit 1, which a caller cannot tell from
    "has errors". The encoding is kept, so output that printed before is unchanged.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    _never_fail_to_print()
    args = build_parser().parse_args(argv)

    try:
        with open(args.runbook, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"cannot read {args.runbook}: {exc}", file=sys.stderr)
        return 2

    findings = check(
        parse(text),
        base_dir=args.base_dir,
        execute=args.execute,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print(format_report(findings, args.runbook))

    return 1 if has_errors(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
