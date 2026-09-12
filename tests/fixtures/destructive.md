# Runbook: a step whose side effect must never happen during a dry run

Working directory: `.`

Elements:
- Releases page

## Step 1 — Prove the interpreter answers
Run: `python -c "print('ok')"`
On failure: your Python is not on PATH.

## Step 2 — Write the release marker into the live directory
Run (destructive): `python -c "open('destructive-marker.tmp', 'w').close()"`
On failure: the directory is read-only; ask the owner to grant write access, then repeat.

## Step 3 — Open the release screen
Open: `Releases page`
On failure: ask for the maintainer role.
