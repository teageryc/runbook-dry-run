"""Parse a runbook and report every step a human could not actually follow.

The unit of judgement is the STEP, never the document. A finding always names the
step it belongs to, because "this runbook has a broken path" is not actionable and
"step 3 names a path that does not resolve" is.
"""

from __future__ import annotations

import codecs
import contextlib
import functools
import locale
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Iterable, Iterator, NamedTuple, Sequence

SEVERITY_ERROR = "error"
SEVERITY_INFO = "info"

STEP_HEADING = re.compile(r"^##\s+Step\s+(\d+)\s*(?:[—–-]\s*)?(.*?)\s*$")
DIRECTIVE = re.compile(
    r"^(Run \(destructive\)|Run \(expect-fail(?:\s*:\s*\d+)?\)|Run|Path|Open|Click"
    r"|On failure|After manual step)\s*:\s*(.*)$"
)
EXPECT_FAIL_KEY = re.compile(r"^Run \(expect-fail(?:\s*:\s*(\d+))?\)$")
STEP_REFERENCE = re.compile(r"(\d+)")
WORKING_DIRECTORY = re.compile(r"^Working directory\s*:\s*(.*)$")
SHELL_LINE = re.compile(r"^Shell\s*:\s*(.*)$")
ELEMENTS_HEADING = re.compile(r"^Elements\s*:\s*$")
BULLET = re.compile(r"^[-*]\s+(.*?)\s*$")
BACKTICKED = re.compile(r"`([^`]+)`")
# CommonMark fenced code: up to three spaces, then three or more backticks or
# tildes. The closing fence uses the same character, is at least as long, and has
# nothing after it. A backtick fence's info string may not hold a backtick, so
# ```x``` on one line is inline code, not a fence that runs to the end.
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})$")

# `Shell:` names as a reader writes them (matched case-insensitively), mapped to
# the shell each one means. The single source for the names the tool accepts.
SHELL_NAMES = {
    "bash": "bash",
    "Git Bash": "bash",
    "pwsh": "pwsh",
    "powershell": "powershell",
    "cmd": "cmd",
}
_SHELL_KEYS = {name.casefold(): shell for name, shell in SHELL_NAMES.items()}
KNOWN_SHELLS = ", ".join(SHELL_NAMES)
POWERSHELL_FLAGS = ("-NoProfile", "-NonInteractive", "-Command")
COMMAND_VARIABLE = "RUNBOOK_DRY_RUN_COMMAND"
GIT_PROBE_TIMEOUT = 30.0

# Documented in docs/specs/2026-09-12-runbook-dry-run-design.md, section 4.
FINDING_CODES = {
    "MISSING_WORKING_DIRECTORY": "the document never says where the reader should stand",
    "NO_STEPS": "the document declares no steps",
    "NO_FAILURE_BRANCH": "the step does not say what to do when it fails",
    "PATH_UNRESOLVED": "the step names a path that does not resolve",
    "UI_ELEMENT_MISSING": "the step names a screen or control absent from the inventory",
    "COMMAND_FAILED": "the step's command exited non-zero",
    "COMMAND_SKIPPED_DESTRUCTIVE": "the step is marked destructive and was not executed",
    "EXPECTED_FAILURE_NOT_OBSERVED": "the step declared its command would fail and it did not",
    "COMMAND_DEFERRED_MANUAL_GATE": "the step waits on a human and its commands were not executed",
    "MANUAL_GATE_UNRESOLVED": "the step waits on a step that does not exist or does not precede it",
    "SHELL_UNRESOLVED": (
        "the document's Shell: cannot be used - a name this tool does not know, a Shell: line "
        "inside a step, two lines naming different shells, or, when a command would run, "
        "a shell this machine does not have; no command in the document is executed"
    ),
    "FENCED_LINE_SKIPPED": (
        "a line the parser would read sits inside fenced code, so it was not read"
    ),
    "FENCE_UNCLOSED": "a code fence never closes, so nothing after it was checked",
}


@dataclass(frozen=True)
class ExpectedFailure:
    """A command whose success condition is a non-zero exit.

    `exit_code` of None means any non-zero satisfies the step. A specific code is
    the stronger declaration and usually the right one: a probe that fails because
    the network is down also exits non-zero, and proves nothing about the thing
    being probed.
    """

    command: str
    exit_code: int | None = None


@dataclass(frozen=True)
class Finding:
    """One defect, anchored to the step a reader would be standing on."""

    step: int
    step_title: str
    code: str
    detail: str
    severity: str = SEVERITY_ERROR

    def __str__(self) -> str:
        where = f"step {self.step}" if self.step else "document"
        title = f" ({self.step_title})" if self.step_title else ""
        return f"[{self.severity}] {where}{title}: {self.code} - {self.detail}"


class SourceLine(NamedTuple):
    """A line of the document: its 1-based number and its text, right-stripped."""

    number: int
    text: str


@dataclass
class Step:
    number: int
    title: str
    commands: list[str] = field(default_factory=list)
    destructive_commands: list[str] = field(default_factory=list)
    expect_fail_commands: list[ExpectedFailure] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    elements: list[str] = field(default_factory=list)
    failure_branch: str | None = None
    manual_gate: int | None = None
    manual_gate_declared: bool = False
    # Fields added after 0.3 go below this line: Step is public API, and a field
    # inserted above shifts every positional argument written against 0.3.
    fenced_lines: list[SourceLine] = field(default_factory=list)
    unclosed_fence: SourceLine | None = None


@dataclass(frozen=True)
class Launcher:
    """How a command reaches the shell it was written for.

    An empty `argv` means the platform default through `shell=True`, which on
    Windows is cmd.exe. With `via_environment`, the command is handed over in
    COMMAND_VARIABLE instead of as an argument: Windows re-parses a command line by
    MSVC rules and Git Bash's runtime by its own, so a backslash pair before a
    quote arrived halved. An environment variable is never re-parsed.

    `encoding` is how the shell's output is decoded. None means the console's
    output code page on Windows, which cmd.exe and PowerShell write in, and the
    locale's elsewhere. Git Bash writes UTF-8 whatever the console says.
    """

    argv: tuple[str, ...] = ()
    via_environment: bool = False
    encoding: str | None = None


@dataclass
class Runbook:
    title: str = ""
    working_directory: str | None = None
    element_inventory: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    # Fields added after 0.2 go below this line: Runbook is public API, and a field
    # inserted above shifts every positional argument written against 0.2.
    shell_declarations: list[str] = field(default_factory=list)
    shell_in_steps: list[int] = field(default_factory=list)
    fenced_lines: list[SourceLine] = field(default_factory=list)
    unclosed_fence: SourceLine | None = None

    @property
    def shell(self) -> str | None:
        """The shell the document declares: its first `Shell:` line, or None.

        Read-only and derived, so it cannot disagree with `shell_declarations`.
        """
        return self.shell_declarations[0] if self.shell_declarations else None


def _first_backticked(value: str) -> str:
    """Take the backticked token if there is one, else the whole line.

    A runbook written for humans marks its literals with backticks. One written in
    a hurry does not, and refusing to read those would make the tool useless on
    exactly the documents that need it most.
    """
    match = BACKTICKED.search(value)
    return match.group(1).strip() if match else value.strip()


def _all_backticked(value: str) -> list[str]:
    found = [m.strip() for m in BACKTICKED.findall(value)]
    return found if found else ([value.strip()] if value.strip() else [])


_READ_LINES = (STEP_HEADING, DIRECTIVE, WORKING_DIRECTORY, SHELL_LINE, ELEMENTS_HEADING)


def _opens_fence(line: str) -> str | None:
    """The fence this line opens, or None."""
    match = FENCE_OPEN.match(line)
    if not match:
        return None
    fence, info = match.group(1), match.group(2)
    if fence[0] == "`" and "`" in info:
        return None
    return fence


def _closes_fence(line: str, fence: str) -> bool:
    match = FENCE_CLOSE.match(line)
    return bool(match) and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence)


def _would_be_read(line: str) -> bool:
    """Whether the parser acts on this line when it is not inside a fence."""
    return any(shape.match(line) for shape in _READ_LINES)


def parse(text: str) -> Runbook:
    """Read a runbook into steps. Never raises on malformed input.

    A parser that throws turns a document defect into a tool defect, and the
    reader is then told nothing about the eleven steps that were fine.

    A line inside fenced code is an example, never an instruction (v0.4): before
    it, a fenced `Run:` example was a command that --execute ran. Each fenced line
    that would otherwise be read is recorded, so check() can say what it skipped.
    """
    book = Runbook()
    current: Step | None = None
    in_elements = False
    fence: str | None = None
    fence_opened: SourceLine | None = None

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()

        if fence is not None:
            if _closes_fence(line, fence):
                fence = None
            elif _would_be_read(line):
                owner = current.fenced_lines if current is not None else book.fenced_lines
                owner.append(SourceLine(number, line))
            continue

        opened = _opens_fence(line)
        if opened is not None:
            fence, fence_opened = opened, SourceLine(number, line)
            in_elements = False
            continue

        heading = STEP_HEADING.match(line)
        if heading:
            in_elements = False
            current = Step(number=int(heading.group(1)), title=heading.group(2))
            book.steps.append(current)
            continue

        if current is None:
            if line.startswith("# ") and not book.title:
                book.title = line[2:].strip()
                continue
            wd = WORKING_DIRECTORY.match(line)
            if wd:
                book.working_directory = _first_backticked(wd.group(1))
                in_elements = False
                continue
            shell = SHELL_LINE.match(line)
            if shell:
                declared = _first_backticked(shell.group(1))
                book.shell_declarations.append(declared)
                in_elements = False
                continue
            if ELEMENTS_HEADING.match(line):
                in_elements = True
                continue
            if in_elements:
                bullet = BULLET.match(line)
                if bullet:
                    book.element_inventory.append(_first_backticked(bullet.group(1)))
                elif line.strip():
                    in_elements = False
            continue

        if SHELL_LINE.match(line):
            # Recorded so check() can refuse it out loud: dropped silently, it would
            # leave a bash runbook running in the platform default.
            book.shell_in_steps.append(current.number)
            continue

        directive = DIRECTIVE.match(line)
        if not directive:
            continue
        key, value = directive.group(1), directive.group(2)
        if key == "Run":
            current.commands.append(_first_backticked(value))
        elif key == "Run (destructive)":
            current.destructive_commands.append(_first_backticked(value))
        elif key == "Path":
            current.paths.extend(_all_backticked(value))
        elif key in ("Open", "Click"):
            current.elements.extend(_all_backticked(value))
        elif key == "On failure":
            current.failure_branch = value.strip()
        elif key == "After manual step":
            current.manual_gate_declared = True
            reference = STEP_REFERENCE.search(value)
            current.manual_gate = int(reference.group(1)) if reference else None
        else:
            expect_fail = EXPECT_FAIL_KEY.match(key)
            if expect_fail:
                declared = expect_fail.group(1)
                current.expect_fail_commands.append(
                    ExpectedFailure(
                        _first_backticked(value),
                        int(declared) if declared is not None else None,
                    )
                )

    if fence is not None:
        # An unclosed fence runs to the end, as a renderer shows it. Headings inside
        # it are skipped, so `current` is still the step where it opened.
        if current is None:
            book.unclosed_fence = fence_opened
        else:
            current.unclosed_fence = fence_opened

    return book


def _resolve(path: str, base: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(path))
    if os.path.isabs(expanded):
        return expanded
    return os.path.normpath(os.path.join(base, expanded))


def _on_path(name: str) -> str | None:
    """Find a program on PATH, and only on PATH.

    shutil.which on Windows searches the current directory first, so a `git.bat`
    planted wherever the checker is run would be chosen - and git, which shell
    resolution executes, would run it. Only absolute PATH entries are searched.
    """
    if sys.platform == "win32":
        extensions = [e for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
    else:
        extensions = [""]
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry or not os.path.isabs(entry):
            continue
        for extension in extensions:
            candidate = os.path.join(entry, name + extension)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def _git_bash() -> tuple[str | None, str]:
    """Find Git Bash through git's own installation, never through PATH.

    On Windows, PATH answers `bash` with the WSL launcher (System32 or the
    WindowsApps alias), which runs the command under Linux with Linux paths: a
    third shell, chosen silently. git's exec path sits a few levels below the
    installation's bin/bash.exe, which is what "Git Bash" means.
    """
    git = _on_path("git")
    if git is None:
        return None, "Git Bash is looked for through git's installation, and git is not on PATH"
    try:
        probe = subprocess.Popen(
            [git, "--exec-path"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
    except (OSError, ValueError) as exc:
        return None, f"git --exec-path did not start: {exc}"
    try:
        raw, _ = probe.communicate(timeout=GIT_PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        # Bounded twice: a git that is really a wrapper can leave a child holding
        # the pipe after it is killed, and an unbounded read would wait for it.
        probe.kill()
        try:
            probe.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        return None, f"git --exec-path did not answer within {GIT_PROBE_TIMEOUT:g}s"
    # git prints its path in UTF-8; the ANSI code page cannot decode every one.
    try:
        start = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        start = raw.decode(locale.getpreferredencoding(False), errors="replace").strip()
    if probe.returncode != 0:
        return None, f"git --exec-path exited {probe.returncode}"
    if not start:
        return None, "git --exec-path printed nothing"
    directory = os.path.normpath(start)
    for _ in range(4):
        candidate = os.path.join(directory, "bin", "bash.exe")
        if os.path.isfile(candidate):
            return candidate, ""
        directory = os.path.dirname(directory)
    return None, f"no bin/bash.exe in git's exec path {start} or the three directories above it"


def _shell_of(declared: str) -> str | None:
    """The shell a `Shell:` name means, or None for a name this tool does not know."""
    return _SHELL_KEYS.get(declared.strip().casefold())


def _unknown_shell(declared: str) -> str:
    return f"{declared.strip()!r} is not a shell this tool knows ({KNOWN_SHELLS})"


def _has_runnable_commands(step: Step) -> bool:
    """Run: and expect-fail commands; destructive ones never run anywhere."""
    return bool(step.commands or step.expect_fail_commands)


def _executes(step: Step) -> bool:
    """Whether --execute runs the step's commands: a gated step's never run.

    The single rule for both check()'s loop and the decision to resolve a shell,
    so the two cannot drift apart.
    """
    return not step.manual_gate_declared


def _has_commands_to_run(book: Runbook) -> bool:
    """Whether --execute would run anything."""
    return any(_executes(step) and _has_runnable_commands(step) for step in book.steps)


def resolve_shell(declared: str) -> tuple[Launcher | None, str]:
    """Turn a `Shell:` name into the Launcher that runs a command in that shell.

    Returns (launcher, "") when the shell is usable here and (None, reason) when
    it is not. Every shell has its own branch; nothing falls through to another
    shell's arguments.
    """
    name = declared.strip()
    shell = _shell_of(name)
    if shell is None:
        return None, _unknown_shell(name)
    windows = sys.platform == "win32"
    if shell == "cmd":
        return (Launcher(), "") if windows else (None, "cmd exists only on Windows")
    if shell == "bash":
        if windows:
            found, problem = _git_bash()
        else:
            found = _on_path("bash")
            problem = "" if found else "bash is not on PATH"
        if found is None:
            return None, problem
        argv = (found, "-c", f'eval "${COMMAND_VARIABLE}"')
        return Launcher(argv, via_environment=True, encoding="utf-8"), ""
    if shell in ("pwsh", "powershell"):
        if shell == "powershell" and not windows:
            return None, "powershell (Windows PowerShell) exists only on Windows; declare pwsh"
        found = _on_path(shell)
        if found is None:
            return None, f"{shell} is not on PATH"
        return Launcher((found, *POWERSHELL_FLAGS)), ""
    return None, f"{name!r} names a shell with no launcher defined"


def _run(
    command: str, cwd: str, timeout: float, launcher: Launcher = Launcher()
) -> tuple[int, str]:
    """Run one command and read its exit code UNPIPED.

    `returncode` is read off the completed process itself. Piping the command into
    anything - a pager, a formatter, `tee` - makes the pipeline's status the one
    you see, and a failing step then reports success.

    With a launcher, the declared shell runs the command; without one, the
    platform default does, exactly as before v0.3.
    """
    env = None
    if not launcher.argv:
        args: str | list[str] = command
    elif launcher.via_environment:
        args = list(launcher.argv)
        env = {**os.environ, COMMAND_VARIABLE: command}
    else:
        args = [*launcher.argv, command]
    # Windows: a timeout must stop everything the command started, not only its
    # first process. Git Bash's bin/bash.exe is a launcher whose real bash is a
    # second process, and cmd.exe may start the program that holds the output
    # pipes; reading those pipes waits for the whole tree, so a command that never
    # ended hung the checker. The command starts suspended inside a Job Object,
    # which also holds every process it starts later - even when an intermediate
    # MSYS process has exited and broken the parent chain, which defeats any walk
    # by parent id.
    # POSIX: the command stays in the checker's own session and process group, as
    # in v0.2, so a terminal prompt and Ctrl+C still reach it. The hang never
    # happened there: after a kill, only the process is waited for, not the pipes.
    job = _new_job() if sys.platform == "win32" else None
    platform = {"creationflags": _CREATE_SUSPENDED} if sys.platform == "win32" else {}
    try:
        proc = subprocess.Popen(
            args,
            shell=not launcher.argv,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=launcher.encoding or _console_encoding(),
            errors="replace",
            **platform,
        )
    except (OSError, ValueError) as exc:
        # ValueError: a NUL byte in the command or its environment, which no
        # operating system will start. A defect in the document, not in the tool.
        _close_job(job)
        return 127, str(exc)
    if sys.platform == "win32":
        job = _assign_and_resume(job, proc)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc, job)
        _reap(proc)
        return 124, f"timed out after {timeout:g}s"
    except BaseException:
        # subprocess.run, which this replaced, kills the command on any exception:
        # an interrupted checker must not leave it running unreported.
        _kill_tree(proc, job)
        _reap(proc)
        raise
    finally:
        _close_job(job)
    detail = (stderr or stdout or "").strip().splitlines()
    return proc.returncode, detail[-1] if detail else ""


_CREATE_SUSPENDED = 0x00000004


@functools.lru_cache(maxsize=None)
def _windows_api():
    """kernel32 and ntdll entry points for Job Objects. Windows only."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.GetConsoleOutputCP.restype = wintypes.UINT
    kernel32.GetConsoleOutputCP.argtypes = []
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    return kernel32, ntdll


def _console_encoding() -> str | None:
    """How cmd.exe and PowerShell write into a pipe: the console's output code page.

    It is not the ANSI code page Python decodes with by default, and it depends on
    where the checker was started: measured 65001 under one shell and 437 under
    another, against Python's cp1252. A checker with no console gives its child a
    new one, in the OEM code page. None (the locale's) everywhere but Windows.
    """
    if sys.platform != "win32":
        return None
    page = _windows_api()[0].GetConsoleOutputCP()
    encoding = f"cp{page}" if page else "oem"
    try:
        codecs.lookup(encoding)
    except LookupError:
        return None
    return encoding


def _new_job():
    return _windows_api()[0].CreateJobObjectW(None, None) or None


def _close_job(job) -> None:
    if job is not None:
        _windows_api()[0].CloseHandle(job)


def _assign_and_resume(job, proc: subprocess.Popen):
    """Put the suspended command in the job, then let it run.

    Assigned while suspended, so nothing it starts can escape the job. If the
    assignment fails, the command still runs and a timeout falls back to killing
    only its first process (recorded in LIMITS.md).
    """
    kernel32, ntdll = _windows_api()
    handle = int(proc._handle)  # CPython's process handle for the child
    if job is not None and not kernel32.AssignProcessToJobObject(job, handle):
        _close_job(job)
        job = None
    ntdll.NtResumeProcess(handle)
    return job


def _kill_tree(proc: subprocess.Popen, job) -> None:
    """Kill a command: on Windows with everything it started, elsewhere its first process."""
    if job is not None:
        _windows_api()[0].TerminateJobObject(job, 1)
    proc.kill()


def _reap(proc: subprocess.Popen) -> None:
    """Collect a killed command without waiting long on anything it left behind.

    Windows: a read bounded at 10 s, for a program that escaped the job and still
    holds the pipes. POSIX: the process only, then the pipes are closed - what
    subprocess.run does, and why a timeout never hung there.
    """
    if sys.platform == "win32":
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - a tree that would not die
            pass
    else:
        proc.wait()
        for stream in (proc.stdout, proc.stderr):
            stream.close()


def _gate_defect(step: Step, step_numbers: set[int]) -> Finding | None:
    """Validate an `After manual step:` declaration.

    A gate that names nothing reachable silently disables execution of the step's
    commands for good - a check that stops checking without ever saying so, which
    fails in the direction that reports health. The step's commands are deferred
    either way, because the author's stated intent was that they not run yet.
    """
    if not step.manual_gate_declared:
        return None

    target = step.manual_gate
    if target is None:
        detail = "the step waits on a manual step but names no step number"
    elif target not in step_numbers:
        detail = f"the step waits on step {target}, which this document does not contain"
    elif target >= step.number:
        detail = (
            f"the step waits on step {target}, which does not come before "
            f"step {step.number}"
        )
    else:
        return None
    return Finding(step.number, step.title, "MANUAL_GATE_UNRESOLVED", detail)


def _fence_findings(
    number: int, title: str, fenced: list[SourceLine], unclosed: SourceLine | None
) -> list[Finding]:
    """What fenced code hid: an unclosed fence (error), then each skipped line (info)."""
    found = []
    if unclosed is not None:
        found.append(
            Finding(
                number,
                title,
                "FENCE_UNCLOSED",
                f"the code fence opened at line {unclosed.number} never closes, so every "
                "line after it is code and nothing after it was checked",
            )
        )
    for skipped in fenced:
        found.append(
            Finding(
                number,
                title,
                "FENCED_LINE_SKIPPED",
                f"line {skipped.number} is inside fenced code and was not read: "
                f"{skipped.text.strip()}",
                severity=SEVERITY_INFO,
            )
        )
    return found


def check(
    book: Runbook,
    base_dir: str | None = None,
    execute: bool = False,
    timeout: float = 60.0,
) -> list[Finding]:
    """Return every finding, in step order. An empty list means every step is followable."""
    findings: list[Finding] = []

    if not book.steps:
        findings.append(Finding(0, "", "NO_STEPS", "the document declares no steps"))
        findings.extend(_fence_findings(0, "", book.fenced_lines, book.unclosed_fence))
        return findings

    declared = book.working_directory
    if declared is None:
        findings.append(
            Finding(
                0,
                "",
                "MISSING_WORKING_DIRECTORY",
                "no 'Working directory:' line, so no path in this document can be resolved",
            )
        )
    findings.extend(_fence_findings(0, "", book.fenced_lines, book.unclosed_fence))

    # Every SHELL_UNRESOLVED stops all execution: falling back to the platform
    # default is the behaviour that produced three COMMAND_FAILED findings that
    # were not defects (spec section 8).
    launcher = Launcher()
    misplaced_shell = set(book.shell_in_steps)
    shell_problem: str | None = None
    declared_shells = {_shell_of(d) or d.strip().casefold() for d in book.shell_declarations}
    if len(declared_shells) > 1:
        names = ", ".join(book.shell_declarations)
        shell_problem = f"Shell: is declared more than once with different shells ({names})"
    elif book.shell is not None:
        if _shell_of(book.shell) is None:
            # A name the tool does not know is a defect in the document, on any machine.
            shell_problem = _unknown_shell(book.shell)
        elif execute and not misplaced_shell and _has_commands_to_run(book):
            # Whether the shell exists is a fact about THIS machine, which is not the
            # reader's; it is asked only when a command is about to run here.
            resolved_shell, problem = resolve_shell(book.shell)
            if resolved_shell is None:
                shell_problem = problem
            else:
                launcher = resolved_shell
    if shell_problem is not None:
        findings.append(
            Finding(
                0,
                "",
                "SHELL_UNRESOLVED",
                f"{shell_problem}, so no command in this document was executed",
            )
        )
        execute = False
    if misplaced_shell:
        execute = False

    base = base_dir or (declared if declared else os.getcwd())
    base = os.path.abspath(os.path.expanduser(os.path.expandvars(base)))

    inventory = {e.casefold() for e in book.element_inventory}
    step_numbers = {s.number for s in book.steps}

    for step in book.steps:
        if step.number in misplaced_shell:
            findings.append(
                Finding(
                    step.number,
                    step.title,
                    "SHELL_UNRESOLVED",
                    "a Shell: line inside a step is not read; it belongs before the "
                    "first step, so no command in this document was executed",
                )
            )
        findings.extend(
            _fence_findings(step.number, step.title, step.fenced_lines, step.unclosed_fence)
        )

        if not step.failure_branch:
            findings.append(
                Finding(
                    step.number,
                    step.title,
                    "NO_FAILURE_BRANCH",
                    "the step never says what the reader should do when it fails",
                )
            )

        gate_defect = _gate_defect(step, step_numbers)
        if gate_defect is not None:
            findings.append(gate_defect)

        for path in step.paths:
            resolved = _resolve(path, base)
            if not os.path.exists(resolved):
                findings.append(
                    Finding(
                        step.number,
                        step.title,
                        "PATH_UNRESOLVED",
                        f"{path} does not resolve from {base} (tried {resolved})",
                    )
                )

        for element in step.elements:
            if element.casefold() not in inventory:
                findings.append(
                    Finding(
                        step.number,
                        step.title,
                        "UI_ELEMENT_MISSING",
                        f"{element!r} is not in the Elements inventory",
                    )
                )

        for command in step.destructive_commands:
            findings.append(
                Finding(
                    step.number,
                    step.title,
                    "COMMAND_SKIPPED_DESTRUCTIVE",
                    f"marked destructive and not executed: {command}",
                    severity=SEVERITY_INFO,
                )
            )

        if not execute:
            continue

        # A gated step's commands are not run, because the thing they depend on is
        # a human act this check cannot perform and cannot observe. Running them
        # anyway would report a failure that is not a defect in the procedure, and
        # a finding that is noise is a finding readers learn to silence.
        if not _executes(step):
            if gate_defect is None and _has_runnable_commands(step):
                findings.append(
                    Finding(
                        step.number,
                        step.title,
                        "COMMAND_DEFERRED_MANUAL_GATE",
                        f"not executed: this step waits on step {step.manual_gate}, "
                        "which a human completes and this check cannot observe",
                        severity=SEVERITY_INFO,
                    )
                )
            continue

        for command in step.commands:
            code, detail = _run(command, base, timeout, launcher)
            if code != 0:
                suffix = f": {detail}" if detail else ""
                findings.append(
                    Finding(
                        step.number,
                        step.title,
                        "COMMAND_FAILED",
                        f"{command} exited {code}{suffix}",
                    )
                )

        for expected in step.expect_fail_commands:
            code, detail = _run(expected.command, base, timeout, launcher)
            if expected.exit_code is None:
                satisfied = code != 0
                declared = "a non-zero exit"
            else:
                satisfied = code == expected.exit_code
                declared = f"exit {expected.exit_code}"
            if not satisfied:
                suffix = f": {detail}" if detail else ""
                findings.append(
                    Finding(
                        step.number,
                        step.title,
                        "EXPECTED_FAILURE_NOT_OBSERVED",
                        f"{expected.command} exited {code}, and the step "
                        f"declared {declared}{suffix}",
                    )
                )

    return findings


def has_errors(findings: Iterable[Finding]) -> bool:
    return any(f.severity == SEVERITY_ERROR for f in findings)


def format_report(findings: Sequence[Finding], source: str) -> str:
    if not findings:
        return f"{source}: every step is followable ({0} findings)."
    lines = [f"{source}: {len(findings)} finding(s)."]
    lines.extend(str(f) for f in findings)
    return "\n".join(lines)
