"""While communicate()'s reader threads block on a child's pipes, how fast can taskkill start?"""

import os
import subprocess
import time

taskkill = os.path.join(os.environ.get("SystemRoot", "C:/Windows"), "System32", "taskkill.exe")

variants = {
    "capture_output": dict(capture_output=True),
    "devnull": dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    "devnull+no_inherit": dict(
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True
    ),
}

for label, kwargs in variants.items():
    proc = subprocess.Popen(
        'python -c "import time; time.sleep(12)"',
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    started = time.monotonic()
    subprocess.run([taskkill, "/F", "/T", "/PID", str(proc.pid)], **kwargs)
    killed = time.monotonic() - started
    proc.communicate()
    print(f"{label:22s} taskkill {killed:5.1f}s, pipes closed at {time.monotonic() - started:5.1f}s")
