"""v0.4 mutation controls: each mutant must turn every test named for it red.

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/mutants.py

Windows only (mutants 5, 5b and 6 touch the console). Exit 0 only if every mutant
is killed; exit 2 if a named test fails unmutated (the control). Run from Git Bash:
mutant 6 is killable only from a console that starts in a page other than 65001.

Two kinds of mutant: an attribute of the checker module replaced, or the checker's
source edited at an anchor that must occur exactly once and run as the module.
Mutants A to K are the first review's surviving source mutants, re-made here.
"""

import contextlib
import os
import re
import sys
import types
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 4))
sys.path[:0] = [REPO, os.path.join(REPO, "tests")]
os.chdir(REPO)
import runbook_dry_run  # noqa: E402
import runbook_dry_run.checker as checker  # noqa: E402
import test_checker  # noqa: E402

SOURCE_PATH = os.path.join(REPO, "runbook_dry_run", "checker.py")
with open(SOURCE_PATH, encoding="utf-8") as handle:
    SOURCE = handle.read()
BOUND = ["FINDING_CODES", "Launcher", "Runbook", "Step", "check", "has_errors", "parse",
         "resolve_shell", "_git_bash"]


@contextlib.contextmanager
def attribute(name, value):
    original = getattr(checker, name)
    setattr(checker, name, value)
    try:
        yield
    finally:
        setattr(checker, name, original)


@contextlib.contextmanager
def source(*replacements):
    text = SOURCE
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"mutation anchor occurs {text.count(old)} times: {old[:70]!r}")
        text = text.replace(old, new)
    module = types.ModuleType("runbook_dry_run.checker")
    module.__file__ = SOURCE_PATH
    module.__package__ = "runbook_dry_run"
    sys.modules["runbook_dry_run.checker"] = module
    runbook_dry_run.checker = module  # mock.patch("runbook_dry_run.checker.x") must hit it
    saved = {name: getattr(test_checker, name) for name in BOUND}
    try:
        exec(compile(text, SOURCE_PATH, "exec"), module.__dict__)
        for name in BOUND:
            setattr(test_checker, name, getattr(module, name))
        yield
    finally:
        sys.modules["runbook_dry_run.checker"] = checker
        runbook_dry_run.checker = checker
        for name, value in saved.items():
            setattr(test_checker, name, value)


def opens_any_fence(line):
    match = checker.FENCE_OPEN.match(line)
    return match.group(1) if match else None


def opens_without_backticks_in_any_info(line):
    match = checker.FENCE_OPEN.match(line)
    return None if not match or "`" in match.group(2) else match.group(1)


def closes_only_at_equal_length(line, fence):
    match = checker.FENCE_CLOSE.match(line)
    return bool(match) and match.group(1)[0] == fence[0] and len(match.group(1)) == len(fence)


@contextlib.contextmanager
def keep_the_output_page_only():
    """The plan's first design: chcp.com, which reports the input page, still moved."""
    kernel32 = checker._windows_api()[0]
    page = kernel32.GetConsoleOutputCP()
    try:
        yield
    finally:
        kernel32.SetConsoleOutputCP(page)


ORIGINAL_RUN = checker._run


def run_resetting_the_pages_each_command(*args, **kwargs):
    with checker._console_pages_kept():
        return ORIGINAL_RUN(*args, **kwargs)


FC, FF, UF, DL, CP = ("test_checker." + c + "." for c in (
    "FencedCode", "FencedCodeFindings", "UnclosedFenceStopsCommands",
    "DocumentLinesInsideAStep", "ConsoleCodePage"))
MUTANTS = [
    ("1 any fence closes any fence",
     lambda: attribute("_closes_fence", lambda line, fence: bool(checker.FENCE_CLOSE.match(line))),
     [FC + "test_a_shorter_or_different_fence_does_not_close_it"]),
    ("2 a one-line code span opens a fence", lambda: attribute("_opens_fence", opens_any_fence),
     [FC + "test_a_one_line_code_span_is_not_a_fence"]),
    ("3 nothing the fence hid is reported", lambda: attribute("_fence_findings", lambda *a: []),
     [FF + "test_a_fenced_run_is_never_executed_and_the_unfenced_one_is",
      FF + "test_an_unclosed_fence_is_an_error_at_the_step_where_it_opened",
      FF + "test_a_fenced_shell_line_inside_a_step_no_longer_refuses_the_document"]),
    ("4 a misplaced working directory lets commands run",
     lambda: attribute("_misplaces_directory", lambda book: False),
     [DL + "test_a_working_directory_inside_a_step_stops_every_command"]),
    ("5 the console pages are not kept",
     lambda: attribute("_console_pages_kept", contextlib.nullcontext),
     [CP + "test_a_chcp_in_a_command_does_not_outlive_the_check"]),
    ("5b only the output page is kept",
     lambda: attribute("_console_pages_kept", keep_the_output_page_only),
     [CP + "test_a_chcp_in_a_command_does_not_outlive_the_check"]),
    ("6 the pages are reset after each command",
     lambda: attribute("_run", run_resetting_the_pages_each_command),
     [CP + "test_within_the_run_the_new_page_carries_to_the_next_command"]),
    ("7 an unclosed fence lets commands run",
     lambda: attribute("_has_unclosed_fence", lambda book: False),
     [UF + "test_an_unclosed_fence_stops_every_command",
      UF + "test_a_fence_left_open_in_a_list_item_runs_neither_command"]),
    ("8 a fence closes before a non-breaking space",
     lambda: source(('fence_line = raw.rstrip(" \\t")', "fence_line = raw.rstrip()")),
     [FC + "test_a_non_breaking_space_after_a_fence_means_it_does_not_close"]),
    ("9 lines split on every Unicode line break",
     lambda: source(("LINE_ENDING.split(text)", "text.splitlines()")),
     [FC + "test_only_commonmark_line_endings_split_lines"]),
    ("A a fence opens at any indentation",
     lambda: attribute("FENCE_OPEN", re.compile(r"^\s*(`{3,}|~{3,})(.*)$")),
     [FC + "test_a_four_space_indented_fence_is_not_a_fence"]),
    ("H a fence closes at any indentation",
     lambda: attribute("FENCE_CLOSE", re.compile(r"^\s*(`{3,}|~{3,})$")),
     [FC + "test_a_four_space_indented_closer_does_not_close"]),
    ("B a fence line with text after it closes",
     lambda: attribute("FENCE_CLOSE", re.compile(r"^ {0,3}(`{3,}|~{3,})")),
     [FC + "test_a_fence_line_with_an_info_string_does_not_close"]),
    ("C only an equally long fence closes",
     lambda: attribute("_closes_fence", closes_only_at_equal_length),
     [FC + "test_a_longer_closing_fence_closes"]),
    ("E the backtick rule applies to tilde fences",
     lambda: attribute("_opens_fence", opens_without_backticks_in_any_info),
     [FC + "test_a_tilde_fence_may_have_backticks_in_its_info_string"]),
    ("F a fence does not end the Elements inventory",
     lambda: source(("            fence, fence_opened = opened, SourceLine(number, line)\n"
                     "            in_elements = False\n",
                     "            fence, fence_opened = opened, SourceLine(number, line)\n")),
     [FC + "test_a_fence_ends_the_elements_inventory"]),
    ("I a fenced Elements: is not recorded",
     lambda: attribute("_READ_LINES", (checker.STEP_HEADING, checker.DIRECTIVE,
                                       checker.WORKING_DIRECTORY, checker.SHELL_LINE)),
     [FC + "test_a_fenced_elements_heading_is_recorded"]),
    ("D fenced lines before the first step are not reported",
     lambda: source(("            )\n        )\n"
                     "    findings.extend(_fence_findings(0, \"\", book.fenced_lines, book.unclosed_fence))\n",
                     "            )\n        )\n")),
     [FF + "test_fenced_lines_before_the_first_step_are_reported_at_the_document"]),
    ("G a misplaced working directory stops only its own step",
     lambda: source(
         ("bool(misplaced_shell) or _misplaces_directory(book) or _has_unclosed_fence(book)",
          "bool(misplaced_shell) or _has_unclosed_fence(book)"),
         ("        if not execute:\n            continue\n",
          "        if not execute or any(WORKING_DIRECTORY.match(m.text) for m in step.misplaced_lines):\n"
          "            continue\n")),
     [DL + "test_a_misplaced_working_directory_stops_commands_in_other_steps_too"]),
    ("K a working directory after a command is not caught",
     lambda: source(("        if WORKING_DIRECTORY.match(line) or ELEMENTS_HEADING.match(line):\n",
                     "        if (WORKING_DIRECTORY.match(line) or ELEMENTS_HEADING.match(line))"
                     " and not current.commands:\n")),
     [DL + "test_a_working_directory_after_a_command_is_still_caught"]),
    ("J the shell is asked for despite a misplaced working directory",
     lambda: source(("elif execute and not refuse_commands and _has_commands_to_run(book):",
                     "elif execute and not misplaced_shell and _has_commands_to_run(book):")),
     [DL + "test_a_misplaced_working_directory_never_asks_for_the_shell"]),
]


def run(names):
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    with open(os.devnull, "w") as sink:
        return unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)


print(f"console output page at start: {checker._windows_api()[0].GetConsoleOutputCP()}")
every_test = sorted({name for _, _, names in MUTANTS for name in names})
control = run(every_test)
if control.failures or control.errors or control.skipped:
    print(f"CONTROL FAILED: {len(control.failures)} failures, {len(control.errors)} errors, "
          f"{len(control.skipped)} skipped of {control.testsRun} unmutated tests")
    sys.exit(2)
print(f"control: {control.testsRun} named tests pass unmutated")

survivors = []
for name, mutate, tests in MUTANTS:
    with mutate():
        result = run(tests)
    red = len(result.failures) + len(result.errors)
    killed = red == len(tests) and not result.skipped
    print(f"{'killed' if killed else 'SURVIVED'}: {name} ({red} of {len(tests)} red, "
          f"{len(result.skipped)} skipped)")
    if not killed:
        survivors.append(name)
sys.exit(1 if survivors else 0)
