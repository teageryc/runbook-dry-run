# Runbook: commands written for bash, declared as such

Working directory: `.`
Shell: `Git Bash`

## Step 1 — Prove the commands reach bash and not the platform default
Run: `[[ -n "$BASH_VERSION" ]]`
On failure: the commands ran in some other shell. Open Git Bash and start again.

## Step 2 — Prove quoting survives the trip into the declared shell
Run: `[ "$(printf '%s' "a b")" = "a b" ]`
On failure: the command reached the shell altered. Report it before trusting any other step.

## Step 3 — Leave proof that the commands really ran
Run: `: > shell-bash-marker.tmp`
On failure: the working directory is not writable. Stand in the repository root.
