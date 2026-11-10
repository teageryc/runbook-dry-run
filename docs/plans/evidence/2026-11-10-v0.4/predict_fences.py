"""C1 prediction: apply the planned CommonMark fence rule to documents and list every
line the parser reads today that the rule would skip, and any fence left open.

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/predict_fences.py <file>...

A document with no such line keeps exactly its current report under C1.
"""

import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 4))
sys.path.insert(0, REPO)
from runbook_dry_run.checker import (  # noqa: E402
    DIRECTIVE,
    ELEMENTS_HEADING,
    SHELL_LINE,
    STEP_HEADING,
    WORKING_DIRECTORY,
)

OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})$")
SHAPES = (STEP_HEADING, DIRECTIVE, WORKING_DIRECTORY, SHELL_LINE, ELEMENTS_HEADING)

for path in sys.argv[1:]:
    fence, opened, fences, shaped = None, 0, 0, []
    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle.read().splitlines(), start=1):
            line = raw.rstrip()
            if fence:
                close = CLOSE.match(line)
                if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= len(fence):
                    fence = None
                elif any(shape.match(line) for shape in SHAPES):
                    shaped.append((number, line))
                continue
            opening = OPEN.match(line)
            if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(2)):
                fence, opened, fences = opening.group(1), number, fences + 1
    print(
        f"{os.path.basename(path)}: {fences} fences; unclosed at line "
        f"{opened if fence else '-'}; {len(shaped)} fenced lines the parser reads today"
    )
    for number, line in shaped:
        print(f"  {number}: {line[:100]}")
