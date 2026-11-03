"""Measure pwsh -Command exit codes through the checker's own launcher."""

import sys

sys.path.insert(0, sys.argv[1])
from runbook_dry_run.checker import _run, resolve_shell  # noqa: E402

launcher, problem = resolve_shell("pwsh")
assert launcher is not None, problem
for command in [
    "cmd /c exit 7",
    "cmd /c exit 7; exit $LASTEXITCODE",
    "Get-Item C:/no-such-path-xyz",
    "Get-Item C:/no-such-path-xyz; exit $LASTEXITCODE",
    "cmd /c exit 5; Get-Item C:/no-such-path-xyz; exit $LASTEXITCODE",
    "Get-Item C:/no-such-path-xyz; Write-Output ok",
    "exit 9",
]:
    code, _ = _run(command, sys.argv[1], 60, launcher)
    print(f"{code:>3}  {command}")
