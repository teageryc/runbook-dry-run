#!/bin/sh
# Replay the `smoke` job of .github/workflows/ci.yml under WSL Ubuntu, step by
# step, with the same commands and the same pass conditions. Prints one line per
# step and exits non-zero if any step fails, so a zero means every step passed.
set -u
mkdir -p /tmp/rdr-bin
ln -sf /usr/bin/python3 /tmp/rdr-bin/python
PATH="/tmp/rdr-bin:$PATH"
export PATH
export PYTHONDONTWRITEBYTECODE=1
cd /mnt/g/Projects/runbook-dry-run || exit 99
rm -f destructive-marker.tmp expect-fail-marker.tmp manual-gate-marker.tmp shell-bash-marker.tmp shell-unknown-marker.tmp
failed=0
step() { echo "[$1] $2"; [ "$1" = PASS ] || failed=$((failed + 1)); }

python -m runbook_dry_run tests/fixtures/good.md --base-dir . --execute
[ $? -eq 0 ] && step PASS "a followable runbook exits 0" || step FAIL "a followable runbook exits 0"

python -m runbook_dry_run tests/fixtures/bad-path.md --base-dir .
code=$?; [ $code -eq 1 ] && step PASS "an unfollowable runbook exits 1" || step FAIL "an unfollowable runbook exits 1 (got $code)"

python -m runbook_dry_run tests/fixtures/destructive.md --base-dir . --execute
[ ! -f destructive-marker.tmp ] && step PASS "a destructive step leaves no trace" || step FAIL "a destructive step leaves no trace"

python -m runbook_dry_run tests/fixtures/expect-fail.md --base-dir . --execute
[ -f expect-fail-marker.tmp ] && step PASS "an expected failure ran and left its marker" || step FAIL "an expected failure ran and left its marker"
rm -f expect-fail-marker.tmp

python -m runbook_dry_run tests/fixtures/manual-gate.md --base-dir . --execute
[ ! -f manual-gate-marker.tmp ] && step PASS "a gated step is reported, not executed" || step FAIL "a gated step is reported, not executed"

python -m runbook_dry_run tests/fixtures/bad-manual-gate.md --base-dir .
code=$?; [ $code -eq 1 ] && step PASS "a gate naming a missing step exits 1" || step FAIL "a gate naming a missing step exits 1 (got $code)"

python -m runbook_dry_run tests/fixtures/shell-bash.md --base-dir . --execute
[ -f shell-bash-marker.tmp ] && step PASS "a declared shell ran the commands" || step FAIL "a declared shell ran the commands"
rm -f shell-bash-marker.tmp

python -m runbook_dry_run tests/fixtures/shell-unknown.md --base-dir . --execute
code=$?
if [ $code -eq 1 ] && [ ! -f shell-unknown-marker.tmp ]; then step PASS "an unresolved shell exits 1 and runs nothing"; else step FAIL "an unresolved shell exits 1 and runs nothing (got $code)"; fi

echo "smoke steps failed=$failed"
exit $failed
