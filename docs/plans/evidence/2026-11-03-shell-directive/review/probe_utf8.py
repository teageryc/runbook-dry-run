import sys
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import parse, check
def run(shell_line, cmd):
    doc = f"# Runbook: t\n\nWorking directory: `.`\n{shell_line}\n\n## Step 1 - out\nRun: `{cmd}`\nOn failure: stop.\n"
    try:
        f = check(parse(doc), base_dir=".", execute=True, timeout=10)
        print(repr(shell_line), "OK", [str(x) for x in f])
    except Exception as e:
        print(repr(shell_line), "CRASH", type(e).__name__, str(e)[:120])
run("Shell: `Git Bash`", "printf '\xe4\xb8\x81\n'")
run("Shell: `Git Bash`", "echo \u4e01")
run("", "echo \u4e01")
