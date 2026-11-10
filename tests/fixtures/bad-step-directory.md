# Runbook: a working directory declared inside a step

Working directory: `.`

## Step 1 — Change directory too late
Working directory: `tests`
Run: `python -c "open('step-line-marker.tmp', 'w').close()"`
On failure: stop.
