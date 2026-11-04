#!/bin/sh
# Run runbook-dry-run's suite under WSL Ubuntu the way CI's setup-python does:
# a `python` on PATH. Usage: sh wsl_tests.sh [unittest args...]
set -u
mkdir -p /tmp/rdr-bin
ln -sf /usr/bin/python3 /tmp/rdr-bin/python
PATH="/tmp/rdr-bin:$PATH"
export PATH
export PYTHONDONTWRITEBYTECODE=1
cd /mnt/g/Projects/runbook-dry-run || exit 99
echo "python: $(command -v python) -> $(python --version 2>&1); uname: $(uname -sr)"
if [ "$#" -eq 0 ]; then
    python -m unittest discover -s tests -v
else
    python -m unittest -v "$@"
fi
code=$?
echo "unittest exit=$code"
exit $code
