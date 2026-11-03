"""Kill a process tree with Toolhelp32 + TerminateProcess: no new process is created."""

import ctypes
import subprocess
import time
from ctypes import wintypes

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def descendants(root: int) -> list[int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []
    children: dict[int, list[int]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            children.setdefault(entry.th32ParentProcessID, []).append(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    found, queue = [], [root]
    while queue:
        for child in children.get(queue.pop(), []):
            if child not in found and child != root:
                found.append(child)
                queue.append(child)
    return found


def terminate(pid: int) -> None:
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if handle:
        kernel32.TerminateProcess(handle, 1)
        kernel32.CloseHandle(handle)


for label, args, shell in [
    ("cmd+python", 'python -c "import time; time.sleep(12)"', True),
    ("gitbash sleep", ["G:/Apps/Git/bin/bash.exe", "-c", 'eval "$X"'], False),
]:
    import os
    env = {**os.environ, "X": "sleep 12"}
    proc = subprocess.Popen(args, shell=shell, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(timeout=1.5)
    except subprocess.TimeoutExpired:
        pass
    started = time.monotonic()
    tree = descendants(proc.pid)
    for pid in [proc.pid, *tree]:
        terminate(pid)
    killed = time.monotonic() - started
    proc.communicate()
    print(f"{label:14s} killed {len(tree) + 1} processes in {killed:.2f}s; pipes closed at {time.monotonic() - started:.2f}s")
