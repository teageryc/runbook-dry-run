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
    r"^(Run \(destructive\)|Run|Path|Open|Click|On failure)\s*:\s*(.*)$"
)
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
}


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
    paths: list[str] = field(default_factory=list)
    elements: list[str] = field(default_factory=list)
    failure_branch: str | None = None


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

        if execute:
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

    return findings


def has_errors(findings: Iterable[Finding]) -> bool:
    return any(f.severity == SEVERITY_ERROR for f in findings)


def format_report(findings: Sequence[Finding], source: str) -> str:
    if not findings:
        return f"{source}: every step is followable ({0} findings)."
    lines = [f"{source}: {len(findings)} finding(s)."]
    lines.extend(str(f) for f in findings)
    return "\n".join(lines)
