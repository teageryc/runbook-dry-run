"""Start suspended, assign to a Job Object, resume; on timeout TerminateJobObject."""

import ctypes
import os
import subprocess
import time
from ctypes import wintypes

CREATE_SUSPENDED = 0x00000004
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

for label, args, shell in [
    ("cmd+python", 'python -c "import time; time.sleep(12)"', True),
    ("gitbash eval sleep", ["G:/Apps/Git/bin/bash.exe", "-c", 'eval "$X"'], False),
    ("gitbash pipeline", ["G:/Apps/Git/bin/bash.exe", "-c", 'eval "$X"'], False),
]:
    env = {**os.environ, "X": "sleep 12" if "pipeline" not in label else "sleep 12 | cat"}
    job = kernel32.CreateJobObjectW(None, None)
    proc = subprocess.Popen(
        args, shell=shell, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=CREATE_SUSPENDED,
    )
    assigned = kernel32.AssignProcessToJobObject(job, int(proc._handle))
    ntdll.NtResumeProcess(int(proc._handle))
    try:
        proc.communicate(timeout=1.5)
    except subprocess.TimeoutExpired:
        pass
    started = time.monotonic()
    kernel32.TerminateJobObject(job, 1)
    proc.communicate()
    kernel32.CloseHandle(job)
    print(f"{label:20s} assigned={bool(assigned)} pipes closed {time.monotonic() - started:.2f}s after TerminateJobObject; rc={proc.returncode}")

# The control: a command that finishes normally must still report its own exit code.
job = kernel32.CreateJobObjectW(None, None)
proc = subprocess.Popen(["G:/Apps/Git/bin/bash.exe", "-c", "exit 7"], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, creationflags=CREATE_SUSPENDED)
kernel32.AssignProcessToJobObject(job, int(proc._handle))
ntdll.NtResumeProcess(int(proc._handle))
proc.communicate(timeout=10)
kernel32.CloseHandle(job)
print("control exit 7 ->", proc.returncode)
