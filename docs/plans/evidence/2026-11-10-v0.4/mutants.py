"""v0.4 mutation controls: each mutant must make every test named for it FAIL.

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/mutants.py

Windows only (mutants 5, 5b and 6 touch the console). Exit 0 only if every mutant
is killed; exit 2 if the control fails. Run from Git Bash: mutant 6 is killable
only from a console that starts in a page other than 65001.

Two kinds of mutant: an attribute of a module replaced, or the checker's source
edited at an anchor that must occur exactly once and run as the module. The
control runs every named test unmutated twice: as imported, and through the
source path with no edit, so a break in that path cannot pass for a kill. Only
assertion failures count as kills; an error is reported as not killed.
Mutants A to K are the first review's surviving source mutants, re-made here.
Mutant 11 (strip spaces but not tabs) was dropped in v4: fence lines are
tab-expanded first, so it is equivalent and no test could kill it.
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
import runbook_dry_run.__main__ as cli  # noqa: E402
import runbook_dry_run.checker as checker  # noqa: E402
import test_checker  # noqa: E402

BS = chr(92)
SOURCE_PATH = os.path.join(REPO, "runbook_dry_run", "checker.py")
with open(SOURCE_PATH, encoding="utf-8") as handle:
    SOURCE = handle.read()
BOUND = ["FINDING_CODES", "Launcher", "Runbook", "Step", "check", "has_errors", "parse",
         "resolve_shell", "_git_bash"]


@contextlib.contextmanager
def attribute(name, value, module=checker):
    original = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, original)


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


def html_block_even_when_it_ends_on_its_line(line):
    return next((end for start, end in checker.HTML_BLOCKS if start.match(line)), None)


@contextlib.contextmanager
def keep_the_output_page_only():
    """The plan's first design: chcp.com, which reports the input page, still moved."""
    kernel32 = checker._windows_api()[0]
    page = kernel32.GetConsoleOutputCP()
    try:
        yield
    finally:
        kernel32.SetConsoleOutputCP(page)


@contextlib.contextmanager
def printable_regardless_and_never_restored():
    """The first fix of review finding 2: every stream switched, nothing put back."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    yield


ORIGINAL_RUN = checker._run


def write_without_escaping(text, stream=None):
    print(text, file=stream or sys.stdout)


def run_resetting_the_pages_each_command(*args, **kwargs):
    with checker._console_pages_kept():
        return ORIGINAL_RUN(*args, **kwargs)


STRIP_SPACES_AND_TABS = 'fence_line = physical.expandtabs(4).rstrip(" ' + BS + 't")'
FC, FF, UF, DL, CP, FI, CL, TR = ("test_checker." + c + "." for c in (
    "FencedCode", "FencedCodeFindings", "UnclosedFenceStopsCommands",
    "DocumentLinesInsideAStep", "ConsoleCodePage", "FencesInsideContainers",
    "CommandLineOutput", "ContainerEdgesThirdReview"))
MUTANTS = [
    ("1 any fence closes any fence",
     lambda: attribute("_closes_fence", lambda line, fence: bool(checker.FENCE_CLOSE.match(line))),
     [FC + "test_a_shorter_or_different_fence_does_not_close_it"]),
    ("2 a one-line code span opens a fence", lambda: attribute("_opens_fence", opens_any_fence),
     [FC + "test_a_one_line_code_span_is_not_a_fence"]),
    ("3 nothing the fence hid is reported", lambda: attribute("_fence_findings", lambda *a: []),
     [FF + "test_a_fenced_run_is_never_executed_and_the_unfenced_one_is",
      FF + "test_an_unclosed_fence_is_an_error_at_the_step_where_it_opened",
      FF + "test_a_fenced_shell_line_inside_a_step_no_longer_refuses_the_document",
      FI + "test_a_fence_closed_less_indented_than_its_opener_is_misaligned"]),
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
     [UF + "test_an_unclosed_fence_stops_every_command"]),
    ("8 a fence closes before a non-breaking space",
     lambda: source((STRIP_SPACES_AND_TABS, "fence_line = physical.expandtabs(4).rstrip()")),
     [FC + "test_a_non_breaking_space_after_a_fence_means_it_does_not_close"]),
    ("9 lines split on every Unicode line break",
     lambda: source(("LINE_ENDING.split(text)", "text.splitlines()")),
     [FC + "test_only_commonmark_line_endings_split_lines",
      FC + "test_a_fence_after_a_line_separator_is_not_a_fence"]),
    ("10 fence lines keep their trailing whitespace",
     lambda: source((STRIP_SPACES_AND_TABS, "fence_line = physical.expandtabs(4)")),
     [FC + "test_a_closing_fence_followed_by_spaces_or_a_tab_still_closes"]),
    ("12 a misaligned fence lets commands run",
     lambda: attribute("_has_misaligned_fence", lambda book: False),
     [FI + "test_e1_a_list_fence_left_open_then_an_open_example_runs_nothing",
      FI + "test_e2_a_list_fence_closed_at_column_0_runs_nothing"]),
    ("13 an indented fence ignores a line indented less",
     lambda: source(("            if fence is not None and not list_fence and fence_indent >= 2 and (\n",
                     "            if False and (\n")),
     [FI + "test_an_indented_fence_with_content_at_column_0_is_misaligned",
      FI + "test_a_fence_closed_less_indented_than_its_opener_is_misaligned",
      FI + "test_e2_a_list_fence_closed_at_column_0_runs_nothing",
      TR + "test_r1_list_fence_content_at_column_0_runs_nothing"]),
    ("14 a fence on a list-marker line is not a fence",
     lambda: attribute("LIST_FENCE_OPEN", re.compile(r"(?!)")),
     [FI + "test_f1_a_fence_opened_on_a_list_marker_line_is_a_fence",
      FI + "test_an_ordered_list_fence_closes_inside_its_item"]),
    ("15 a list item does not end its fence",
     lambda: source(("# it (CommonMark); the line itself is read below like any other.\n"
                     "            fence = None\n",
                     "# it (CommonMark); the line itself is read below like any other.\n"
                     "            pass\n")),
     [FI + "test_a_list_fence_ends_with_its_item"]),
    ("16 HTML blocks are not recognised", lambda: attribute("_html_block", lambda line: None),
     [FI + "test_e3_a_fence_line_inside_an_html_comment_is_not_a_fence",
      FI + "test_a_fence_line_inside_a_pre_block_is_not_a_fence"]),
    ("17 a one-line HTML comment opens a block",
     lambda: attribute("_html_block", html_block_even_when_it_ends_on_its_line),
     [FI + "test_a_one_line_html_comment_opens_no_block"]),
    ("18 a list item's lines are read from column 0",
     lambda: source(("inner = fence_line[fence_indent:] if list_fence else fence_line",
                     "inner = fence_line")),
     [FI + "test_a_wide_list_marker_reads_the_item_from_its_content_column"]),
    ("19 a page break before a heading hides the step",
     lambda: source(("for part in physical.splitlines() or [physical]:", "for part in [physical]:")),
     [FC + "test_a_form_feed_before_a_heading_still_starts_a_step"]),
    ("20 the output streams are switched and never put back",
     lambda: attribute("_printable_output", printable_regardless_and_never_restored, cli),
     [CL + "test_main_puts_the_streams_back"]),
    ("21 an HTML block ignores its list item's end",
     lambda: source(("            elif html_end is not None and html_indent >= 2 and "
                     "_indent(fence_line) < html_indent:\n", "            elif False:\n")),
     [TR + "test_r2b_a_pre_block_ended_by_its_list_item_runs_nothing"]),
    ("22 lines inside an HTML block are read",
     lambda: source(("                owner.fenced_lines.append(SourceLine(number, line))\n"
                     "            continue\n\n        html_end = _html_block(fence_line)\n",
                     "                owner.fenced_lines.append(SourceLine(number, line))\n\n"
                     "        html_end = _html_block(fence_line)\n")),
     [TR + "test_r6_a_command_inside_a_pre_block_is_not_read",
      TR + "test_a_command_inside_an_html_comment_is_not_read"]),
    ("23 an HTML block that never closes does not refuse",
     lambda: source(("    if fence is not None or html_end is not None:\n", "    if fence is not None:\n")),
     [TR + "test_an_html_block_that_never_closes_stops_every_command"]),
    ("24 Unicode whitespace counts as blank",
     lambda: source(('blank = not fence_line.strip(" ' + BS + 't")', "blank = not fence_line.strip()")),
     [TR + "test_r3_a_non_breaking_space_line_ends_a_list_item"]),
    ("25 a tab is one column",
     lambda: source((STRIP_SPACES_AND_TABS, 'fence_line = physical.rstrip(" ' + BS + 't")')),
     [TR + "test_a_tab_indented_line_stays_inside_its_list_fence"]),
    ("26 a blank line ends a list fence",
     lambda: source(("if list_fence and fence is not None and not blank and _indent(fence_line) < fence_indent:",
                     "if list_fence and fence is not None and _indent(fence_line) < fence_indent:")),
     [TR + "test_a_blank_line_inside_a_list_fence_does_not_end_it"]),
    ("27 HTML blocks of types 3 to 5 are not known",
     lambda: attribute("HTML_BLOCKS", checker.HTML_BLOCKS[:2]),
     [TR + "test_html_blocks_of_types_3_to_5_hide_fence_lines"]),
    ("28 any number of spaces may follow a list marker",
     lambda: attribute("LIST_FENCE_OPEN",
                       re.compile(r"^( {0,3}(?:[-*+]|\d{1,9}[.)]) {1,})(`{3,}|~{3,})(.*)$")),
     [TR + "test_five_spaces_after_a_list_marker_is_indented_code_not_a_fence"]),
    ("29 </pre> never ends a pre block",
     lambda: attribute("HTML_BLOCKS",
                       [(checker.HTML_BLOCKS[0][0], re.compile(r"(?!)"))] + checker.HTML_BLOCKS[1:]),
     [TR + "test_a_fence_after_a_pre_block_is_a_fence"]),
    ("30 a stream that cannot be reconfigured gets unescaped text",
     lambda: attribute("_write", write_without_escaping, cli),
     [CL + "test_a_stream_that_cannot_be_reconfigured_still_gets_the_report"]),
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
     lambda: source(("            fence_opened, flagged = SourceLine(number, line), False\n"
                     "            in_elements = False\n",
                     "            fence_opened, flagged = SourceLine(number, line), False\n")),
     [FC + "test_a_fence_ends_the_elements_inventory"]),
    ("I a fenced Elements: is not recorded",
     lambda: attribute("_READ_LINES", (checker.STEP_HEADING, checker.DIRECTIVE,
                                       checker.WORKING_DIRECTORY, checker.SHELL_LINE)),
     [FC + "test_a_fenced_elements_heading_is_recorded"]),
    ("D fenced lines before the first step are not reported",
     lambda: source(("            )\n        )\n    findings.extend(\n"
                     "        _fence_findings(0, \"\", book.fenced_lines, book.unclosed_fence, "
                     "book.misaligned_fences)\n    )\n",
                     "            )\n        )\n")),
     [FF + "test_fenced_lines_before_the_first_step_are_reported_at_the_document"]),
    ("G a misplaced working directory stops only its own step",
     lambda: source(
         ("        or _misplaces_directory(book)\n", ""),
         ("            if not execute:\n                continue\n"
          if "            if not execute:\n                continue\n" in SOURCE
          else "        if not execute:\n            continue\n",
          "        if not execute or any(WORKING_DIRECTORY.match(m.text) for m in step.misplaced_lines):\n"
          "            continue\n")),
     [DL + "test_a_misplaced_working_directory_stops_commands_in_other_steps_too"]),
    ("K a working directory after a command is not caught",
     lambda: source(("            if WORKING_DIRECTORY.match(line) or ELEMENTS_HEADING.match(line):\n",
                     "            if (WORKING_DIRECTORY.match(line) or ELEMENTS_HEADING.match(line))"
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


def clean(result):
    return not (result.failures or result.errors or result.skipped)


print(f"console output page at start: {checker._windows_api()[0].GetConsoleOutputCP()}")
every_test = sorted({name for _, _, names in MUTANTS for name in names})
as_imported = run(every_test)
with source():
    through_source = run(every_test)
if not (clean(as_imported) and clean(through_source)):
    for label, result in (("as imported", as_imported), ("through the source path", through_source)):
        print(f"CONTROL {label}: {len(result.failures)} failures, {len(result.errors)} errors, "
              f"{len(result.skipped)} skipped of {result.testsRun}")
    sys.exit(2)
print(f"control: {len(every_test)} named tests pass unmutated, as imported and through the source path")

survivors = []
for name, mutate, tests in MUTANTS:
    with mutate():
        result = run(tests)
    failed, errored = len(result.failures), len(result.errors)
    killed = failed == len(tests) and not errored and not result.skipped
    print(f"{'killed' if killed else 'NOT KILLED'}: {name} ({failed} of {len(tests)} failed, "
          f"{errored} errored, {len(result.skipped)} skipped)")
    if not killed:
        survivors.append(name)
sys.exit(1 if survivors else 0)
