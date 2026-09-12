# Runbook: the second step does not say what to do when it fails

Working directory: `.`

Elements:
- Releases page

## Step 1 — Confirm the license is in place
Path: `LICENSE`
On failure: stop and add a license before anything else.

## Step 2 — Tag the release
Run: `python -c "print('tagged')"`

## Step 3 — Open the release screen
Open: `Releases page`
On failure: ask for the maintainer role.
