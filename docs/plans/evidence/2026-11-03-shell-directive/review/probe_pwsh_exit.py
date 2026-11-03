import subprocess, sys
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import resolve_shell

pw, why = resolve_shell("pwsh")
print("pwsh launcher:", pw, why)
for c in [
    "cmd /c exit 7",
    "cmd /c exit 7; exit $LASTEXITCODE",
    "Get-Item C:/definitely-not-here-xyz",
    "Get-Item C:/definitely-not-here-xyz; exit $LASTEXITCODE",
    "cmd /c exit 5; Get-Item C:/definitely-not-here-xyz; exit $LASTEXITCODE",
]:
    r = subprocess.run([*pw, c], capture_output=True, text=True, errors="replace")
    print(repr(c), "->", r.returncode)
