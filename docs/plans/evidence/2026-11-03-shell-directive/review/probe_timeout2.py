import sys, time
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import parse, check
def run(shell_line, cmd):
    doc = f"# Runbook: t\n\nWorking directory: `.`\n{shell_line}\n\n## Step 1 - hang\nRun: `{cmd}`\nOn failure: stop.\n"
    t = time.time()
    f = check(parse(doc), base_dir=".", execute=True, timeout=1)
    print(repr(shell_line), repr(cmd), "elapsed %.1fs" % (time.time() - t), [str(x)[-40:] for x in f])
run("", "set /a x=1 & ping -n 1 127.0.0.1 >nul & set /a y=2")  # trivial
run("", 'python -c "import time; time.sleep(6)"')  # cmd -> grandchild
run("Shell: `Git Bash`", "SECONDS=0; while [ $SECONDS -lt 6 ]; do :; done")  # bash builtin only
run("Shell: `pwsh`", "Start-Sleep 6")  # direct child
