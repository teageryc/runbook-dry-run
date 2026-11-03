import subprocess, sys
sys.path.insert(0, r"G:\Projects\runbook-dry-run")
from runbook_dry_run.checker import resolve_shell, parse, check

BS = chr(92)
DQ = chr(34)
launcher, _ = resolve_shell("Git Bash")
for c in [
    "printf '%s' 'a" + BS + BS + "' | wc -c",
    "echo 'x" + BS + BS + "' | grep -c '" + BS + BS + "'",
]:
    a = subprocess.run([*launcher, c], capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = subprocess.run([launcher[0], "-s"], input=c, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(ascii(c), "argv:", ascii(a.stdout.strip()), a.returncode, ascii(a.stderr.strip()[-70:]), "| stdin:", ascii(s.stdout.strip()), s.returncode)

# end to end through the checker: a step that must pass in a real Git Bash
cmd = "[ " + DQ + "$(printf '%s' 'a" + BS + BS + "' | wc -c)" + DQ + " -eq 3 ]"
doc = "# Runbook: t\n\nWorking directory: `.`\nShell: `Git Bash`\n\n## Step 1 - x\nRun: `" + cmd + "`\nOn failure: stop.\n"
print("checker command:", ascii(parse(doc).steps[0].commands[0]))
s = subprocess.run([launcher[0], "-s"], input=cmd, capture_output=True, text=True)
print("same command typed into Git Bash exits", s.returncode)
print("checker says:", [str(x) for x in check(parse(doc), base_dir=".", execute=True)])

pw = resolve_shell("pwsh")[0]
if pw:
    for c in ["Write-Output 'C:" + BS + "dir" + BS + BS + "'", "Write-Output " + DQ + "a b" + DQ + " 'c " + BS + DQ + " d'"]:
        a = subprocess.run([*pw, c], capture_output=True, text=True)
        print("pwsh", ascii(c), "->", ascii(a.stdout.strip()), a.returncode, ascii(a.stderr.strip()[-80:]))
