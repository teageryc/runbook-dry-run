"""Command line entry point: `python -m runbook_dry_run <runbook.md>`."""

from __future__ import annotations

import argparse
import contextlib
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


@contextlib.contextmanager
def _printable_output():
    """Escape what the output's encoding cannot hold, instead of crashing, for one call.

    Redirected, Python writes in the locale's encoding (cp1252 on Windows), and a
    report quoting Chinese text crashed with exit 1, which a caller cannot tell from
    "has errors". Only a stream on the default strict handler is changed, so a
    handler the caller chose (PYTHONIOENCODING=ascii:replace, or surrogateescape for
    file names on POSIX) is kept, and the streams are put back when main() returns.
    """
    changed = []
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "errors", None) == "strict" and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
            changed.append(stream)
    try:
        yield
    finally:
        for stream in changed:
            stream.reconfigure(errors="strict")


def main(argv: list[str] | None = None) -> int:
    with _printable_output():
        return _main(argv)


def _main(argv: list[str] | None) -> int:
    args = build_parser().parse_args(argv)

    try:
        with open(args.runbook, encoding="utf-8") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        # A traceback and exit 1 would read like "has errors" to a caller.
        print(
            f"cannot read {args.runbook}: it is not UTF-8 (byte {exc.start}: {exc.reason})",
            file=sys.stderr,
        )
        return 2
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
