import sys, time
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import parse, check
doc = """# Runbook: t

Working directory: `.`
Shell: `Git Bash`

## Step 1 - hang
Run: `sleep 8`
On failure: stop.
"""
t = time.time()
f = check(parse(doc), base_dir=".", execute=True, timeout=1)
print("elapsed %.1fs" % (time.time() - t))
for x in f: print(x)
