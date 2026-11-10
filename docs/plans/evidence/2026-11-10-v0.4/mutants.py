"""v0.4 mutation controls: each mutant must turn every test named for it red.

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/mutants.py

Windows only (mutants 5, 5b and 6 touch the console). Exit 0 only if every mutant
is killed. Run from Git Bash: mutant 6 is killable only from a console that starts
in a page other than 65001.
"""

import contextlib
import os
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 4))
sys.path[:0] = [REPO, os.path.join(REPO, "tests")]
os.chdir(REPO)
import runbook_dry_run.checker as checker  # noqa: E402


def opens_any_fence(line):
    match = checker.FENCE_OPEN.match(line)
    return match.group(1) if match else None


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


T = "test_checker."
MUTANTS = [
    ("1 any fence closes any fence", "_closes_fence",
     lambda line, fence: bool(checker.FENCE_CLOSE.match(line)),
     [T + "FencedCode.test_a_shorter_or_different_fence_does_not_close_it"]),
    ("2 a one-line code span opens a fence", "_opens_fence", opens_any_fence,
     [T + "FencedCode.test_a_one_line_code_span_is_not_a_fence"]),
    ("3 nothing the fence hid is reported", "_fence_findings", lambda *args: [],
     [T + "FencedCodeFindings.test_a_fenced_run_is_never_executed_and_the_unfenced_one_is",
      T + "FencedCodeFindings.test_an_unclosed_fence_is_an_error_at_the_step_where_it_opened",
      T + "FencedCodeFindings.test_a_fenced_shell_line_inside_a_step_no_longer_refuses_the_document"]),
    ("4 a misplaced working directory lets commands run", "_misplaces_directory",
     lambda book: False,
     [T + "DocumentLinesInsideAStep.test_a_working_directory_inside_a_step_stops_every_command"]),
    ("5 the console pages are not kept", "_console_pages_kept", contextlib.nullcontext,
     [T + "ConsoleCodePage.test_a_chcp_in_a_command_does_not_outlive_the_check"]),
    ("5b only the output page is kept", "_console_pages_kept", keep_the_output_page_only,
     [T + "ConsoleCodePage.test_a_chcp_in_a_command_does_not_outlive_the_check"]),
    ("6 the pages are reset after each command", "_run", run_resetting_the_pages_each_command,
     [T + "ConsoleCodePage.test_within_the_run_the_new_page_carries_to_the_next_command"]),
]

print(f"console output page at start: {checker._windows_api()[0].GetConsoleOutputCP()}")
survivors = []
for name, attribute, replacement, tests in MUTANTS:
    original = getattr(checker, attribute)
    setattr(checker, attribute, replacement)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(tests)
        with open(os.devnull, "w") as sink:
            result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    finally:
        setattr(checker, attribute, original)
    red = len(result.failures) + len(result.errors)
    killed = red == len(tests) and not result.skipped
    print(f"{'killed' if killed else 'SURVIVED'}: {name} ({red} of {len(tests)} red, "
          f"{len(result.skipped)} skipped)")
    if not killed:
        survivors.append(name)
sys.exit(1 if survivors else 0)
