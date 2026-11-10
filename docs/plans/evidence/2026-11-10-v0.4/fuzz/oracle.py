"""Differential oracle: what CommonMark (markdown-it-py) shows as code, against what the
checker would run.

Adapted on 2026-11-10 from the third code review's oracle (a fresh reviewer's scratch
script). Development only: markdown-it-py is not a dependency of runbook-dry-run.

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/fuzz/oracle.py <file.md>

A line is code when markdown-it puts it inside a fenced or indented code block, or
inside an HTML block of CommonMark types 1-5 (the checker's own start patterns decide
the type, so markdown-it's type-7 reading of a lone "</pre>" line, which the spec
excludes, is not counted). A document is dangerous when a `Run: `echo Ln`` line that
is code would be executed and the checker does not refuse the document.
"""

import os
import re
import sys

# RDR_REPO points the oracle at another tree, for the gate's positive control.
REPO = os.environ.get("RDR_REPO") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 5)
)
sys.path.insert(0, REPO)
from markdown_it import MarkdownIt  # noqa: E402
from runbook_dry_run import checker  # noqa: E402

MD = MarkdownIt("commonmark")
RUN = re.compile(r"^Run: `echo (L\d+)`$")


def code_lines(text):
    """0-based line index -> kind, for every line CommonMark renders as code."""
    lines = checker.LINE_ENDING.split(text)
    kinds = {}
    for token in MD.parse(text):
        if token.map is None:
            continue
        start, end = token.map
        if token.type == "fence":
            for i in range(start + 1, start + 1 + token.content.count("\n")):
                kinds[i] = "fence"
        elif token.type == "code_block":
            for i in range(start, end):
                kinds[i] = "code_block"
        elif token.type == "html_block":
            first = lines[start].expandtabs(4)
            if any(opening.match(first) for opening, _ in checker.HTML_BLOCKS):
                for i in range(start, end):
                    kinds.setdefault(i, "html_block")
    return kinds


# CommonMark 0.31, HTML block type 7: "any tag name other than pre, script, style, or
# textarea". markdown-it-py 4.0.0 reads a lone </pre> line as such a block anyway,
# which moves its fence pairing; on those documents the oracle is not the spec.
SPEC_EXCLUDED_TYPE_7 = re.compile(r"^ {0,3}</(?:pre|script|style|textarea)\s*>\s*$", re.I)


def oracle_deviates(text):
    """Whether markdown-it opens an HTML block where the spec says there is none."""
    lines = checker.LINE_ENDING.split(text)
    for token in MD.parse(text):
        if token.type == "html_block" and token.map is not None:
            if SPEC_EXCLUDED_TYPE_7.match(lines[token.map[0]].expandtabs(4)):
                return True
    return False


def executed_labels(book):
    labels = set()
    for step in book.steps:
        if checker._executes(step):
            for command in step.commands:
                match = re.match(r"^echo (L\d+)$", command)
                if match:
                    labels.add(match.group(1))
    return labels


def analyse(text):
    """(dangerous lines as (label, 1-based line, kind), refused?) for one document."""
    book = checker.parse(text)
    kinds = code_lines(text)
    where = {}
    for i, line in enumerate(checker.LINE_ENDING.split(text)):
        match = RUN.match(line)
        if match:
            where[match.group(1)] = i
    danger = [
        (label, where[label] + 1, kinds[where[label]])
        for label in sorted(executed_labels(book))
        if label in where and where[label] in kinds
    ]
    return danger, refuses(book)


def refuses(book):
    """check()'s own decision; a tree from before _refuses_commands() composed it."""
    if hasattr(checker, "_refuses_commands"):
        return checker._refuses_commands(book)
    return bool(
        book.shell_in_steps
        or checker._misplaces_directory(book)
        or checker._has_unclosed_fence(book)
        or checker._has_misaligned_fence(book)
    )


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8", newline="") as handle:
        document = handle.read()
    danger, refused = analyse(document)
    print("refused:", refused)
    print("executed although CommonMark shows it as code:", danger)
    kinds = code_lines(document)
    for i, line in enumerate(checker.LINE_ENDING.split(document)):
        print(f"{i + 1:3} {kinds.get(i, ''):10} {line!r}")
