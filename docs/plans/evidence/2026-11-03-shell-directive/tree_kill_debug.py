"""Why does taskkill /T not stop the command tree? Print what it says and what survives."""

import os
import subprocess
import time

system_root = os.environ.get("SystemRoot", "C:/Windows")
taskkill = os.path.join(system_root, "System32", "taskkill.exe")
print("SystemRoot:", os.environ.get("SystemRoot"), "| taskkill exists:", os.path.isfile(taskkill))

for label, args, shell in [
    ("cmd+python", 'python -c "import time; time.sleep(12)"', True),
    ("gitbash sleep", ["G:/Apps/Git/bin/bash.exe", "-c", "sleep 12"], False),
]:
    proc = subprocess.Popen(args, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2)
    tree = subprocess.run(
        ["C:/Program Files/PowerShell/7/pwsh.exe", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process | ForEach-Object { '{0},{1},{2}' -f $_.ProcessId,$_.ParentProcessId,$_.Name }"],
        capture_output=True, text=True,
    ).stdout
    children = {}
    for row in tree.splitlines():
        parts = row.split(",", 2)
        if len(parts) == 3:
            pid, ppid, name = parts
            children.setdefault(ppid.strip(), []).append((pid.strip(), name.strip()))

    def walk(pid, depth=0):
        for child_pid, name in children.get(str(pid), []):
            print("   " + "  " * depth + f"{name} pid={child_pid}")
            walk(child_pid, depth + 1)

    print(f"== {label}: root pid={proc.pid}")
    walk(proc.pid)
    result = subprocess.run([taskkill, "/F", "/T", "/PID", str(proc.pid)], capture_output=True, text=True)
    print(f"   taskkill exit={result.returncode} out={result.stdout.strip()!r} err={result.stderr.strip()!r}")
    started = time.monotonic()
    try:
        proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        print("   communicate still blocked after 15s")
    print(f"   pipes closed after {time.monotonic() - started:.1f}s")
