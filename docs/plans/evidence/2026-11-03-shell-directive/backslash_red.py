"""Red check against the CURRENT checker: does a backslash pair before a quote reach bash halved?"""

import sys

sys.path.insert(0, sys.argv[1])
from runbook_dry_run.checker import check, parse  # noqa: E402

for expected_len in (3, 2):
    text = (
        "# Runbook: one step\n\nWorking directory: `.`\nShell: `bash`\n\n"
        "## Step 1 - probe\n"
        f"Run: `x='a\\\\'; [ ${{#x}} -eq {expected_len} ]`\n"
        "On failure: stop.\n"
    )
    command = parse(text).steps[0].commands[0]
    findings = check(parse(text), base_dir=sys.argv[1], execute=True)
    print(f"command={command!r} -> passes={not findings}")
