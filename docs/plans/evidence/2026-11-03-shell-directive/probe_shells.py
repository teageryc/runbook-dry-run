"""Probe the exact invocation the v0.3 plan will specify, before writing it down."""

import os
import shutil
import subprocess
import sys

REPO = sys.argv[1]

git = shutil.which("git")
print("git:", git)
exec_path = subprocess.run([git, "--exec-path"], capture_output=True, text=True).stdout.strip()
print("exec-path:", exec_path)

directory = os.path.normpath(exec_path)
bash = None
for level in range(4):
    candidate = os.path.join(directory, "bin", "bash.exe")
    print(f"  level {level}: {candidate} exists={os.path.isfile(candidate)}")
    if bash is None and os.path.isfile(candidate):
        bash = candidate
    directory = os.path.dirname(directory)
print("resolved bash:", bash)
print("which('bash') from this Python:", shutil.which("bash"))


def run(argv, label):
    proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, timeout=60)
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
    print(f"{label}: exit={proc.returncode} tail={tail[-1] if tail else ''!r}")
    return proc.returncode


run([bash, "-c", '[ -n "$BASH_VERSION" ]'], "bash BASH_VERSION")
run([bash, "-c", "[ \"$(printf '%s' \"a b\")\" = \"a b\" ]"], "bash quoting round-trip")
run([bash, "-c", "[ \"$(printf '%s' \"a b\")\" = \"a  b\" ]"], "bash quoting NEGATIVE control (must be 1)")
run([bash, "-c", "cd /g/Projects/runbook-dry-run && git log --oneline -1"], "bash cd /g + git")
run([bash, "-c", "python -c \"print('ok')\""], "bash python on PATH")
run([bash, "-c", ": > probe-marker.tmp"], "bash marker in cwd")
print("  marker landed in REPO:", os.path.isfile(os.path.join(REPO, "probe-marker.tmp")))
if os.path.isfile(os.path.join(REPO, "probe-marker.tmp")):
    os.remove(os.path.join(REPO, "probe-marker.tmp"))
run([bash, "-c", "exit 7"], "bash exit 7")

pwsh = shutil.which("pwsh")
print("pwsh:", pwsh)
ps = [pwsh, "-NoProfile", "-NonInteractive", "-Command"]
run(ps + ["if ($PSVersionTable -and (\"a b\" -eq 'a b')) { exit 7 }"], "pwsh quoting + exit 7")
run(ps + ["if ($PSVersionTable -and (\"a b\" -eq 'a  b')) { exit 7 }"], "pwsh NEGATIVE control (must be 0)")

proc = subprocess.run('[ -n "$BASH_VERSION" ]', shell=True, cwd=REPO, capture_output=True, text=True)
print("undeclared (cmd) BASH_VERSION control: exit", proc.returncode)
proc = subprocess.run("if ($PSVersionTable) { exit 7 }", shell=True, cwd=REPO, capture_output=True, text=True)
print("undeclared (cmd) pwsh-only command: exit", proc.returncode)
