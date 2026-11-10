# Runbook: an example inside fenced code must never run

Working directory: `.`

## Step 1 — Show the command, then run the real one
The command looks like this:

```
Run: `python -c "open('fenced-marker.tmp', 'w').close()"`
```

Run: `python -c "open('unfenced-marker.tmp', 'w').close()"`
On failure: your Python is not on PATH.
