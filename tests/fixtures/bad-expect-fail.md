# Runbook: a step expects its command to fail and the command succeeds

Working directory: `.`

Elements:
- Releases page

## Step 1 — Prove the interpreter answers
Run: `python -c "print('ok')"`
On failure: your Python is not on PATH.

## Step 2 — Confirm the target repository does not already exist
Run (expect-fail): `python -c "print('the repository answered')"`
On failure: the repository already exists. Stop and read it before pushing into it.

## Step 3 — Open the release screen
Open: `Releases page`
On failure: ask for the maintainer role.
