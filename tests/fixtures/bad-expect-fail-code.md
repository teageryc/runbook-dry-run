# Runbook: a step expects exit 128 and the command exits 1

Working directory: `.`

Elements:
- Releases page

## Step 1 — Prove the interpreter answers
Run: `python -c "print('ok')"`
On failure: your Python is not on PATH.

## Step 2 — Confirm the remote is absent rather than merely unreachable
Run (expect-fail: 128): `python -c "import sys; sys.exit(1)"`
On failure: a code other than 128 means the probe failed for its own reasons and cannot tell you whether the repository exists.

## Step 3 — Open the release screen
Open: `Releases page`
On failure: ask for the maintainer role.
