import subprocess, sys
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import resolve_shell

launcher, why = resolve_shell("Git Bash")
print("launcher", launcher, why)
BS = chr(92)
DQ = chr(34)
cases = [
    "echo 'a" + BS + DQ + "b'",
    "echo 'C:" + BS + "dir" + BS + "'",
    "echo 'C:" + BS + "dir" + BS + BS + "'",
    "echo " + DQ + "a" + BS + BS + "b" + DQ,
    "echo 'x" + BS + BS + DQ + "y'",
    "echo '*'",
    "echo a'b c'd",
    "echo " + DQ + "{a,b}" + DQ,
    "echo 'it''s'",
    "printf '%s|' 'a b' " + DQ + "c  d" + DQ,
    "echo " + DQ + "$((1+2))" + DQ,
    "echo 'single'" ,
    "echo " + DQ + "C:" + BS + DQ,
]
for c in cases:
    via_argv = subprocess.run([*launcher, c], capture_output=True, text=True, encoding="utf-8", errors="replace")
    via_stdin = subprocess.run([launcher[0], "-s"], input=c, capture_output=True, text=True, encoding="utf-8", errors="replace")
    same = (via_argv.stdout, via_argv.returncode) == (via_stdin.stdout, via_stdin.returncode)
    print("SAME" if same else "DIFF", ascii(c), "| argv:", ascii(via_argv.stdout.strip()), via_argv.returncode, ascii(via_argv.stderr.strip()[-60:]), "| stdin:", ascii(via_stdin.stdout.strip()), via_stdin.returncode)
