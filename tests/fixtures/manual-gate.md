# Runbook: a step that cannot run until a human has finished an earlier one

Working directory: `.`

Elements:
- New repository page
- Create repository

## Step 1 — Create the repository in the browser
Open: `New repository page`
Click: `Create repository`
On failure: you are signed in as the wrong account. Sign out and start this step again.

## Step 2 — Verify the push landed, against the remote rather than the local pointer
After manual step: 1
Run: `python -c "open('manual-gate-marker.tmp', 'w').close(); import sys; sys.exit(9)"`
On failure: nothing reached the remote. Re-read step 1's output before repeating it.
