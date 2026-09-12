"""Parse a runbook and report every step a human could not actually follow.

The unit of judgement is the STEP, never the document. A finding always names the
step it belongs to, because "this runbook has a broken path" is not actionable and
"step 3 names a path that does not resolve" is.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Iterable, Sequence

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
ELEMENTS_HEADING = re.compile(r"^Elements\s*:\s*$")
BULLET = re.compile(r"^[-*]\s+(.*?)\s*$")
BACKTICKED = re.compile(r"`([^`]+)`")

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


@dataclass
class Runbook:
    title: str = ""
    working_directory: str | None = None
    element_inventory: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)


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


def parse(text: str) -> Runbook:
    """Read a runbook into steps. Never raises on malformed input.

    A parser that throws turns a document defect into a tool defect, and the
    reader is then told nothing about the eleven steps that were fine.
    """
    book = Runbook()
    current: Step | None = None
    in_elements = False

    for raw in text.splitlines():
        line = raw.rstrip()

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

    return book


def _resolve(path: str, base: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(path))
    if os.path.isabs(expanded):
        return expanded
    return os.path.normpath(os.path.join(base, expanded))


def _run(command: str, cwd: str, timeout: float) -> tuple[int, str]:
    """Run one command and read its exit code UNPIPED.

    `returncode` is read off the completed process itself. Piping the command into
    anything - a pager, a formatter, `tee` - makes the pipeline's status the one
    you see, and a failing step then reports success.
    """
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:g}s"
    except OSError as exc:  # pragma: no cover - platform dependent
        return 127, str(exc)
    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return proc.returncode, detail[-1] if detail else ""


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

    base = base_dir or (declared if declared else os.getcwd())
    base = os.path.abspath(os.path.expanduser(os.path.expandvars(base)))

    inventory = {e.casefold() for e in book.element_inventory}
    step_numbers = {s.number for s in book.steps}

    for step in book.steps:
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
        if step.manual_gate_declared:
            if gate_defect is None and (step.commands or step.expect_fail_commands):
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
            code, detail = _run(command, base, timeout)
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
            code, detail = _run(expected.command, base, timeout)
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
