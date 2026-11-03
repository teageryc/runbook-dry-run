# Runbook: a shell this tool does not know

Working directory: `.`
Shell: `fish`

## Step 1 — A command that must never run under an unresolved shell
Run: `python -c "open('shell-unknown-marker.tmp', 'w').close()"`
On failure: stop.
