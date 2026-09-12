# Runbook: a step is gated on a step that does not exist

Working directory: `.`

Elements:
- Releases page

## Step 1 — Verify the push landed
After manual step: 5
Run: `python -c "print('ok')"`
On failure: nothing reached the remote.

## Step 2 — Open the release screen
Open: `Releases page`
On failure: ask for the maintainer role.
