"""F10 probe: which code page do pwsh, powershell and cmd write into a pipe here?"""
import ctypes
import locale
import shutil
import subprocess

k32 = ctypes.windll.kernel32
print("ANSI ACP", k32.GetACP(), "OEMCP", k32.GetOEMCP(), "console out CP", k32.GetConsoleOutputCP())
print("locale.getpreferredencoding", locale.getpreferredencoding(False))

WORD = "Schl" + chr(0xFC) + "ssel " + chr(0x4E2D)  # u-umlaut + one CJK char


def show(label, argv):
    raw = subprocess.run(argv, capture_output=True).stdout
    print(f"--- {label}: raw={raw!r}")
    for enc in ("utf-8", "cp1252", "oem", "mbcs"):
        try:
            print(f"    {enc:7} -> {raw.decode(enc)!r}")
        except Exception as exc:
            print(f"    {enc:7} -> FAIL {type(exc).__name__}")


for exe in ("pwsh", "powershell"):
    found = shutil.which(exe)
    if found:
        show(exe + " Write-Output", [found, "-NoProfile", "-NonInteractive", "-Command", f"Write-Output '{WORD}'"])
        show(exe + " Write-Error(stderr->stdout?)", [found, "-NoProfile", "-NonInteractive", "-Command", f"[Console]::Out.Write('{WORD}')"])
show("cmd echo", "cmd /c echo " + WORD)
