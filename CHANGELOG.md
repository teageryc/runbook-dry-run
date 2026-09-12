# Changelog

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-12

### Added

- `runbook_dry_run.checker` — parses a Markdown runbook into steps and reports every step a
  reader could not perform. Seven finding codes, each anchored to a step number.
- `python -m runbook_dry_run <file>` — command line entry point with `--base-dir`,
  `--execute`, `--timeout` and `--json`. Exits `1` when any finding is an error.
- `Run (destructive):` directive — reported, never executed, with or without `--execute`.
- Test suite, twelve cases, standard library only. Every assertion names a finding code
  **and** the step it must land on.
- `.github/workflows/ci.yml` — the suite on Linux and Windows across two Python versions,
  plus a smoke job that asserts a defective runbook exits `1` and that a destructive step
  leaves no trace on disk.
- `docs/specs/2026-09-12-runbook-dry-run-design.md` — the dated design spec, with Non-goals.
- `LIMITS.md` — what the tool cannot tell you, in the first person.

[Unreleased]: https://github.com/teageryc/runbook-dry-run/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/teageryc/runbook-dry-run/releases/tag/v0.1.0
