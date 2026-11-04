"""F12 control: with _executes() always True, the existing suite must go red."""
import os
import sys
import unittest

repo = sys.argv[1]
sys.path.insert(0, repo)
os.chdir(repo)
import runbook_dry_run.checker as checker  # noqa: E402

checker._executes = lambda step: True
suite = unittest.defaultTestLoader.discover(os.path.join(repo, "tests"))
result = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
names = sorted({t.id().rsplit(".", 1)[-1] for t, _ in result.failures + result.errors})
print(f"ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}")
for name in names:
    print("  red:", name)
sys.exit(0 if names else 1)
