"""Every test asserts a finding lands on the RIGHT step, not merely that one exists.

A suite that asserts "some finding was produced" passes on a checker that reports
every step as broken. The step number is what makes the assertion worth anything.
"""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures")
sys.path.insert(0, REPO_ROOT)

from runbook_dry_run.checker import check, has_errors, parse  # noqa: E402


def run_fixture(name: str, execute: bool = False):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        book = parse(handle.read())
    return check(book, base_dir=REPO_ROOT, execute=execute)


def codes_at(findings, step: int) -> set[str]:
    return {f.code for f in findings if f.step == step}


class GoodRunbook(unittest.TestCase):
    def test_a_followable_runbook_reports_nothing(self):
        findings = run_fixture("good.md", execute=True)
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")

    def test_it_parses_every_step(self):
        with open(os.path.join(FIXTURES, "good.md"), encoding="utf-8") as handle:
            book = parse(handle.read())
        self.assertEqual([1, 2, 3, 4], [s.number for s in book.steps])
        self.assertEqual(".", book.working_directory)


class DefectIsReportedAtTheRightStep(unittest.TestCase):
    def test_unresolved_path_is_reported_at_step_three_only(self):
        findings = run_fixture("bad-path.md")
        self.assertEqual({"PATH_UNRESOLVED"}, codes_at(findings, 3))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("operator-handbook", findings[0].detail)

    def test_failing_command_is_reported_at_step_two_only(self):
        findings = run_fixture("bad-command.md", execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 2))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("exited 3", findings[0].detail)

    def test_unknown_control_is_reported_at_step_two_only(self):
        findings = run_fixture("bad-ui.md")
        self.assertEqual({"UI_ELEMENT_MISSING"}, codes_at(findings, 2))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")

    def test_missing_failure_branch_is_reported_at_step_two_only(self):
        findings = run_fixture("bad-no-failure-branch.md")
        self.assertEqual({"NO_FAILURE_BRANCH"}, codes_at(findings, 2))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")


class TheSuiteCanActuallyFail(unittest.TestCase):
    """The positive control. A suite that cannot fail is guidance, not a test."""

    def test_at_least_one_fixture_produces_an_error(self):
        self.assertTrue(has_errors(run_fixture("bad-path.md")))

    def test_the_good_fixture_and_a_bad_one_disagree(self):
        self.assertFalse(has_errors(run_fixture("good.md", execute=True)))
        self.assertTrue(has_errors(run_fixture("bad-ui.md")))


class DestructiveStepsAreNeverExecuted(unittest.TestCase):
    """The Non-goal, asserted by the ABSENCE of the side effect rather than by a promise."""

    MARKER = os.path.join(REPO_ROOT, "destructive-marker.tmp")

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def tearDown(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def test_execute_mode_does_not_run_the_destructive_command(self):
        findings = run_fixture("destructive.md", execute=True)
        self.assertFalse(
            os.path.exists(self.MARKER),
            "a destructive step was executed during a dry run",
        )
        self.assertEqual({"COMMAND_SKIPPED_DESTRUCTIVE"}, codes_at(findings, 2))
        self.assertFalse(has_errors(findings))


class DocumentLevelDefects(unittest.TestCase):
    def test_a_document_with_no_steps_says_so(self):
        findings = check(parse("# Runbook: empty\n"), base_dir=REPO_ROOT)
        self.assertEqual(["NO_STEPS"], [f.code for f in findings])

    def test_a_document_with_no_working_directory_says_so_at_document_level(self):
        text = "# Runbook: nowhere\n\n## Step 1 - do it\nOn failure: stop.\n"
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertIn("MISSING_WORKING_DIRECTORY", codes_at(findings, 0))

    def test_a_malformed_document_does_not_raise(self):
        findings = check(parse("garbage ## Step not-a-number\n"), base_dir=REPO_ROOT)
        self.assertEqual(["NO_STEPS"], [f.code for f in findings])


class ExpectedFailureDirective(unittest.TestCase):
    """A step whose success condition is a NON-ZERO exit.

    Without this directive the author must delete the command and move the real
    check into prose, which is exactly what happened on this tool's first real use:
    the step that mattered most ended up with no command at all.
    """

    MARKER = os.path.join(REPO_ROOT, "expect-fail-marker.tmp")

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def tearDown(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def test_a_command_that_fails_as_declared_reports_nothing(self):
        """Zero findings AND proof the command ran.

        Without the second assertion this test also passes on a checker that does
        not understand the directive at all and therefore skips the command - a
        clean report produced by not looking, which is this project's subject.
        """
        findings = run_fixture("expect-fail.md", execute=True)
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")
        self.assertTrue(
            os.path.exists(self.MARKER),
            "the expect-fail command never ran, so a clean report means nothing",
        )

    def test_a_command_that_unexpectedly_succeeds_is_reported_at_step_two_only(self):
        findings = run_fixture("bad-expect-fail.md", execute=True)
        self.assertEqual({"EXPECTED_FAILURE_NOT_OBSERVED"}, codes_at(findings, 2))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("exited 0", findings[0].detail)

    def test_the_wrong_nonzero_code_is_still_a_finding(self):
        """Any non-zero is not the same as the declared one.

        A probe that fails because the network is down exits non-zero and proves
        nothing about the thing being probed. Accepting it would return the
        safe-looking answer for the wrong reason.
        """
        findings = run_fixture("bad-expect-fail-code.md", execute=True)
        self.assertEqual({"EXPECTED_FAILURE_NOT_OBSERVED"}, codes_at(findings, 2))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("128", findings[0].detail)

    def test_nothing_is_checked_without_execute(self):
        self.assertEqual([], run_fixture("bad-expect-fail.md"))


class ManualGateDirective(unittest.TestCase):
    """A step that cannot run until a human has completed an earlier one.

    Asserted by the ABSENCE of the side effect, the same way the destructive
    Non-goal is asserted. A report that a command was not run is worth nothing
    if the only evidence for it is the tool's own say-so.
    """

    MARKER = os.path.join(REPO_ROOT, "manual-gate-marker.tmp")

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def tearDown(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    def test_a_gated_command_is_not_executed(self):
        findings = run_fixture("manual-gate.md", execute=True)
        self.assertFalse(
            os.path.exists(self.MARKER),
            "a gated step ran before the manual step it declared it was waiting on",
        )
        self.assertEqual({"COMMAND_DEFERRED_MANUAL_GATE"}, codes_at(findings, 2))
        self.assertFalse(has_errors(findings))

    def test_a_gate_naming_a_step_that_does_not_exist_is_reported(self):
        findings = run_fixture("bad-manual-gate.md")
        self.assertEqual({"MANUAL_GATE_UNRESOLVED"}, codes_at(findings, 1))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")

    def test_a_gate_naming_a_later_step_is_reported(self):
        text = (
            "# Runbook: gated on the future\n\nWorking directory: `.`\n\n"
            "## Step 1 - verify the thing\nAfter manual step: 2\nOn failure: stop.\n\n"
            "## Step 2 - the manual one\nOn failure: stop.\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual({"MANUAL_GATE_UNRESOLVED"}, codes_at(findings, 1))

    def test_no_deferral_is_reported_without_execute(self):
        """Singling out gated steps when NO command ran would be noise.

        Under --execute the report means every command was run and passed, so the
        reader must be told which ones were not. Without it, none were.
        """
        self.assertEqual([], run_fixture("manual-gate.md"))


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


if __name__ == "__main__":
    unittest.main()
