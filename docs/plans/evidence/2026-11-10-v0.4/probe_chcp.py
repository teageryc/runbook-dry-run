"""C3 probe: what the checker reports after a command runs chcp, and what decoding
the captured bytes after the command exits would report instead.

Windows only. Run from the repository root, once from each shell, because the
console's starting code page depends on the launcher (437 from Git Bash, 65001
from PowerShell on the machine this was written on):

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/probe_chcp.py

The console's page is restored after every case and at the end.
"""

import ctypes
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 4))
sys.path.insert(0, REPO)
from runbook_dry_run.checker import check, parse  # noqa: E402

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetConsoleOutputCP.restype = ctypes.c_uint
kernel32.SetConsoleOutputCP.argtypes = [ctypes.c_uint]

scratch = tempfile.mkdtemp(prefix="probe-chcp-")
batch = os.path.join(scratch, "to65001.bat")
with open(batch, "wb") as handle:
    # UTF-8 bytes on purpose: cmd.exe reads the line after chcp in the new page.
    handle.write(b"@chcp 65001>nul\r\n@echo \xe4\xb8\xad\xe6\x96\x87 1>&2\r\n@exit /b 1\r\n")

start = kernel32.GetConsoleOutputCP()
print(f"start output code page: {start}")

cases = {
    "one line, chcp 65001 then echo CJK": "chcp 65001>nul & echo 中文 1>&2 & exit 1",
    "one line, chcp 437 then echo u-umlaut": "chcp 437>nul & echo Schlüssel 1>&2 & exit 1",
    "batch file, chcp 65001 then echo CJK": f'"{batch}"',
}
for label, command in cases.items():
    kernel32.SetConsoleOutputCP(start)
    text = (
        "# Runbook: probe\n\nWorking directory: `.`\nShell: `cmd`\n\n"
        f"## Step 1 - probe\nRun: `{command}`\nOn failure: stop.\n"
    )
    findings = check(parse(text), base_dir=".", execute=True)
    reported = findings[0].detail.rsplit(": ", 1)[-1] if findings else "<no finding>"
    kernel32.SetConsoleOutputCP(start)
    raw = subprocess.run(command, shell=True, capture_output=True).stderr.strip()
    after = kernel32.GetConsoleOutputCP()
    late = raw.decode(f"cp{after}", errors="replace")
    print(f"{label}:")
    print(f"  bytes cmd.exe wrote: {raw!r}")
    print(f"  reported now (page at start, {start}): {reported!a}")
    print(f"  decoded after exit (page then, {after}): {late!a}")

kernel32.SetConsoleOutputCP(start)
os.remove(batch)
os.rmdir(scratch)
print(f"restored output code page: {kernel32.GetConsoleOutputCP()}")
