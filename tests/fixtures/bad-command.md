# Runbook: the second step's command exits non-zero

Working directory: `.`

Elements:
- Releases page

## Step 1 — Prove the interpreter answers
Run: `python -c "print('ok')"`
On failure: your Python is not on PATH.

## Step 2 — Check the migration has already been applied
Run: `python -c "import sys; sys.exit(3)"`
On failure: apply the migration, then run this step again.

## Step 3 — Open the release screen
Open: `Releases page`
On failure: ask for the maintainer role.
