# Changelog

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-10

The three limits 0.3.0 recorded and kept (spec section 10), changed on Yan's picks
C1 to C3 and D1 to D5. Three code reviews ran before release, and the release gate
is a differential fuzzer against a CommonMark parser (spec section 11).

### Added

- `FENCED_LINE_SKIPPED` (info): a line inside fenced code, or inside an HTML block
  of CommonMark types 1 to 5, that the parser would otherwise read; reported at its
  step and not read.
- `FENCE_UNCLOSED` (error): a code fence or HTML block that never closes, at the
  step where it opened, or at the document.
- `FENCE_MISALIGNED` (error): a code fence or HTML block opened two or three spaces
  in and followed by a line indented less, which in a list item would end it.
- `DOCUMENT_LINE_IN_STEP` (error): `Working directory:` or `Elements:` inside a
  step.
- `FENCE_UNCLOSED`, `FENCE_MISALIGNED` and a misplaced `Working directory:` stop
  every command in the document, as a misplaced `Shell:` already did.
- `SourceLine`, and the `fenced_lines`, `unclosed_fence`, `misplaced_lines` and
  `misaligned_fences` fields, appended to `Step` and `Runbook` so positional callers
  still line up.
- Seventy-two test cases, 129 in total (`grep -c -E '^    def test_'
  tests/test_checker.py`), 41 mutation controls and a differential fuzz gate under
  `docs/plans/evidence/2026-11-10-v0.4/`; the last two are development only.

### Changed

- **Documents that passed before may now fail, and commands that ran before may
  not run.** A fenced `Run:` example is no longer executed; a fenced `## Step N` is
  no longer a step; a fenced `Shell:` example inside a step no longer refuses the
  document; a `Run:` inside `<pre>` or an HTML comment is no longer read; an
  unclosed fence, a misaligned indented fence and a document line inside a step
  are errors.
- A fence opened on a list item's marker line (`` - ``` ``) and the item's lines
  are read as CommonMark reads them; tabs are 4-column stops, and a blank line holds
  only spaces and tabs.
- A top-level fence or HTML block indented two or three spaces, with a line
  indented less inside it, is refused although it is valid Markdown: the cost of
  `FENCE_MISALIGNED`, fixed by indenting every line as far as the first.
- Line numbers count CommonMark's line endings only; each line is still read in
  the parts `str.splitlines()` makes of it, as before.
- On Windows, the console's input and output code pages are put back when a
  `--execute` check ends: a command's `chcp` used to stay in the terminal after the
  checker exited. Output decoding is unchanged: the planned change was measured to
  break one-line commands (spec section 11).
- The spec gains section 11 and four rows in section 4; section 10 and three
  `LIMITS.md` paragraphs carry dated corrections, and `LIMITS.md` gains a paragraph
  on escaped redirected output; the README lists the new codes.
- CI smokes: a fenced example leaves no marker beside an unfenced one that must;
  an unclosed fence and a misplaced `Working directory:` exit 1 and run nothing.

### Fixed

- A report quoting text the output's encoding cannot hold no longer crashes when
  redirected, where it exited 1 like a report with errors. Only a stream on the
  default strict handler is switched, for the call only; a stream without
  `reconfigure()` is escaped by hand.
- A runbook that is not UTF-8 is a message and exit 2, as an unreadable file
  already was, not a traceback and exit 1.

## [0.3.0] - 2026-11-03

Built after the second real use, never during it. Re-checking the publishing
procedure at v0.2 produced three `COMMAND_FAILED` findings that were not defects:
the document declared Git Bash in its header, and the format could not say so.

### Added

- `Shell: <name>` - document-level; `bash` (alias `Git Bash`), `pwsh`, `powershell`
  or `cmd`, case-insensitive. Under `--execute` every command runs in that shell.
- `SHELL_UNRESOLVED` (error) - on every run, a `Shell:` name the tool does not know
  (step 0), a `Shell:` line inside a step (at that step), or two lines naming
  different shells (step 0); under `--execute`, when a command would run, a shell
  this machine does not have. No command in the document is then executed.
  Falling back to the platform default was rejected: it is the behaviour that
  produced the three false findings.
- On Windows, Git Bash is found by walking up from `git --exec-path` to
  `bin\bash.exe`, never through `PATH`: on the machine this was built on,
  `shutil.which("bash")` answers with the WSL launcher in `WindowsApps`.
- `Launcher`, returned by `resolve_shell()`: how a command reaches its shell.
- Thirty-seven test cases, fifty-seven in total (`grep -c -E '^    def test_'
  tests/test_checker.py` gives 20 at v0.2.0), some platform-specific and skipped
  elsewhere. The declared-bash fixture must leave its marker; an unresolved shell
  must leave none. Its bash probe is `[[ ]]`, because a runner launched from Git
  Bash puts coreutils' `[.exe` on `PATH`, where `cmd.exe` finds it and a
  single-bracket probe passes in the wrong shell.

### Changed

- The spec gains sections 8, 9 and 10 and the `Shell:` line in sections 3 and 4;
  section 7's "not built", two statements of section 8 and one of section 9 carry
  dated corrections.
- `LIMITS.md` records the directive's limits, and its quoting paragraph now names
  the declared shell. It also records three limits the second review found and
  left in place: the parser does not know fenced code, so a fenced `Run:` example
  is executed; `Working directory:` and `Elements:` inside a step are ignored; a
  command that runs `chcp` is decoded in the code page it started with.
- `.github/workflows/ci.yml` smokes the directive both ways: a declared shell must
  leave its marker, an unresolved one must exit `1` and leave none.

### Fixed

Found by two code reviews of this release before it shipped (spec sections 9 and
10); each was reproduced, then fixed test-first.

- On Windows, a timeout now stops the whole command tree. A 2-second timeout took
  10.3 seconds under Git Bash, and under `cmd.exe` whenever the program was a
  grandchild - the second case predates this release. The command runs inside a
  Job Object. On POSIX, where the timeout never hung, commands stay in the
  checker's own session and process group, as in 0.2, so terminal prompts and
  Ctrl+C still reach them.
- An interrupted check (Ctrl+C) stops the running command instead of leaving it
  running unreported.
- Shell resolution no longer searches the current directory, where a planted
  `git.bat` was executed - even without `--execute`.
- A Git installed under a non-ASCII folder no longer crashes shell resolution:
  `git --exec-path` is read as UTF-8, and a git that never answers is given up on.
- A NUL byte in a command is a `COMMAND_FAILED` finding, not a traceback; true of
  undeclared runbooks before this release too.
- `FINDING_CODES["SHELL_UNRESOLVED"]` names all four cases that emit it.
- Bash receives its command in an environment variable: as an argument, a
  backslash pair before a quote arrived halved.
- Git Bash output is decoded as UTF-8, and no output can raise a decode error.
  `cmd.exe` and PowerShell output is decoded in the console's output code page,
  which they write in, instead of the ANSI one: measured 65001 under one shell and
  437 under another, against Python's cp1252, and a non-ASCII error read wrongly
  under both.
- A `Shell:` line inside a step, or a second conflicting one, is refused instead
  of silently dropped.
- `Runbook`'s new fields, `shell_declarations` and `shell_in_steps`, are appended
  after the 0.2 fields, so positional construction written against 0.2 still
  lines up. `Runbook.shell` is a read-only property, the first declaration, so it
  cannot disagree with them.
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
