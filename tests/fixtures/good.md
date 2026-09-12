# Runbook: publish the checker

Working directory: `.`

Elements:
- Releases page
- Draft a new release

## Step 1 — Confirm the license is in place
Path: `LICENSE`
On failure: stop. A repository with no license is not publishable; add one and start again.

## Step 2 — Confirm the tests exist before trusting them
Path: `tests/test_checker.py`
On failure: stop and tell the author. A suite you cannot find is a suite that never ran.

## Step 3 — Prove the interpreter answers
Run: `python -c "print('ok')"`
On failure: your Python is not on PATH. Fix that before any later step, which all assume it.

## Step 4 — Open the release screen
Open: `Releases page`
Click: `Draft a new release`
On failure: you are not a maintainer on this repository. Ask for the role; do not work around it.
