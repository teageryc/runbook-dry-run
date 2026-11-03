# Changelog

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-03

Built after the second real use, never during it. Re-checking the publishing
procedure at v0.2 produced three `COMMAND_FAILED` findings that were not defects:
the document declared Git Bash in its header, and the format could not say so.

### Added

- `Shell: <name>` - document-level; `bash` (alias `Git Bash`), `pwsh`, `powershell`
  or `cmd`, case-insensitive. Under `--execute` every command runs in that shell.
- `SHELL_UNRESOLVED` (error, step 0) - an unknown name, or a shell this machine does
  not have. No command in the document is then executed, with or without
  `--execute`. Falling back to the platform default was rejected: it is the
  behaviour that produced the three false findings.
- On Windows, Git Bash is found by walking up from `git --exec-path` to
  `bin\bash.exe`, never through `PATH`: on the machine this was built on,
  `shutil.which("bash")` answers with the WSL launcher in `WindowsApps`.
- Fifteen test cases, thirty-five in total, some platform-specific and skipped
  elsewhere. The declared-bash fixture must leave its marker; an unresolved shell
  must leave none. Its bash probe is `[[ ]]`, because a runner launched from Git
  Bash puts coreutils' `[.exe` on `PATH`, where `cmd.exe` finds it and a
  single-bracket probe passes in the wrong shell.

### Changed

- The spec gains section 8 and the `Shell:` line in sections 3 and 4; section 7's
  "not built" carries a dated correction.
- `LIMITS.md` records four limits of the directive, and its quoting paragraph now
  names the declared shell.
- `.github/workflows/ci.yml` smokes the directive both ways: a declared shell must
  leave its marker, an unresolved one must exit `1` and leave none.

### Fixed

- `runbook_dry_run.__version__` read `0.1.0` through the 0.2.0 release; it now
  matches this changelog.

## [0.2.0] - 2026-09-12

Both entries below come from this tool's first real use, which was checking the
procedure that publishes this tool. Neither finding was about that procedure; both
were about the runbook format. The gaps were recorded at the time and fixed
afterwards, never during - patching a tool mid-first-use destroys the evidence that
the first use found anything.

### Added

- `Run (expect-fail):` and `Run (expect-fail: <code>):` - a step whose success
  condition is a command that FAILS. Previously such a step had to delete its command
  and move the real check into `On failure:` prose, which made the most consequential
  step in a procedure the only one the tool could not check. Naming the exact code is
  the stronger form: `git ls-remote` exits `128` for an absent repository and also
  exits non-zero when the network is down, and only one of those answers the question.
- `After manual step: <N>` - a step that cannot run until a human has completed step N.
  Its commands are reported rather than executed, instead of failing under `--execute`
  for a reason that is not a defect in the procedure.
- `EXPECTED_FAILURE_NOT_OBSERVED` (error), `MANUAL_GATE_UNRESOLVED` (error) and
  `COMMAND_DEFERRED_MANUAL_GATE` (info). The middle one exists because a gate naming a
  step that does not exist would quietly stop the tool from ever executing those
  commands while reporting a clean run.
- Eight test cases, twenty in total. One asserts the PRESENCE of a side effect - an
  `expect-fail` command must leave its marker on disk - because without it a clean
  report is indistinguishable from a directive the parser silently ignored.
- `LIMITS.md` records the coverage a gated step removes, and what an expected failure
  does not prove.

### Changed

- `docs/specs/2026-09-12-runbook-dry-run-design.md` gains section 7, the dated
  amendment recording why the format grew.
- `.gitignore` ignores `*.tmp`, so a run interrupted between `setUp` and `tearDown`
  cannot leave a test marker where it could be committed.


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

[Unreleased]: https://github.com/teageryc/runbook-dry-run/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/teageryc/runbook-dry-run/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/teageryc/runbook-dry-run/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/teageryc/runbook-dry-run/releases/tag/v0.1.0
