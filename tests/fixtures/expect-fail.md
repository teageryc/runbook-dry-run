# Runbook: a step whose success condition is a command that fails

Working directory: `.`

Elements:
- Releases page

## Step 1 — Prove the interpreter answers
Run: `python -c "print('ok')"`
On failure: your Python is not on PATH.

## Step 2 — Confirm the release tag does not exist yet
Run (expect-fail): `python -c "open('expect-fail-marker.tmp', 'w').close(); import sys; sys.exit(3)"`
On failure: the tag already exists. Read it before publishing anything over it.

## Step 3 — Confirm the remote repository is absent, by its own exit code
Run (expect-fail: 128): `python -c "import sys; sys.exit(128)"`
On failure: exit 0 means the repository exists; any other code means the probe itself failed and tells you nothing about the repository.
