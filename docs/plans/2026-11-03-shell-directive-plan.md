# runbook-dry-run v0.3.0 — `Shell:` directive Implementation Plan

> **For agentic workers:** executed inline in this session (superpowers:executing-plans discipline). Steps use `- [ ]` checkboxes. Mirror of this file, committed in Task 0: `G:\Projects\runbook-dry-run\docs\plans\2026-11-03-shell-directive-plan.md`.

## Context

KL-0122 (open since 2026-09-12, `G:\Business\AI\docs\knowledge\KNOWLEDGE_LEDGER.md`): re-checking the publish procedure `G:\Business\AI\Learnings\Publish-runbook-dry-run-Procedure-2026-09-12.md` at v0.2 produced three `COMMAND_FAILED` findings (steps 1–3) that are not defects. The procedure declares Git Bash in its header prose; `checker._run()` uses `subprocess.run(..., shell=True)`, which is `cmd.exe` on Windows, so `cd /g/Projects/...` fails. The design was decided and approved by Yan on 2026-11-03 and committed as spec §8 (`77fa3d4`, `G:\Projects\runbook-dry-run\docs\specs\2026-09-12-runbook-dry-run-design.md`).

**Goal:** a runbook can declare `Shell: <name>`; `--execute` runs its commands in that shell, and refuses out loud (`SHELL_UNRESOLVED`) when the shell cannot be found. Ships as v0.3.0, local only.

## Non-goals

- Editing the dated publish procedure. Acceptance runs on a scratch copy with the line added; the original is the control.
- A per-step shell override, or sh / zsh / fish / WSL. WSL is refused on purpose: it is what `PATH` returns for `bash` on this machine.
- Any change for runbooks without `Shell:` — same execution, no new finding (Yan's pick).
- Normalising PowerShell exit codes (e.g. auto-appending `exit $LASTEXITCODE`). Recorded as a limit instead.
- New CLI flags.
- Push, GitHub repo creation, GitHub release. Local commits and a local annotated tag only; publishing is Yan's separate decision.
- Ledger writes in `G:\Business\AI`. That is the later checkpoint capture, after lane ai-0a's commit (KL-0236..0239) lands.

## Measured before planning (2026-11-03, this machine)

From a PowerShell-launched Python (`G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\probe_shells.py`, copied there from the session scratchpad after the code review):

- `git --exec-path` = `G:/Apps/Git/ucrt64/libexec/git-core`; walking up, `bin\bash.exe` first exists at level 3 = `G:\Apps\Git\bin\bash.exe` (levels 0–2 absent).
- `shutil.which("bash")` = `C:\Users\cheny\AppData\Local\Microsoft\WindowsApps\bash.EXE` — the WSL launcher. This is why PATH is never consulted.
- `[bash, "-c", cmd]`: `[ -n "$BASH_VERSION" ]` 0; quoting round-trip `[ "$(printf '%s' "a b")" = "a b" ]` 0, its mangled negative (`"a  b"`) 1; `cd /g/... && git log` 0; marker lands in `cwd`; `exit 7` 7.
- `[pwsh, -NoProfile, -NonInteractive, -Command, cmd]`: `if ($PSVersionTable -and ("a b" -eq 'a b')) { exit 7 }` 7, negative 0.
- Undeclared (`shell=True` = cmd): the BASH_VERSION probe exits 1; the pwsh-only probe exits 1.

## Files

- Modify `G:\Projects\runbook-dry-run\runbook_dry_run\checker.py` — `Shell:` parsing, `resolve_shell()`, `_git_bash()`, `_run(launcher=...)`, `SHELL_UNRESOLVED` in `check()`.
- Modify `G:\Projects\runbook-dry-run\tests\test_checker.py` — classes `ShellDirective`, `ShellResolution`, `UnresolvedShell` (15 cases → 35 total; 48 after the review round below).
- Create `G:\Projects\runbook-dry-run\tests\fixtures\shell-bash.md`, `G:\Projects\runbook-dry-run\tests\fixtures\shell-unknown.md`.
- Modify `G:\Projects\runbook-dry-run\.github\workflows\ci.yml` (two smoke steps), `G:\Projects\runbook-dry-run\README.md`, `G:\Projects\runbook-dry-run\LIMITS.md`, `G:\Projects\runbook-dry-run\CHANGELOG.md`, `G:\Projects\runbook-dry-run\runbook_dry_run\__init__.py`.
- Create `G:\Projects\runbook-dry-run\docs\plans\2026-11-03-shell-directive-plan.md` (this plan's mirror).

All paths relative to `G:\Projects\runbook-dry-run`. Commands below run in Git Bash from that directory. Every commit uses `git commit -m "<msg>" -- <paths>` and ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Exit codes are read unpiped (`cmd; echo "exit=$?"`).

---

### Task 0: Preflight, guard check, plan mirror

- [ ] **Step 1: Non-goals guard fired.** Read the last line of the guard's log (the handoff's step 2): it must carry `verdict` and `source`, timestamp after `2026-11-03T09:15:55Z`. No new line = the hook did not run → `node C:\Users\cheny\.claude\hooks\pre-tooluse-plan-nongoals-guard.test.cjs`.
- [ ] **Step 2: Clean start.** `git status --porcelain | wc -l` → `0`; `git log -1 --format=%h` → `77fa3d4`.
- [ ] **Step 3: Baseline.** `python -m unittest discover -s tests; echo "exit=$?"` → `Ran 20 tests`, `OK`, `exit=0`.
- [ ] **Step 4: Mirror and commit the plan.** Copy this file to `docs/plans/2026-11-03-shell-directive-plan.md`; `git check-ignore -v docs/plans/2026-11-03-shell-directive-plan.md` prints nothing; commit `docs(plan): v0.3 Shell: directive implementation plan`.

### Task 1: Parse the `Shell:` line

- [ ] **Step 1: Failing test.** Add to `tests/test_checker.py` (and `import shutil` / `from unittest import mock` at the top; import `resolve_shell` alongside `check, has_errors, parse` — it lands in Task 2, so add it to the import in Task 2):

```python
class ShellDirective(unittest.TestCase):
    """A document declares the shell its commands are written for.

    Every execution test pairs with a control that runs the same command undeclared:
    a clean report proves nothing unless the declaration is what made it clean.
    """

    MARKER = os.path.join(REPO_ROOT, "shell-bash-marker.tmp")

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def tearDown(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def test_the_shell_line_is_read_and_an_absent_one_is_none(self):
        book = parse("# Runbook: x\n\nWorking directory: `.`\nShell: `Git Bash`\n")
        self.assertEqual("Git Bash", book.shell)
        with open(os.path.join(FIXTURES, "good.md"), encoding="utf-8") as handle:
            self.assertIsNone(parse(handle.read()).shell)
```

- [ ] **Step 2: Run, expect FAIL.** `python -m unittest discover -s tests -k ShellDirective -v` → `AttributeError: 'Runbook' object has no attribute 'shell'`.
- [ ] **Step 3: Implement** in `checker.py`:

```python
SHELL_LINE = re.compile(r"^Shell\s*:\s*(.*)$")          # beside WORKING_DIRECTORY

@dataclass
class Runbook:
    title: str = ""
    working_directory: str | None = None
    shell: str | None = None                                 # new field
    element_inventory: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
```

In `parse()`, in the pre-step block directly after the `WORKING_DIRECTORY` branch:

```python
            shell = SHELL_LINE.match(line)
            if shell:
                book.shell = _first_backticked(shell.group(1))
                in_elements = False
                continue
```

(The publish procedure's header line `> **Written** … · **Shell** Git Bash …` does not match `^Shell`, so the original stays undeclared — that is the acceptance control.)

- [ ] **Step 4: Run, expect PASS**, then full suite `Ran 21 tests … OK`.
- [ ] **Step 5: Commit** `feat(parse): read a document-level Shell: line`.

### Task 2: `resolve_shell()` — names to an argv prefix, Git Bash through git

- [ ] **Step 1: Failing tests.** Change the import to `from runbook_dry_run.checker import check, has_errors, parse, resolve_shell  # noqa: E402` and add:

```python
class ShellResolution(unittest.TestCase):
    def test_git_bash_is_an_alias_and_case_does_not_matter(self):
        alias, _ = resolve_shell("Git Bash")
        self.assertIsNotNone(alias)
        self.assertEqual(alias, resolve_shell("BASH")[0])

    def test_an_unknown_name_is_refused_with_the_known_names(self):
        launcher, reason = resolve_shell("fish")
        self.assertIsNone(launcher)
        self.assertIn("'fish'", reason)
        self.assertIn("Git Bash", reason)

    @unittest.skipUnless(sys.platform == "win32", "the Git Bash lookup is Windows-only")
    def test_windows_bash_comes_from_git_never_from_path(self):
        """On the machine this was built on, PATH answers bash with the WSL launcher."""
        launcher, _ = resolve_shell("bash")
        self.assertIsNotNone(launcher)
        exe = launcher[0].casefold()
        self.assertTrue(exe.endswith(os.path.join("bin", "bash.exe")), exe)
        self.assertNotIn("windowsapps", exe)
        self.assertNotIn("system32", exe)

    @unittest.skipUnless(sys.platform == "win32", "the Git Bash lookup is Windows-only")
    def test_windows_bash_without_git_is_unresolved(self):
        with mock.patch("runbook_dry_run.checker.shutil.which", return_value=None):
            launcher, reason = resolve_shell("bash")
        self.assertIsNone(launcher)
        self.assertIn("git", reason)

    @unittest.skipUnless(sys.platform == "win32", "cmd exists only on Windows")
    def test_cmd_on_windows_is_the_platform_default(self):
        self.assertEqual(((), ""), resolve_shell("cmd"))

    @unittest.skipIf(sys.platform == "win32", "cmd and powershell exist on Windows")
    def test_cmd_and_powershell_are_refused_elsewhere(self):
        self.assertIsNone(resolve_shell("cmd")[0])
        self.assertIsNone(resolve_shell("powershell")[0])
```

- [ ] **Step 2: Run, expect FAIL** (`ImportError: cannot import name 'resolve_shell'`).
- [ ] **Step 3: Implement** in `checker.py` (`import shutil`, `import sys` at the top; constants beside the other module constants; functions after `_resolve()`):

```python
# Accepted `Shell:` names, case-insensitive, mapped to the shell actually resolved.
SHELL_NAMES = {
    "bash": "bash",
    "git bash": "bash",
    "pwsh": "pwsh",
    "powershell": "powershell",
    "cmd": "cmd",
}
KNOWN_SHELLS = "bash, Git Bash, pwsh, powershell, cmd"
POWERSHELL_FLAGS = ("-NoProfile", "-NonInteractive", "-Command")


def _git_bash() -> tuple[tuple[str, ...] | None, str]:
    """Find Git Bash through git's own installation, never through PATH.

    On Windows, PATH answers `bash` with the WSL launcher (System32 or the
    WindowsApps alias), which runs the command under Linux with Linux paths: a
    third shell, chosen silently. git's exec path sits a few levels below the
    installation's bin/bash.exe, which is what "Git Bash" means.
    """
    git = shutil.which("git")
    if git is None:
        return None, "Git Bash is looked for through git's installation, and git is not on PATH"
    try:
        probe = subprocess.run(
            [git, "--exec-path"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git --exec-path did not answer: {exc}"
    start = probe.stdout.strip()
    if probe.returncode != 0 or not start:
        return None, f"git --exec-path exited {probe.returncode}"
    directory = os.path.normpath(start)
    for _ in range(4):
        candidate = os.path.join(directory, "bin", "bash.exe")
        if os.path.isfile(candidate):
            return (candidate, "-c"), ""
        directory = os.path.dirname(directory)
    return None, f"no bin/bash.exe in the four directories above git's exec path {start}"


def resolve_shell(declared: str) -> tuple[tuple[str, ...] | None, str]:
    """Turn a `Shell:` name into the argv prefix that runs a command in that shell.

    Returns (prefix, "") when the shell is usable and (None, reason) when it is
    not. An empty prefix means the platform default through `shell=True`, which
    on Windows is cmd.exe.
    """
    name = declared.strip()
    key = SHELL_NAMES.get(name.casefold())
    if key is None:
        return None, f"{name!r} is not a shell this tool knows ({KNOWN_SHELLS})"
    windows = sys.platform == "win32"
    if key == "cmd":
        return ((), "") if windows else (None, "cmd exists only on Windows")
    if key == "bash":
        if windows:
            return _git_bash()
        found = shutil.which("bash")
        return ((found, "-c"), "") if found else (None, "bash is not on PATH")
    if key == "powershell" and not windows:
        return None, "powershell (Windows PowerShell) exists only on Windows; declare pwsh"
    found = shutil.which(key)
    if found is None:
        return None, f"{key} is not on PATH"
    return (found, *POWERSHELL_FLAGS), ""
```

- [ ] **Step 4: Run, expect PASS** (`-k ShellResolution`; on Windows 1 skipped), then full suite `Ran 27 tests … OK (skipped=1)`.
- [ ] **Step 5: Commit** `feat(shell): resolve a declared shell; Git Bash through git, never PATH`.

### Task 3: Run every command in the declared shell

- [ ] **Step 1: Fixture** `tests/fixtures/shell-bash.md`:

```markdown
# Runbook: commands written for bash, declared as such

Working directory: `.`
Shell: `Git Bash`

## Step 1 — Prove the commands reach bash and not the platform default
Run: `[ -n "$BASH_VERSION" ]`
On failure: the commands ran in some other shell. Open Git Bash and start again.

## Step 2 — Prove quoting survives the trip into the declared shell
Run: `[ "$(printf '%s' "a b")" = "a b" ]`
On failure: the command reached the shell altered. Report it before trusting any other step.

## Step 3 — Leave proof that the commands really ran
Run: `: > shell-bash-marker.tmp`
On failure: the working directory is not writable. Stand in the repository root.
```

- [ ] **Step 2: Failing tests.** Module-level helper after `codes_at()`, then add to `ShellDirective`:

```python
def one_step(shell_line: str, directive: str) -> str:
    return (
        "# Runbook: one step\n\nWorking directory: `.`\n"
        f"{shell_line}\n\n"
        "## Step 1 - the command under test\n"
        f"{directive}\n"
        "On failure: stop.\n"
    )
```

```python
    PWSH_PROBE = (
        "Run (expect-fail: 7): "
        "`if ($PSVersionTable -and (\"a b\" -eq 'a b')) { exit 7 }`"
    )

    def test_a_declared_bash_runs_every_command_in_bash(self):
        findings = run_fixture("shell-bash.md", execute=True)
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")
        self.assertTrue(
            os.path.exists(self.MARKER),
            "the commands never ran, so a clean report means nothing",
        )

    def test_the_same_commands_fail_without_the_declaration(self):
        with open(os.path.join(FIXTURES, "shell-bash.md"), encoding="utf-8") as handle:
            text = handle.read().replace("Shell: `Git Bash`\n", "")
        book = parse(text)
        self.assertIsNone(book.shell, "the control must really be undeclared")
        findings = check(book, base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))

    def test_a_mangled_quote_would_be_caught(self):
        """The round-trip step can fail: the same comparison with one space altered."""
        text = one_step("Shell: `bash`", "Run: `[ \"$(printf '%s' \"a b\")\" = \"a  b\" ]`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh is not installed")
    def test_a_declared_pwsh_runs_the_command_in_pwsh(self):
        findings = check(
            parse(one_step("Shell: `pwsh`", self.PWSH_PROBE)), base_dir=REPO_ROOT, execute=True
        )
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh is not installed")
    def test_the_pwsh_probe_fails_without_the_declaration(self):
        findings = check(parse(one_step("", self.PWSH_PROBE)), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"EXPECTED_FAILURE_NOT_OBSERVED"}, codes_at(findings, 1))
```

- [ ] **Step 3: Run, expect FAIL** — `test_a_declared_bash_runs_every_command_in_bash` reports `COMMAND_FAILED` (cmd ran it) and `test_a_declared_pwsh_runs_the_command_in_pwsh` reports `EXPECTED_FAILURE_NOT_OBSERVED`; the two controls already pass (they describe today's behaviour).
- [ ] **Step 4: Implement.** `_run()` gains the launcher; the subprocess call becomes:

```python
def _run(
    command: str, cwd: str, timeout: float, launcher: tuple[str, ...] = ()
) -> tuple[int, str]:
    """Run one command and read its exit code UNPIPED.

    `returncode` is read off the completed process itself. Piping the command into
    anything - a pager, a formatter, `tee` - makes the pipeline's status the one
    you see, and a failing step then reports success.

    With a launcher, the command is handed to the declared shell as one argument;
    without one, the platform default runs it, exactly as before v0.3.
    """
    try:
        proc = subprocess.run(
            [*launcher, command] if launcher else command,
            shell=not launcher,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
```

In `check()`, after the `MISSING_WORKING_DIRECTORY` block and before `base = ...`:

```python
    launcher: tuple[str, ...] = ()
    if book.shell is not None:
        resolved, problem = resolve_shell(book.shell)
        if resolved is not None:
            launcher = resolved
```

and both `_run(...)` calls pass `launcher`: `_run(command, base, timeout, launcher)` and `_run(expected.command, base, timeout, launcher)`. (An unresolved shell silently falls through here until Task 4 — do not commit Task 3 without Task 4 if pausing.)

- [ ] **Step 5: Run, expect PASS**; full suite `Ran 32 tests … OK (skipped=1)`.
- [ ] **Step 6: Commit** `feat(execute): run commands in the declared shell` (with the fixture).

### Task 4: `SHELL_UNRESOLVED` — refuse out loud

- [ ] **Step 1: Fixture** `tests/fixtures/shell-unknown.md`:

```markdown
# Runbook: a shell this tool does not know

Working directory: `.`
Shell: `fish`

## Step 1 — A command that must never run under an unresolved shell
Run: `python -c "open('shell-unknown-marker.tmp', 'w').close()"`
On failure: stop.
```

- [ ] **Step 2: Failing tests:**

```python
class UnresolvedShell(unittest.TestCase):
    """A check that stops checking must say so out loud, and must really stop.

    Asserted by the ABSENCE of the marker, paired with ShellDirective's test that
    the same kind of command DOES leave one when the shell resolves.
    """

    MARKERS = [
        os.path.join(REPO_ROOT, "shell-unknown-marker.tmp"),
        os.path.join(REPO_ROOT, "shell-bash-marker.tmp"),
    ]

    def setUp(self):
        for marker in self.MARKERS:
            if os.path.exists(marker):
                os.remove(marker)

    tearDown = setUp

    def test_an_unknown_shell_is_reported_once_and_nothing_runs(self):
        findings = run_fixture("shell-unknown.md", execute=True)
        self.assertEqual(["SHELL_UNRESOLVED"], [f.code for f in findings])
        self.assertEqual(0, findings[0].step)
        self.assertIn("fish", findings[0].detail)
        self.assertIn("no command in this document was executed", findings[0].detail)
        self.assertTrue(has_errors(findings))
        self.assertFalse(
            os.path.exists(self.MARKERS[0]),
            "a command ran under a shell that could not be resolved",
        )

    def test_it_is_reported_without_execute_too(self):
        findings = run_fixture("shell-unknown.md")
        self.assertEqual(["SHELL_UNRESOLVED"], [f.code for f in findings])

    def test_an_unavailable_shell_refuses_on_every_platform(self):
        with mock.patch(
            "runbook_dry_run.checker.resolve_shell", return_value=(None, "pwsh is not on PATH")
        ):
            findings = run_fixture("shell-bash.md", execute=True)
        self.assertEqual(["SHELL_UNRESOLVED"], [f.code for f in findings])
        self.assertIn("pwsh is not on PATH", findings[0].detail)
        self.assertFalse(
            os.path.exists(self.MARKERS[1]),
            "a command ran under a shell reported unavailable",
        )
```

- [ ] **Step 3: Run, expect FAIL** (no finding; the python marker is created under the default shell).
- [ ] **Step 4: Implement.** Add to `FINDING_CODES`:

```python
    "SHELL_UNRESOLVED": "the document names a shell this tool does not know or this machine does not have",
```

and complete the Task 3 block in `check()`:

```python
    launcher: tuple[str, ...] = ()
    if book.shell is not None:
        resolved, problem = resolve_shell(book.shell)
        if resolved is None:
            findings.append(
                Finding(
                    0,
                    "",
                    "SHELL_UNRESOLVED",
                    f"{problem}, so no command in this document was executed",
                )
            )
            # Falling back to the platform default is the behaviour that produced
            # three COMMAND_FAILED findings that were not defects (spec section 8).
            execute = False
        else:
            launcher = resolved
```

- [ ] **Step 5: Run, expect PASS**; full suite `Ran 35 tests … OK (skipped=1)`.
- [ ] **Step 6: Commit** `feat(check): SHELL_UNRESOLVED refuses execution out loud`.

### Task 5: CI smoke steps

- [ ] **Step 1:** Append to the `smoke` job in `.github/workflows/ci.yml`:

```yaml
      - name: A declared shell runs the commands, and they really ran
        run: |
          python -m runbook_dry_run tests/fixtures/shell-bash.md --base-dir . --execute
          if [ ! -f shell-bash-marker.tmp ]; then
            echo "the declared-shell commands never ran, so their clean report means nothing"
            exit 1
          fi
          rm -f shell-bash-marker.tmp

      - name: An unresolved shell exits 1 and runs nothing
        run: |
          set +e
          python -m runbook_dry_run tests/fixtures/shell-unknown.md --base-dir . --execute
          code=$?
          set -e
          if [ "$code" -ne 1 ]; then
            echo "expected exit 1 from an unresolved shell, got $code"
            exit 1
          fi
          if [ -f shell-unknown-marker.tmp ]; then
            echo "a command ran under a shell that could not be resolved"
            exit 1
          fi
```

- [ ] **Step 2: Local equivalent** (Git Bash): run both blocks by hand; first prints the clean report and the marker exists; second prints `exit` 1 and no marker. `python -c "import yaml"` is not available — validate indentation by eye against the existing steps.
- [ ] **Step 3: Commit** `ci: smoke the declared shell both ways`.

### Task 6: Documentation and version

- [ ] **`runbook_dry_run/__init__.py`:** `__version__ = "0.3.0"` (was `0.1.0` through the 0.2.0 release).
- [ ] **`CHANGELOG.md`:** insert under `## [Unreleased]`:

```markdown
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
  must leave none.

### Changed

- The spec gains section 8 and the `Shell:` line in sections 3 and 4; section 7's
  "not built" carries a dated correction.
- `LIMITS.md` records four limits of the directive, and its quoting paragraph now
  names the declared shell.

### Fixed

- `runbook_dry_run.__version__` read `0.1.0` through the 0.2.0 release; it now
  matches this changelog.
```

  and update the link block: `[Unreleased]: …/compare/v0.3.0...HEAD`, add `[0.3.0]: https://github.com/teageryc/runbook-dry-run/compare/v0.2.0...v0.3.0`.

- [ ] **`README.md` EN** — after the `After manual step:` paragraph insert:

````markdown
One directive belongs to the document rather than to a step:

```markdown
Working directory: `/srv/ledger`
Shell: `Git Bash`
```

`Shell:` names the shell the commands are written for - `bash` (or `Git Bash`), `pwsh`, `powershell` or `cmd` - and `--execute` runs them in it. On Windows, Git Bash is found through git's own installation, never through `PATH`, which can answer with the WSL launcher. If the declared shell cannot be found, nothing is executed and the report says so. A document with no `Shell:` line runs in the platform default, as before.
````

  then add the table row `` | `SHELL_UNRESOLVED` | the `Shell:` line names a shell this tool does not know, or one this machine does not have; nothing is then executed | `` after `MANUAL_GATE_UNRESOLVED`; change "Twenty cases." to "Thirty-five cases, a few of them platform-specific and skipped elsewhere."; append to the side-effect paragraph: "A runbook declaring `Shell:` must leave its marker too, and one whose shell cannot be found must leave none."

- [ ] **`README.md` 中文** — the same three places: after the `After manual step:` paragraph:

````markdown
有一条指令属于整份文档，而不属于某个步骤：

```markdown
Working directory: `/srv/ledger`
Shell: `Git Bash`
```

`Shell:` 点明命令是为哪个 shell 写的——`bash`（或 `Git Bash`）、`pwsh`、`powershell` 或 `cmd`——`--execute` 就在那个 shell 里运行它们。在 Windows 上，Git Bash 通过 git 自己的安装目录找到，绝不通过 `PATH`，因为 `PATH` 可能给出 WSL 启动器。声明的 shell 找不到时，什么都不执行，报告会说明这一点。没有 `Shell:` 行的文档照旧在平台默认 shell 里运行。
````

  then add the table row `` | `SHELL_UNRESOLVED` | `Shell:` 行点名的 shell 本工具不认识，或这台机器上没有；此时什么都不执行 | ``; "二十个用例。" → "三十五个用例，其中几个只适用于特定平台，在别的平台上跳过。"; append "声明了 `Shell:` 的手册同样必须留下标记，而 shell 找不到的手册必须一个都不留。"

- [ ] **`LIMITS.md` EN** — rewrite the second sentence of the quoting paragraph to "Commands run through the shell the document declares with `Shell:`, or through the platform's own when it declares none." (rest unchanged); after the expected-failure paragraph insert:

```markdown
**A declared shell is the shell I ran, not the shell the reader will open.** *(Added 2026-11-03, v0.3.)* `Shell: Git Bash` makes me run every command in Git Bash. It does not make the operator open Git Bash, and if they type the same commands into PowerShell, the document told them not to and I cannot see that it did not work.

**I find Git Bash only through git.** *(Added 2026-11-03, v0.3.)* On Windows I walk up from `git --exec-path` to the installation's `bin\bash.exe` and never ask `PATH`, because on the machine this was built on `PATH` answered `bash` with the WSL launcher, which runs the command under Linux. The cost: a Git Bash the reader has, but whose git is not on `PATH`, is invisible to me, and I report `SHELL_UNRESOLVED` for a shell that exists.

**Under PowerShell, the exit code I read is PowerShell's summary, not the command's.** *(Added 2026-11-03, v0.3.)* `-Command` collapses any failure of the last statement to `1` - even a native program's own code - and reports a failure followed by a success as `0`. A `Run (expect-fail: <code>):` step under `Shell: pwsh` must end its command with `; exit $LASTEXITCODE`, or the code it names can never arrive.

**A runbook that declares no shell is checked in mine, and I say nothing about it.** *(Added 2026-11-03, v0.3.)* Without a `Shell:` line I use the platform default - `cmd.exe` on Windows - and add no finding, because a finding on every existing runbook would be noise. A bash runbook checked on Windows without the line still fails in exactly the way that made this directive necessary; the only defence is to declare it.
```

- [ ] **`LIMITS.md` 中文** — quoting paragraph's second sentence → "命令通过文档用 `Shell:` 声明的那个 shell 运行，没有声明时通过平台自己的 shell 运行。"; after the 预期中的失败 paragraph insert:

```markdown
**声明的 shell 是我运行时用的 shell，不是读者会打开的那个。**（2026-11-03 补记，v0.3）`Shell: Git Bash` 让我在 Git Bash 里运行每一条命令，但不会让操作员去打开 Git Bash。如果他们把同样的命令敲进 PowerShell，文档已经告诉过他们不要这样做，而我看不见那样行不通。

**我只通过 git 找 Git Bash。**（2026-11-03 补记，v0.3）在 Windows 上，我从 `git --exec-path` 往上找到安装目录下的 `bin\bash.exe`，从不询问 `PATH`——在构建本工具的那台机器上，`PATH` 对 `bash` 给出的是 WSL 启动器，它会把命令放到 Linux 里运行。代价是：读者确实装了 Git Bash、但 git 不在 `PATH` 上时，我看不见它，会对一个存在的 shell 报出 `SHELL_UNRESOLVED`。

**在 PowerShell 下，我读到的退出码是 PowerShell 的总结，不是命令自己的。**（2026-11-03 补记，v0.3）`-Command` 会把最后一条语句的任何失败压成 `1`——连原生程序自己的代码也一样——并把先失败后成功报成 `0`。`Shell: pwsh` 下的 `Run (expect-fail: <代码>):` 步骤，命令必须以 `; exit $LASTEXITCODE` 结尾，否则它点名的那个代码永远到不了。

**没有声明 shell 的手册，是在我的默认 shell 里检查的，而我对此一言不发。**（2026-11-03 补记，v0.3）没有 `Shell:` 行时，我用平台默认 shell——Windows 上是 `cmd.exe`——而且不加任何发现，因为对每一份现有手册都报的发现就是噪音。一份为 bash 写的手册，在 Windows 上不带这一行检查，仍然会以当初促成这条指令的那种方式失败；唯一的防线是把它声明出来。
```

- [ ] **Commit** `docs: v0.3.0 - Shell: directive in README, LIMITS, CHANGELOG; version 0.3.0`.

### Task 7: Whole-suite and repository checks

- [ ] `python -m unittest discover -s tests -v; echo "exit=$?"` → `Ran 35 tests`, `OK (skipped=1)`, `exit=0`. If the count differs, fix the README/CHANGELOG numbers to the measured one (and say so).
- [ ] Count the new code in docs both ways: `grep -c SHELL_UNRESOLVED README.md` → 2 and `grep -c SHELL_UNRESOLVED LIMITS.md` → 2 (one line per half); positive control `grep -c MANUAL_GATE_UNRESOLVED README.md` → 2.
- [ ] `git status --porcelain | wc -l` → 0 (no stray `*.tmp`; they are gitignored, so also `ls *.tmp 2>&1` → no such file).

### Task 8: Acceptance on the real procedure (scratch copy + control)

- [ ] Write (Write tool, not a heredoc) a Python helper in the scratchpad that copies `G:\Business\AI\Learnings\Publish-runbook-dry-run-Procedure-2026-09-12.md` to `<scratchpad>\procedure-declared.md` and inserts ``Shell: `Git Bash` `` on the line after `Working directory:`; assert exactly one insertion.
- [ ] In Git Bash from the repo, with prompts disabled because step 4 calls `git ls-remote` on a URL that may not exist:

```bash
export GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never
python -m runbook_dry_run "<scratchpad>/procedure-declared.md" --execute; echo "exit=$?"
python -m runbook_dry_run "G:/Business/AI/Learnings/Publish-runbook-dry-run-Procedure-2026-09-12.md" --execute; echo "exit=$?"
```

- [ ] **Pass:** the declared copy has no `COMMAND_FAILED` at steps 1, 2 or 3; the original (control) still has `COMMAND_FAILED` at steps 1, 2 and 3. Other steps' results are recorded verbatim and are not pass conditions (step 4 depends on whether the remote exists; 6 is destructive; 7 is gated).

### Task 9: Review

- [ ] Run the `code-review` skill (default level) over `77fa3d4..HEAD`. Fix confirmed findings test-first, re-run Task 7, commit each fix separately.

### Task 10: Local release tag

- [ ] `git tag -a v0.3.0 -m "v0.3.0 - Shell: directive, from the second real use"` (annotated, matching v0.1.0 / v0.2.0). `git tag -l` lists three tags. No push.

## Verification (end to end)

1. Task 7: 35 tests, `OK (skipped=1)` on Windows, exit 0 read unpiped.
2. Every new behaviour is proven both ways: bash fixture clean + marker present vs. undeclared control `COMMAND_FAILED`; quoting round-trip passes vs. mangled-space control fails; pwsh probe clean vs. undeclared `EXPECTED_FAILURE_NOT_OBSERVED`; unresolved shell leaves no marker vs. resolved shell leaves one.
3. Task 8 on the real procedure: three false `COMMAND_FAILED` gone with the line, present without it.
4. CI is not run (nothing is pushed); the two new smoke steps are exercised locally in Task 5.

> **Corrected 2026-11-04 (publish)** — item 4 was true when written and is no longer. On Yan's go, `main` and the annotated tag `v0.3.0` were pushed to https://github.com/teageryc/runbook-dry-run on 2026-11-04, both at `cf8d7f2`. The first CI run, 41879067288, ran on that commit from 17:37:40Z to 17:46:03Z and completed with conclusion `success`, 5 of 5 jobs: `tests` on windows-latest and ubuntu-latest with Python 3.11 and 3.13, and `smoke`. Command: `curl -s https://api.github.com/repos/teageryc/runbook-dry-run/actions/runs/41879067288/jobs`.

## After this plan (not part of it)

- Checkpoint capture in `G:\Business\AI` once lane ai-0a's KL-0236..0239 commit has landed: re-read the Next-ID counter, one entry (KL-0240 or later) resolving KL-0122 and recording Yan's 2026-11-03 picks; announce exact paths to live lanes before staging.
- Ask Yan whether and when to publish the repository (no remote-tracking branch exists locally; `gh` as `teagerca-prog` cannot see `teageryc/runbook-dry-run`).

> **Corrected 2026-11-04 (publish)** — the last bullet is answered: Yan said to publish, and the repository went public on 2026-11-04 (see the correction under Verification). `origin/main` now exists locally. Now that the repository is public, `gh` as `teagerca-prog` can read it but still cannot push: `gh api repos/teageryc/runbook-dry-run --jq .permissions` prints `"pull":true` and `"push":false`.

## Deviations during execution

> **Corrected 2026-11-03 (Task 3)** — the step-1 probe in `G:\Projects\runbook-dry-run\tests\fixtures\shell-bash.md` is `[[ -n "$BASH_VERSION" ]]`, not the `[ -n "$BASH_VERSION" ]` written in Task 3 above. The single-bracket form does not discriminate: when the test runner is launched from Git Bash, `PATH` contains `G:\Apps\Git\usr\bin\[.exe` (coreutils `test`), so `cmd.exe` runs it with the literal string `"$BASH_VERSION"` and exits 0 — the undeclared control then passed for the wrong reason and its test failed. The "Measured before planning" bullet that the undeclared probe exits 1 was true only for a PowerShell-launched Python. `[[` is a bash keyword with no external binary (`[[.exe` does not exist), so it exits 1 under cmd from either launch context and 0 under bash.

> **Corrected 2026-11-03 (Task 5)** — Task 5 says PyYAML is not available; it is (`python -c "import yaml"` exits 0). The workflow was therefore validated by parsing it with `yaml.safe_load` and listing each job's steps, not by eye.

## Code review round (Task 9)

The `code-review` skill reported fifteen findings over `77fa3d4..6f35c5b`. Two changed the approved design and went to Yan, who picked the recommended option for both on 2026-11-03; the rest were fixed test-first, each commit red before green. Spec section 9 records the contract changes.

| # | Finding | Disposition | Commit |
| --- | --- | --- | --- |
| 1 | `--timeout` could not stop a command under Git Bash (or a `cmd.exe` grandchild) | Job Object on Windows, process group on POSIX; `taskkill /T` and a parent-id walk measured and rejected | `9221eb9` |
| 2 | `shutil.which` searched the current directory; a planted `git.bat` ran | `_on_path()`: absolute `PATH` entries only | `d76e769` |
| 3 | A backslash pair before a quote reached bash halved | Command passed in `RUNBOOK_DRY_RUN_COMMAND` | `cd230b2` |
| 4 | UTF-8 output crashed the reader thread under cp1252 | Bash decoded as UTF-8; `errors="replace"` everywhere | `40a0255` |
| 5 | A `Shell:` line inside a step, or a second one, was silently ignored | Yan's pick: refused as `SHELL_UNRESOLVED` | `225cb3c` |
| 6 | The pwsh `; exit $LASTEXITCODE` advice was wrong for cmdlets | Measured; spec §8 corrected, LIMITS rewritten | docs commit |
| 7 | `Runbook.shell` inserted mid-dataclass broke positional construction | Field appended after the 0.2 fields | `f2918e8` |
| 8 | `SHELL_UNRESOLVED` without `--execute` failed CI on another OS | Yan's pick: unknown name always; availability only under `--execute` | `02799fc` |
| 9 | Bash-less git first on `PATH`; level count in the message | Message fixed (`cd230b2`); the bash-less git recorded in LIMITS | docs commit |
| 10 | `SHELL_UNRESOLVED` for documents with nothing to run | Folded into #8: asked only when a command would run | `02799fc` |
| 11 | README claimed every test asserts a code and a step | Audited (26 of 48 assert a code); two `NO_STEPS` tests now assert step 0; sentence reworded | docs commit |
| 12, 13 | Fall-through to PowerShell flags; `KNOWN_SHELLS` a hand copy | One table, one branch per shell | `cd230b2` |
| 14 | This plan cited relative and scratchpad paths | Absolute paths; probes archived below | docs commit |
| 15 | No tests for timeouts, cmd execution, misplaced lines | Added with #1, #5 and #8 | as above |

**Evidence**, first round:

- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\probe_shells.py` — the pre-plan measurements.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\accept-declared.txt` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\accept-original.txt` — Task 8 acceptance and its control, on the pre-review code at `6f35c5b`.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\accept-declared-final.txt` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\accept-original-final.txt` — the same pair re-run on the reviewed code at `ee45449`, with the tree committed first: an earlier re-run with the docs still uncommitted correctly failed the procedure's own "nothing is uncommitted" step.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\backslash_red.py` — finding 3 reproduced, then fixed.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\run_timing.py`, `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\tree_kill_debug.py`, `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\taskkill_variants.py`, `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\msys_tree.py`, `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\ctypes_tree_kill.py` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\job_kill.py` — finding 1: why taskkill and the parent walk fail, and the Job Object that works.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\pwsh_exit_codes.py` — finding 6.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\audit_test_claims.py` — finding 11.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\make_declared_copy.py` — builds the Task 8 copy.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\review\` — the reviewer's own probes. They call the pre-fix API at `6f35c5b` (`resolve_shell` then returned a tuple) and do not run against later commits.

> **Corrected 2026-11-03 (second review)** — row 1 records what `9221eb9` built, and its POSIX half, a process group of the command's own, was reverted before release in `d9c3059`; see the second review round below. The Evidence list was rewritten with an absolute path on every file (second review, finding 14), and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\run_timing.py` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\audit_test_claims.py` were amended (`8ef3547`, `526586d`).

## Second review round (2026-11-03)

The `code-review` skill (level `xhigh`) reported fifteen findings over `6f35c5b..dacaf75`, the first round's fixes. Each was reproduced, measured or read against the code before acting. Yan picked three dispositions: POSIX back to v0.2's placement (findings 2 and 4), the two parser findings recorded in `G:\Projects\runbook-dry-run\LIMITS.md` rather than changed (5 and 6), and all three optional cleanups (10, 12, 13). Every code fix was red first, then green from Git Bash AND PowerShell; the POSIX ones were also red, then green, under WSL Ubuntu.

| # | Finding | Disposition | Commit |
| --- | --- | --- | --- |
| 1 | `_git_bash` decoded git's exec path in the locale code page (a non-ASCII install crashed `check()`) and read its pipe without a bound after a kill | Bytes decoded as UTF-8 with a locale fallback; both waits bounded | `b5c6f40` |
| 2 | The bare `Popen` lost `subprocess.run`'s kill-on-exception: Ctrl+C left the command running | Kill and reap on any exception | `d9c3059` |
| 3 | A NUL byte in a command raised `ValueError` out of `check()` and leaked the job handle | `COMMAND_FAILED`, exit 127 | `d3461c5` |
| 4 | `start_new_session` on every POSIX command broke spec §3 and §8 (`sudo`, `ssh`, Ctrl+C) | Yan's pick: v0.2's placement on POSIX; Windows keeps the Job Object | `d9c3059` |
| 5 | `Working directory:` and `Elements:` inside a step are dropped silently (since v0.1) | Yan's pick: recorded in `G:\Projects\runbook-dry-run\LIMITS.md`, parser unchanged | `3592bab` |
| 6 | A fenced `Shell:` example inside a step refuses the document; any fenced directive is read, so a fenced `Run:` example is executed (since v0.1) | Yan's pick: recorded in `G:\Projects\runbook-dry-run\LIMITS.md` | `3592bab` |
| 7 | The conflict test ran `exit 0`, so it could not tell refused from run | Marker absence asserted; with `execute = False` removed the new test fails and the old one passes | `f585870` |
| 8 | `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-shell-directive\run_timing.py` crashed on the two-argument `_kill_tree` | Arguments passed through; re-run at HEAD, both timeouts 2.0-2.1 s | `8ef3547` |
| 9 | `G:\Projects\runbook-dry-run\LIMITS.md` said an escaped program keeps the checker waiting; the code moves on after 10 s and leaves it running | Rewritten in EN and 中文 | `06d2608` |
| 10 | `cmd.exe` and PowerShell output decoded in the ANSI page | Yan's pick: the console's output code page, read per command | `3c095cf` |
| 11 | `SHELL_UNRESOLVED`'s description named two of its four cases | Rewritten, with a test | `f8436ed` |
| 12 | `_has_commands_to_run` duplicated the loop's "does it run" rule | Yan's pick: one predicate; with it patched to always run, the suite goes red | `aa475d1` |
| 13 | `Runbook.shell` duplicated `shell_declarations[0]` and could disagree with it | Yan's pick: a read-only property | `e5a9c61` |
| 14 | This plan's Evidence paragraph cited bare filenames | Absolute paths, above | this section's commit |
| 15 | README counts with no command or tree | Counts removed; the audit command named, and it now exits 1 on a miss | `526586d` |

**Deviations.** Ubuntu under WSL has `python3` and no `python`; CI's `setup-python` provides `python`, which the fixtures call, so the WSL scripts put a `python` link to `python3` first on `PATH`. An inline `wsl.exe -- sh -c '...'` expanded `$PATH` in the Windows launcher, where "Program Files (x86)" broke the inner shell; the WSL commands are therefore passed as script files.

**Evidence**, second round:

- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\probe_codepages.py` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\probe_codepages-powershell.txt` — finding 10: from PowerShell, with the console at 65001, pwsh, Windows PowerShell and cmd all wrote UTF-8, while Python's default decoding is cp1252.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\mutate_executes.py` — finding 12: the suite with `_executes()` patched to always run (1 of 55 red).
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\wsl_tests.sh` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\wsl-full-suite.txt` — the whole suite on Linux (WSL Ubuntu, Python 3.12.3) at `526586d`: 57 run, 11 skipped, exit 0; the first run of this code on Linux.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\wsl_smoke.sh` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\wsl-smoke.txt` — CI's `smoke` job replayed step by step on Linux at `526586d`: 8 of 8 pass.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\accept-declared-second.txt` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\accept-original-second.txt` — Task 8 re-run on the second-reviewed code at `e75b3be`, with the tree committed first: the declared copy exits 0 with no `COMMAND_FAILED` at steps 1, 2 or 3 (its step 3 runs this suite through Git Bash); the original, the control, still fails at steps 1, 2 and 3 and exits 1.
- `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\suite-gitbash.txt` and `G:\Projects\runbook-dry-run\docs\plans\evidence\2026-11-03-second-review\suite-powershell.txt` — the suite at `e75b3be` launched from each shell: 57 run, 2 skipped, exit 0.
