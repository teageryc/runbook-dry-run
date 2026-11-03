"""Show the Windows parentage of a Git Bash `eval "$X"` -> sleep chain."""

import os
import subprocess
import time

env = {**os.environ, "X": "sleep 8"}
proc = subprocess.Popen(
    ["G:/Apps/Git/bin/bash.exe", "-c", 'eval "$X"'],
    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(1.5)
rows = subprocess.run(
    ["C:/Program Files/PowerShell/7/pwsh.exe", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'bash.exe','sleep.exe' } | "
     "ForEach-Object { '{0} pid={1} ppid={2}' -f $_.Name,$_.ProcessId,$_.ParentProcessId }"],
    capture_output=True, text=True,
).stdout
alive = set()
for line in rows.splitlines():
    print("  ", line)
print("root (launcher) pid:", proc.pid)
proc.wait()
