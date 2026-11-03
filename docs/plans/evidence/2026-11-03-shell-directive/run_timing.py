"""Time each phase of checker._run's timeout path."""

import sys
import time

sys.path.insert(0, sys.argv[1])
from runbook_dry_run import checker  # noqa: E402

original_kill = checker._kill_tree


def timed_kill(proc):
    started = time.monotonic()
    original_kill(proc)
    print(f"   _kill_tree took {time.monotonic() - started:.1f}s; poll={proc.poll()}")


checker._kill_tree = timed_kill

for label, command, launcher in [
    ("cmd+python", 'python -c "import time; time.sleep(10)"', checker.Launcher()),
    ("bash sleep", "sleep 10", checker.resolve_shell("bash")[0]),
]:
    started = time.monotonic()
    code, detail = checker._run(command, sys.argv[1], 2, launcher)
    print(f"== {label}: code={code} detail={detail!r} total={time.monotonic() - started:.1f}s")
