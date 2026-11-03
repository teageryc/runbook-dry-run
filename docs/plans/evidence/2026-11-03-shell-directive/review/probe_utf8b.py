import sys
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import parse, check

BS = chr(92)
# printf with octal escapes: E4 B8 81 = U+4E01, written to stderr, then exit 3
cmd = "printf '" + BS + "344" + BS + "270" + BS + "201" + BS + "n' >&2; exit 3"
doc = (
    "# Runbook: t\n\nWorking directory: `.`\nShell: `Git Bash`\n\n"
    "## Step 1 - out\nRun: `" + cmd + "`\nOn failure: stop.\n"
)
print("command:", ascii(parse(doc).steps[0].commands))
try:
    f = check(parse(doc), base_dir=".", execute=True, timeout=10)
    print("RESULT", [ascii(str(x)) for x in f])
except Exception as e:
    print("CRASH", type(e).__name__, str(e)[:160])
