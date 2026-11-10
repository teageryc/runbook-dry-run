"""Every test asserts a finding lands on the RIGHT step, not merely that one exists.

A suite that asserts "some finding was produced" passes on a checker that reports
every step as broken. The step number is what makes the assertion worth anything.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures")
sys.path.insert(0, REPO_ROOT)

from runbook_dry_run.checker import (  # noqa: E402
    _git_bash,
    FINDING_CODES,
    Launcher,
    Runbook,
    Step,
    check,
    has_errors,
    parse,
    resolve_shell,
)
from runbook_dry_run.__main__ import main as cli_main  # noqa: E402


def run_fixture(name: str, execute: bool = False):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        book = parse(handle.read())
    return check(book, base_dir=REPO_ROOT, execute=execute)


def codes_at(findings, step: int) -> set[str]:
    return {f.code for f in findings if f.step == step}


def one_step(shell_line: str, directive: str) -> str:
    return (
        "# Runbook: one step\n\nWorking directory: `.`\n"
        f"{shell_line}\n\n"
        "## Step 1 - the command under test\n"
        f"{directive}\n"
        "On failure: stop.\n"
    )


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
        self.assertEqual({"NO_STEPS"}, codes_at(findings, 0))

    def test_a_document_with_no_working_directory_says_so_at_document_level(self):
        text = "# Runbook: nowhere\n\n## Step 1 - do it\nOn failure: stop.\n"
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertIn("MISSING_WORKING_DIRECTORY", codes_at(findings, 0))

    def test_a_malformed_document_does_not_raise(self):
        findings = check(parse("garbage ## Step not-a-number\n"), base_dir=REPO_ROOT)
        self.assertEqual(["NO_STEPS"], [f.code for f in findings])
        self.assertEqual({"NO_STEPS"}, codes_at(findings, 0))


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

    def test_the_shell_is_read_from_the_declarations_and_cannot_disagree(self):
        """check() reads both; two writable copies of one fact let a caller split them."""
        book = parse(one_step("Shell: `bash`\nShell: `Git Bash`", "Run: `exit 0`"))
        self.assertEqual("bash", book.shell)
        with self.assertRaises(AttributeError):
            book.shell = "pwsh"
        self.assertEqual("pwsh", Runbook(shell_declarations=["pwsh"]).shell)

    def test_a_runbook_built_positionally_against_0_2_still_lines_up(self):
        """Runbook is public API; a new field goes at the END, never in the middle."""
        step = Step(number=1, title="t", failure_branch="stop.")
        book = Runbook("title", ".", ["Save"], [step])
        self.assertEqual(["Save"], book.element_inventory)
        self.assertEqual([step], book.steps)
        self.assertIsNone(book.shell)

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

    def test_backslashes_reach_bash_unaltered(self):
        """Windows re-parses a command line by rules Git Bash's runtime does not share.

        Passed as an argument, a backslash pair before a quote arrived halved. The
        command now travels in an environment variable, which nothing re-parses.
        """
        text = one_step("Shell: `bash`", r"Run: `x='a\\'; [ ${#x} -eq 3 ]`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")

    def test_the_backslash_probe_can_fail(self):
        text = one_step("Shell: `bash`", r"Run: `x='a\\'; [ ${#x} -eq 2 ]`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))

    def test_bash_output_is_read_as_utf_8(self):
        """Git Bash writes UTF-8; decoded with the ANSI code page, the detail was lost."""
        text = one_step("Shell: `bash`", r"Run: `printf '\344\270\201\n' >&2; exit 3`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))
        self.assertIn("exited 3: 丁", findings[0].detail)

    @unittest.skipUnless(sys.platform == "win32", "the console code page is a Windows fact")
    def test_cmd_output_is_read_in_the_console_code_page(self):
        """cmd.exe writes into a pipe in the console's code page, not the ANSI one Python assumes.

        Measured on the machine this was built on: console 65001, Python's default cp1252.
        """
        text = one_step("", "Run: `echo Schlüssel 1>&2 & exit /b 3`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))
        self.assertIn("exited 3: Schlüssel", findings[0].detail)

    @unittest.skipUnless(
        sys.platform == "win32" and shutil.which("pwsh"), "pwsh on Windows is not installed"
    )
    def test_pwsh_output_is_read_in_the_console_code_page(self):
        text = one_step(
            "Shell: `pwsh`", "Run: `[Console]::Error.WriteLine('Schlüssel'); exit 3`"
        )
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))
        self.assertIn("exited 3: Schlüssel", findings[0].detail)

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


class ShellResolution(unittest.TestCase):
    def test_git_bash_is_an_alias_and_case_does_not_matter(self):
        alias, _ = resolve_shell("Git Bash")
        self.assertIsNotNone(alias)
        self.assertEqual(alias, resolve_shell("BASH")[0])

    def test_an_unknown_name_is_refused_with_the_known_names(self):
        launcher, reason = resolve_shell("fish")
        self.assertIsNone(launcher)
        self.assertIn("'fish'", reason)
        for known in ("bash", "Git Bash", "pwsh", "powershell", "cmd"):
            self.assertIn(known, reason)

    @unittest.skipUnless(sys.platform == "win32", "the Git Bash lookup is Windows-only")
    def test_windows_bash_comes_from_git_never_from_path(self):
        """On the machine this was built on, PATH answers bash with the WSL launcher."""
        launcher, _ = resolve_shell("bash")
        self.assertIsNotNone(launcher)
        exe = launcher.argv[0].casefold()
        self.assertTrue(exe.endswith(os.path.join("bin", "bash.exe")), exe)
        self.assertNotIn("windowsapps", exe)
        self.assertNotIn("system32", exe)

    @unittest.skipUnless(sys.platform == "win32", "the Git Bash lookup is Windows-only")
    def test_windows_bash_without_git_is_unresolved(self):
        with mock.patch("runbook_dry_run.checker._on_path", return_value=None):
            launcher, reason = resolve_shell("bash")
        self.assertIsNone(launcher)
        self.assertIn("git", reason)

    @staticmethod
    def _fake_git(root: str, python_code: str) -> str:
        """A git.bat whose --exec-path answer is whatever `python_code` does.

        The .bat stays ASCII: cmd.exe reads a batch file in the console code page.
        """
        fake = os.path.join(root, "git.bat")
        with open(fake, "w", encoding="ascii") as handle:
            handle.write(f'@"{sys.executable}" -c "{python_code}"\r\n')
        return fake

    @unittest.skipUnless(sys.platform == "win32", "the Git Bash lookup is Windows-only")
    def test_a_git_installed_under_a_non_ascii_folder_is_found(self):
        """git prints its exec path in UTF-8, which the ANSI code page cannot always decode."""
        with tempfile.TemporaryDirectory() as root:
            install = os.path.join(root, "丁", "Git")
            exec_path = os.path.join(install, "mingw64", "libexec", "git-core")
            os.makedirs(exec_path)
            os.makedirs(os.path.join(install, "bin"))
            bash = os.path.join(install, "bin", "bash.exe")
            open(bash, "wb").close()
            answer = os.path.join(root, "exec-path.txt")
            with open(answer, "wb") as handle:
                handle.write(exec_path.replace(os.sep, "/").encode("utf-8") + b"\n")
            fake = self._fake_git(
                root, f"import sys; sys.stdout.buffer.write(open(r'{answer}', 'rb').read())"
            )
            with mock.patch("runbook_dry_run.checker._on_path", return_value=fake):
                found, problem = _git_bash()
        self.assertEqual("", problem)
        self.assertEqual(os.path.normcase(bash), os.path.normcase(found))

    @unittest.skipUnless(sys.platform == "win32", "the Git Bash lookup is Windows-only")
    def test_a_git_that_never_answers_is_given_up_on(self):
        """The real program is cmd.exe's child and holds the pipe after cmd.exe is killed."""
        with tempfile.TemporaryDirectory() as root:
            fake = self._fake_git(root, "import time; time.sleep(25)")
            started = time.monotonic()
            with mock.patch("runbook_dry_run.checker._on_path", return_value=fake), mock.patch(
                "runbook_dry_run.checker.GIT_PROBE_TIMEOUT", 1
            ):
                found, problem = _git_bash()
            elapsed = time.monotonic() - started
        self.assertIsNone(found)
        self.assertIn("did not answer", problem)
        self.assertLess(elapsed, 12, f"the probe waited {elapsed:.1f}s for a git that never answers")

    @unittest.skipUnless(sys.platform == "win32", "cmd exists only on Windows")
    def test_cmd_on_windows_is_the_platform_default(self):
        self.assertEqual((Launcher(), ""), resolve_shell("cmd"))

    @unittest.skipIf(sys.platform == "win32", "cmd and powershell exist on Windows")
    def test_cmd_and_powershell_are_refused_elsewhere(self):
        self.assertIsNone(resolve_shell("cmd")[0])
        self.assertIsNone(resolve_shell("powershell")[0])


class Timeouts(unittest.TestCase):
    """--timeout must stop the command, not merely stop waiting for its first process.

    Git Bash's bin/bash.exe is a launcher whose real bash is a second process, and
    cmd.exe or bash may start the program that actually holds the output pipes.
    Killing only the direct child left the checker reading pipes until the whole
    tree finished - forever, for a command that never ends.
    """

    def _timed(self, text: str):
        started = time.monotonic()
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True, timeout=2)
        return findings, time.monotonic() - started

    def test_a_timeout_under_a_declared_shell_stops_the_command(self):
        findings, elapsed = self._timed(one_step("Shell: `bash`", "Run: `sleep 10`"))
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))
        self.assertIn("timed out", findings[0].detail)
        self.assertLess(elapsed, 7, f"the timeout did not stop the command ({elapsed:.1f}s)")

    def test_a_timeout_in_the_platform_default_stops_the_command(self):
        findings, elapsed = self._timed(
            one_step("", "Run: `python -c \"import time; time.sleep(10)\"`")
        )
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))
        self.assertIn("timed out", findings[0].detail)
        self.assertLess(elapsed, 7, f"the timeout did not stop the command ({elapsed:.1f}s)")


class FindingDescriptions(unittest.TestCase):
    def test_shell_unresolved_names_every_case_that_emits_it(self):
        """A reader shown 'unknown or missing' for a misplaced line looks in the wrong place."""
        description = FINDING_CODES["SHELL_UNRESOLVED"]
        for case in ("does not know", "inside a step", "different shells", "does not have"):
            self.assertIn(case, description)

    def test_the_codes_added_in_0_4_are_described(self):
        for code in ("FENCED_LINE_SKIPPED", "FENCE_UNCLOSED", "DOCUMENT_LINE_IN_STEP"):
            self.assertIn(code, FINDING_CODES)


class ProcessPlacement(unittest.TestCase):
    """v0.2 ran every command in the checker's own session and process group.

    That is what lets a terminal prompt (sudo, ssh) and Ctrl+C reach the command,
    and an outer `timeout` or CI cancel stop it. A runbook is promised that
    behaviour whether or not it declares a shell.
    """

    MARKER = os.path.join(REPO_ROOT, "interrupted-marker.tmp")

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    tearDown = setUp

    @unittest.skipIf(sys.platform == "win32", "process groups are POSIX")
    def test_a_command_runs_in_the_checkers_own_process_group(self):
        probe = (
            f'"{sys.executable}" -c "import os, sys; '
            f'sys.exit(0 if os.getpgid(0) == {os.getpgid(0)} else 1)"'
        )
        for shell_line in ("", "Shell: `bash`"):
            with self.subTest(shell_line=shell_line or "undeclared"):
                text = one_step(shell_line, f"Run: `{probe}`")
                findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
                self.assertEqual([], findings, msg=f"unexpected findings: {findings}")

    def test_an_interrupted_check_stops_the_command(self):
        """subprocess.run killed the child on any exception; _run must too."""
        command = (
            f'"{sys.executable}" -c "import time; time.sleep(2); '
            "open('interrupted-marker.tmp', 'w').close()\""
        )
        text = one_step("", f"Run: `{command}`")
        real_communicate = subprocess.Popen.communicate
        interrupted = []

        def ctrl_c_once(proc, *args, **kwargs):
            """Ctrl+C arrives while the first read waits; later reads work."""
            if not interrupted:
                interrupted.append(proc)
                raise KeyboardInterrupt
            return real_communicate(proc, *args, **kwargs)

        with mock.patch.object(
            subprocess.Popen, "communicate", autospec=True, side_effect=ctrl_c_once
        ):
            with self.assertRaises(KeyboardInterrupt):
                check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual(1, len(interrupted), "the interruption never reached the command")
        time.sleep(4)
        self.assertFalse(
            os.path.exists(self.MARKER), "the command kept running after the check was interrupted"
        )


class CommandsThatCannotStart(unittest.TestCase):
    """A command the operating system refuses to start is a finding, never a crash.

    A traceback tells the reader nothing about the steps that were fine.
    """

    def test_a_nul_byte_in_a_command_is_a_finding(self):
        for shell_line in ("", "Shell: `bash`"):
            with self.subTest(shell_line=shell_line or "undeclared"):
                text = one_step(shell_line, "Run: `echo a\x00b`")
                findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
                self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 1))
                self.assertIn("null", findings[0].detail)


class ProgramLookup(unittest.TestCase):
    """Windows searches the current directory before PATH.

    A program planted where the checker happens to be run must never be chosen,
    and for git - which resolution executes - never run.
    """

    def _resolve_in(self, planted: str, name: str):
        """Resolve from inside `planted`, with Windows' default search order.

        NoDefaultCurrentDirectoryInExePath turns the current-directory search off,
        and some launchers set it; with it present this test passes on the old
        code too. Windows' default is to leave it unset, so the test removes it.
        """
        previous = os.getcwd()
        os.chdir(planted)
        try:
            with mock.patch.dict(os.environ):
                os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
                return resolve_shell(name)
        finally:
            os.chdir(previous)

    def _inside(self, path: str, directory: str) -> bool:
        """True for a path in `directory`, and for any relative path.

        shutil.which returns `.\\pwsh.BAT` for a current-directory hit; resolved
        after the test has left that directory, it would point somewhere else and
        pass. A relative program path is a current-directory hit by definition.
        """
        if not os.path.isabs(path):
            return True
        return os.path.realpath(path).casefold().startswith(
            os.path.realpath(directory).casefold()
        )

    @unittest.skipUnless(sys.platform == "win32", "only Windows searches the current directory first")
    def test_a_git_planted_in_the_current_directory_is_never_run(self):
        with tempfile.TemporaryDirectory() as planted:
            marker = os.path.join(planted, "planted-git-ran.tmp")
            with open(os.path.join(planted, "git.bat"), "w", encoding="ascii") as handle:
                handle.write("@echo off\r\necho ran> planted-git-ran.tmp\r\necho %CD%\r\n")
            launcher, _ = self._resolve_in(planted, "bash")
            self.assertFalse(os.path.exists(marker), "a git planted in the current directory ran")
            self.assertIsNotNone(launcher)
            self.assertFalse(self._inside(launcher.argv[0], planted), launcher.argv[0])

    @unittest.skipUnless(sys.platform == "win32", "only Windows searches the current directory first")
    def test_a_pwsh_planted_in_the_current_directory_is_not_chosen(self):
        with tempfile.TemporaryDirectory() as planted:
            with open(os.path.join(planted, "pwsh.bat"), "w", encoding="ascii") as handle:
                handle.write("@echo off\r\nexit /b 0\r\n")
            launcher, _ = self._resolve_in(planted, "pwsh")
            if launcher is not None:
                self.assertFalse(self._inside(launcher.argv[0], planted), launcher.argv[0])


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

    def test_an_unknown_name_is_reported_without_execute_too(self):
        """A name the tool does not know is a defect in the document, on any machine."""
        findings = run_fixture("shell-unknown.md")
        self.assertEqual({"SHELL_UNRESOLVED"}, codes_at(findings, 0))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")

    def test_an_unavailable_shell_refuses_on_every_platform(self):
        with mock.patch(
            "runbook_dry_run.checker.resolve_shell", return_value=(None, "pwsh is not on PATH")
        ):
            findings = run_fixture("shell-bash.md", execute=True)
        self.assertEqual({"SHELL_UNRESOLVED"}, codes_at(findings, 0))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("pwsh is not on PATH", findings[0].detail)
        self.assertFalse(
            os.path.exists(self.MARKERS[1]),
            "a command ran under a shell reported unavailable",
        )

    def test_a_shell_line_inside_a_step_is_refused_at_that_step(self):
        """Ignoring it would run bash commands in cmd.exe: the defect this directive removes."""
        text = (
            "# Runbook: misplaced\n\nWorking directory: `.`\n\n"
            "## Step 1 - declare too late\nShell: `bash`\n"
            "Run: `python -c \"open('shell-unknown-marker.tmp', 'w').close()\"`\n"
            "On failure: stop.\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"SHELL_UNRESOLVED"}, codes_at(findings, 1))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("inside a step", findings[0].detail)
        self.assertFalse(os.path.exists(self.MARKERS[0]), "a command ran despite a misplaced Shell:")
        self.assertEqual(
            {"SHELL_UNRESOLVED"}, codes_at(check(parse(text), base_dir=REPO_ROOT), 1)
        )

    def test_two_different_shells_are_refused(self):
        """Refused means not run: a command that succeeds anywhere cannot show that."""
        command = f"\"{sys.executable}\" -c \"open('shell-unknown-marker.tmp', 'w').close()\""
        text = one_step("Shell: `bash`\nShell: `pwsh`", f"Run: `{command}`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"SHELL_UNRESOLVED"}, codes_at(findings, 0))
        self.assertEqual(1, len(findings), msg=f"expected exactly one: {findings}")
        self.assertIn("more than once", findings[0].detail)
        self.assertFalse(
            os.path.exists(self.MARKERS[0]), "a command ran despite conflicting Shell: lines"
        )

    def test_two_names_for_the_same_shell_are_not_a_conflict(self):
        text = one_step("Shell: `Git Bash`\nShell: `bash`", "Run: `[[ -n \"$BASH_VERSION\" ]]`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")

    def test_without_execute_availability_is_never_checked(self):
        """The checking machine is not the reader's machine.

        A path-only CI run on Linux must not fail a Windows runbook for declaring a
        shell only Windows has - and must spawn nothing to find out.
        """
        with mock.patch("runbook_dry_run.checker.resolve_shell") as resolve:
            findings = run_fixture("shell-bash.md")
        resolve.assert_not_called()
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")

    def test_a_document_with_nothing_to_run_never_asks(self):
        text = one_step("Shell: `pwsh`", "Run (destructive): `Remove-Item -Recurse build`")
        with mock.patch(
            "runbook_dry_run.checker.resolve_shell", return_value=(None, "pwsh is not on PATH")
        ) as resolve:
            findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        resolve.assert_not_called()
        self.assertEqual({"COMMAND_SKIPPED_DESTRUCTIVE"}, codes_at(findings, 1))
        self.assertFalse(has_errors(findings))


FENCE = "```"


def fenced_doc(*step_lines: str, before: str = "") -> str:
    """A one-step runbook; its step body is the given lines, verbatim, from line 6."""
    body = "\n".join(step_lines)
    return (
        "# Runbook: fences\n\nWorking directory: `.`\n"
        f"{before}\n"
        "## Step 1 - the step under test\n"
        f"{body}\n"
        "On failure: stop.\n"
    )


class FencedCode(unittest.TestCase):
    """A line inside fenced code is an example, never an instruction (decision C1, KL-0277).

    Fenced lines are compared as plain (number, text) tuples: SourceLine is a NamedTuple.
    """

    def test_a_fenced_run_is_not_a_command(self):
        book = parse(fenced_doc(FENCE, "Run: `echo example`", FENCE, "Run: `echo real`"))
        self.assertEqual(["echo real"], book.steps[0].commands)
        self.assertEqual([(7, "Run: `echo example`")], book.steps[0].fenced_lines)

    def test_a_tilde_fence_and_an_indented_fence_are_fences_too(self):
        book = parse(fenced_doc("~~~", "Run: `a`", "~~~", "   ```", "Run: `b`", "   ```"))
        self.assertEqual([], book.steps[0].commands)
        self.assertEqual([7, 10], [line.number for line in book.steps[0].fenced_lines])

    def test_a_shorter_or_different_fence_does_not_close_it(self):
        book = parse(
            fenced_doc("````", FENCE, "Run: `a`", "~~~~", "Run: `b`", "````", "Run: `c`")
        )
        self.assertEqual(["c"], book.steps[0].commands)
        self.assertEqual([8, 10], [line.number for line in book.steps[0].fenced_lines])

    def test_a_fenced_step_heading_is_not_a_step(self):
        book = parse(fenced_doc(FENCE, "## Step 2 - an example", "On failure: x.", FENCE))
        self.assertEqual([1], [step.number for step in book.steps])
        self.assertEqual("stop.", book.steps[0].failure_branch)

    def test_a_one_line_code_span_is_not_a_fence(self):
        """```x``` on one line is inline code; read as a fence it would swallow the document."""
        book = parse(fenced_doc("```echo inline```", "Run: `echo real`"))
        self.assertEqual(["echo real"], book.steps[0].commands)
        self.assertEqual([], book.steps[0].fenced_lines)
        self.assertIsNone(book.steps[0].unclosed_fence)

    def test_an_unclosed_fence_is_recorded_where_it_opened(self):
        text = fenced_doc(FENCE, "Run: `a`") + "\n## Step 2 - swallowed\nOn failure: x.\n"
        book = parse(text)
        self.assertEqual([1], [step.number for step in book.steps])
        self.assertEqual((6, FENCE), book.steps[0].unclosed_fence)
        self.assertEqual([7, 8, 10, 11], [line.number for line in book.steps[0].fenced_lines])
        self.assertIsNone(book.unclosed_fence)

    def test_an_unclosed_fence_before_the_first_step_is_the_documents(self):
        book = parse(
            "# Runbook: x\n\nWorking directory: `.`\n```\n## Step 1 - swallowed\nOn failure: x.\n"
        )
        self.assertEqual([], book.steps)
        self.assertEqual((4, FENCE), book.unclosed_fence)
        self.assertEqual([5, 6], [line.number for line in book.fenced_lines])

    def test_a_fenced_document_line_before_the_first_step_is_not_read(self):
        before = "```\nWorking directory: `elsewhere`\nShell: `pwsh`\n```"
        book = parse(fenced_doc("Run: `x`", before=before))
        self.assertEqual(".", book.working_directory)
        self.assertIsNone(book.shell)

    def test_a_non_breaking_space_after_a_fence_means_it_does_not_close(self):
        """CommonMark allows only spaces or tabs after a closing fence (review finding 7).

        Word and Confluence paste U+00A0; read as a close, a line a renderer shows as
        code ran under --execute.
        """
        book = parse(fenced_doc(FENCE, "Run: `a`", "``` ", "Run: `b`", FENCE, "Run: `c`"))
        self.assertEqual(["c"], book.steps[0].commands)
        self.assertEqual([7, 9], [line.number for line in book.steps[0].fenced_lines])

    def test_a_closing_fence_followed_by_spaces_or_a_tab_still_closes(self):
        """The other half of review finding 7 (second review): trailing whitespace is common."""
        for closer in ("```  ", "```\t"):
            book = parse(fenced_doc(FENCE, "Run: `a`", closer, "Run: `b`"))
            self.assertEqual(["b"], book.steps[0].commands, msg=repr(closer))

    def test_only_commonmark_line_endings_split_lines(self):
        """U+2028 is not a line ending, so the line numbers after it stay true."""
        book = parse(fenced_doc("text more", FENCE, "Run: `x`", FENCE))
        self.assertEqual([(8, "Run: `x`")], book.steps[0].fenced_lines)

    def test_a_fence_after_a_line_separator_is_not_a_fence(self):
        """CommonMark sees one line, so no fence opens mid-line (review round 1, probe p6)."""
        book = parse(fenced_doc("text ```", "Run: `a`"))
        self.assertEqual(["a"], book.steps[0].commands)
        self.assertIsNone(book.steps[0].unclosed_fence)

    def test_a_form_feed_before_a_heading_still_starts_a_step(self):
        """As in v0.3 (second review, finding 7): a page break must not hide a step."""
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\n## Step 1 - one\nOn failure: stop.\n"
            "\f## Step 2 - two\nRun: `echo two`\nOn failure: retry.\n"
        )
        book = parse(text)
        self.assertEqual([1, 2], [step.number for step in book.steps])
        self.assertEqual(["echo two"], book.steps[1].commands)
        self.assertEqual("stop.", book.steps[0].failure_branch)

    def test_crlf_and_cr_line_endings_still_split_lines(self):
        text = fenced_doc(FENCE, "Run: `a`", FENCE, "Run: `b`")
        for ending in ("\r\n", "\r"):
            book = parse(text.replace("\n", ending))
            self.assertEqual(["b"], book.steps[0].commands, msg=repr(ending))
            self.assertEqual([(7, "Run: `a`")], book.steps[0].fenced_lines, msg=repr(ending))

    # Review round 1, finding 3: one guard per fence rule the spec states.

    def test_a_four_space_indented_fence_is_not_a_fence(self):
        book = parse(fenced_doc("    ```", "Run: `a`", "    ```"))
        self.assertEqual(["a"], book.steps[0].commands)
        self.assertEqual([], book.steps[0].fenced_lines)

    def test_a_four_space_indented_closer_does_not_close(self):
        book = parse(fenced_doc(FENCE, "    ```", "Run: `a`", FENCE, "Run: `b`"))
        self.assertEqual(["b"], book.steps[0].commands)
        self.assertEqual([8], [line.number for line in book.steps[0].fenced_lines])

    def test_a_fence_line_with_an_info_string_does_not_close(self):
        book = parse(fenced_doc(FENCE, "```bash", "Run: `a`", FENCE, "Run: `b`"))
        self.assertEqual(["b"], book.steps[0].commands)

    def test_a_longer_closing_fence_closes(self):
        book = parse(fenced_doc(FENCE, "Run: `a`", "`````", "Run: `b`"))
        self.assertEqual(["b"], book.steps[0].commands)

    def test_a_tilde_fence_may_have_backticks_in_its_info_string(self):
        book = parse(fenced_doc("~~~ `x`", "Run: `a`", "~~~", "Run: `b`"))
        self.assertEqual(["b"], book.steps[0].commands)
        self.assertEqual([7], [line.number for line in book.steps[0].fenced_lines])

    def test_a_fence_ends_the_elements_inventory(self):
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\nElements:\n- Save\n"
            "```\n- Fenced\n```\n- After\n\n## Step 1 - x\nOn failure: stop.\n"
        )
        self.assertEqual(["Save"], parse(text).element_inventory)

    def test_a_fenced_elements_heading_is_recorded(self):
        book = parse(fenced_doc(FENCE, "Elements:", FENCE))
        self.assertEqual([(7, "Elements:")], book.steps[0].fenced_lines)

    def test_the_new_fields_are_appended_so_positional_callers_still_line_up(self):
        step = Step(1, "t", ["echo a"])
        self.assertEqual(["echo a"], step.commands)
        self.assertEqual(([], None), (step.fenced_lines, step.unclosed_fence))
        self.assertEqual(([], None), (Runbook().fenced_lines, Runbook().unclosed_fence))


class FencedCodeFindings(unittest.TestCase):
    """Skipped means not run: a marker that must NOT appear beside one that must."""

    MARKERS = [
        os.path.join(REPO_ROOT, "fenced-marker.tmp"),
        os.path.join(REPO_ROOT, "unfenced-marker.tmp"),
    ]

    def setUp(self):
        for marker in self.MARKERS:
            if os.path.exists(marker):
                os.remove(marker)

    tearDown = setUp

    def test_a_fenced_run_is_never_executed_and_the_unfenced_one_is(self):
        findings = run_fixture("fenced.md", execute=True)
        self.assertFalse(os.path.exists(self.MARKERS[0]), "a fenced example was executed")
        self.assertTrue(os.path.exists(self.MARKERS[1]), "the real command never ran")
        self.assertEqual({"FENCED_LINE_SKIPPED"}, codes_at(findings, 1))
        self.assertIn("line 9", findings[0].detail)
        self.assertEqual("info", findings[0].severity)
        self.assertFalse(has_errors(findings))

    def test_an_unclosed_fence_is_an_error_at_the_step_where_it_opened(self):
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\n"
            "## Step 1 - fine\nOn failure: stop.\n\n"
            "## Step 2 - opens a fence\nOn failure: stop.\n```\n\n"
            "## Step 3 - swallowed\nOn failure: stop.\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual(set(), codes_at(findings, 1))
        self.assertEqual({"FENCE_UNCLOSED", "FENCED_LINE_SKIPPED"}, codes_at(findings, 2))
        self.assertEqual(set(), codes_at(findings, 3))
        unclosed = [f for f in findings if f.code == "FENCE_UNCLOSED"]
        self.assertEqual(1, len(unclosed))
        self.assertIn("line 10", unclosed[0].detail)
        self.assertTrue(has_errors(findings))

    def test_an_unclosed_fence_before_any_step_is_reported_with_no_steps(self):
        text = "# Runbook: x\n\nWorking directory: `.`\n~~~\n## Step 1 - x\n"
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual(
            {"NO_STEPS", "FENCE_UNCLOSED", "FENCED_LINE_SKIPPED"}, codes_at(findings, 0)
        )

    def test_fenced_lines_before_the_first_step_are_reported_at_the_document(self):
        text = fenced_doc("Run: `x`", before="```\nRun: `example`\n```")
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual({"FENCED_LINE_SKIPPED"}, codes_at(findings, 0))
        self.assertEqual(set(), codes_at(findings, 1))

    def test_a_fenced_shell_line_inside_a_step_no_longer_refuses_the_document(self):
        """KL-0256: a fenced Shell: example refused the whole document; now it is info only."""
        text = one_step("", f"{FENCE}\nShell: `bash`\n{FENCE}\nRun: `exit 0`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"FENCED_LINE_SKIPPED"}, codes_at(findings, 1))
        self.assertFalse(has_errors(findings))


class CommandLineOutput(unittest.TestCase):
    """Review finding 2: a report must reach a pipe or a file whatever text it quotes.

    Redirected, Python writes in the locale's encoding (cp1252 on Windows), and a
    skipped line quoting Chinese crashed the report with exit 1, which CI cannot
    tell from "has errors". PYTHONIOENCODING=ascii reproduces that on any platform.
    """

    def test_a_report_quoting_non_ascii_text_reaches_a_pipe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "cjk.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(fenced_doc(FENCE, "Run: `echo 中文`", FENCE))
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
            env["PYTHONIOENCODING"] = "ascii"
            result = subprocess.run(
                [sys.executable, "-m", "runbook_dry_run", path, "--base-dir", REPO_ROOT],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
            )
        self.assertEqual(0, result.returncode, msg=result.stderr.decode("ascii", "replace"))
        self.assertIn(b"step 1", result.stdout)
        self.assertIn(b"FENCED_LINE_SKIPPED", result.stdout)
        self.assertIn(b"\\u4e2d\\u6587", result.stdout)

    def cjk_runbook(self, folder):
        path = os.path.join(folder, "cjk.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(fenced_doc(FENCE, "Run: `echo 中文`", FENCE))
        return path

    def test_an_error_handler_the_caller_chose_is_kept(self):
        """Second review, finding 4: only the default strict handler is replaced."""
        with tempfile.TemporaryDirectory() as folder:
            path = self.cjk_runbook(folder)
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
            env["PYTHONIOENCODING"] = "ascii:replace"
            result = subprocess.run(
                [sys.executable, "-m", "runbook_dry_run", path, "--base-dir", REPO_ROOT],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
            )
        self.assertEqual(0, result.returncode, msg=result.stderr.decode("ascii", "replace"))
        self.assertIn(b"step 1", result.stdout)
        self.assertIn(b"echo ??", result.stdout)

    def test_main_puts_the_streams_back(self):
        """Called in-process, main() must not leave sys.stdout's handler changed."""
        with tempfile.TemporaryDirectory() as folder:
            path = self.cjk_runbook(folder)
            stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict")
            with mock.patch("sys.stdout", stream):
                code = cli_main([path, "--base-dir", REPO_ROOT])
            self.assertEqual(0, code)
            self.assertEqual("strict", stream.errors)
            stream.flush()
            self.assertIn(b"step 1", stream.buffer.getvalue())
            self.assertIn(b"\\u4e2d\\u6587", stream.buffer.getvalue())

    def test_a_stream_that_cannot_be_reconfigured_still_gets_the_report(self):
        """Third review, m3: a stand-in stdout with no reconfigure() crashed with exit 1."""

        class AsciiOnly:
            encoding, errors = "ascii", "strict"

            def __init__(self):
                self.parts = []

            def write(self, text):
                text.encode("ascii")
                self.parts.append(text)
                return len(text)

            def flush(self):
                pass

        with tempfile.TemporaryDirectory() as folder:
            path = self.cjk_runbook(folder)
            stream = AsciiOnly()
            with mock.patch("sys.stdout", stream):
                code = cli_main([path, "--base-dir", REPO_ROOT])
        self.assertEqual(0, code)
        self.assertIn("step 1", "".join(stream.parts))
        self.assertIn("\\u4e2d\\u6587", "".join(stream.parts))

    def test_a_runbook_that_is_not_utf_8_is_refused_with_exit_2(self):
        """Second review, finding 5: a traceback and exit 1 read like "has errors"."""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "gbk.md")
            with open(path, "wb") as handle:
                handle.write("# Runbook: 中文\n".encode("gbk"))
            errors = io.StringIO()
            with mock.patch("sys.stderr", errors):
                code = cli_main([path])
        self.assertEqual(2, code)
        self.assertIn("not UTF-8", errors.getvalue())


class UnclosedFenceStopsCommands(unittest.TestCase):
    """Review finding 1, Yan's pick: once a fence does not close, nothing runs.

    The checker does not model list items: a fence a renderer closes where its item
    ends stays open here, the rest of the document reads inverted, and before this
    rule a fenced example ran while the real command did not.
    """

    MARKERS = [os.path.join(REPO_ROOT, name) for name in ("real-marker.tmp", "example-marker.tmp")]
    REAL = "Run: `python -c \"open('real-marker.tmp', 'w').close()\"`"
    EXAMPLE = "Run: `python -c \"open('example-marker.tmp', 'w').close()\"`"

    def setUp(self):
        for marker in self.MARKERS:
            if os.path.exists(marker):
                os.remove(marker)

    tearDown = setUp

    def test_an_unclosed_fence_stops_every_command(self):
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\n"
            f"## Step 1 - runs first\n{self.REAL}\nOn failure: stop.\n\n"
            "## Step 2 - opens a fence\nOn failure: stop.\n```\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertFalse(os.path.exists(self.MARKERS[0]), "a command ran despite an unclosed fence")
        self.assertEqual({"FENCE_UNCLOSED"}, codes_at(findings, 2))
        self.assertIn("no command in this document was executed", findings[0].detail)

    def test_a_fence_left_open_in_a_list_item_runs_neither_command(self):
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\n"
            "## Step 1 - inspect\n1. The output looks like this:\n   ```\n   all good\n"
            "2. That is all there is to see.\n\nOn failure: stop.\n\n"
            f"## Step 2 - the real command\n{self.REAL}\nOn failure: stop.\n\n"
            f"An example, never run:\n\n```\n{self.EXAMPLE}\n```\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertFalse(os.path.exists(self.MARKERS[1]), "a fenced example was executed")
        self.assertFalse(os.path.exists(self.MARKERS[0]), "a command ran despite an unclosed fence")
        self.assertIn("FENCE_UNCLOSED", codes_at(findings, 1))


class FencesInsideContainers(unittest.TestCase):
    """Second review, Yan's pick A: fences in list items and HTML blocks.

    A fence opened on a list-marker line is read as CommonMark reads it; a fence
    line inside an HTML block of types 1-5 is not a fence; a fence closed by a line
    indented less than its opener is FENCE_MISALIGNED, which stops every command.
    The four documents below are the second review's reproductions (e1, e2, e3, f1).
    """

    MARKERS = [os.path.join(REPO_ROOT, name)
               for name in ("container-real-marker.tmp", "container-example-marker.tmp")]
    REAL = "Run: `python -c \"open('container-real-marker.tmp', 'w').close()\"`"
    EXAMPLE = "Run: `python -c \"open('container-example-marker.tmp', 'w').close()\"`"
    HEAD = "# Runbook: x\n\nWorking directory: `.`\n\n"

    def setUp(self):
        for marker in self.MARKERS:
            if os.path.exists(marker):
                os.remove(marker)

    tearDown = setUp

    def run_it(self, text):
        return check(parse(text), base_dir=REPO_ROOT, execute=True)

    def test_e1_a_list_fence_left_open_then_an_open_example_runs_nothing(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - inspect\n1. The output looks like this:\n   ```\n"
            "   all good\n2. That is all there is to see.\n\nOn failure: stop.\n\n"
            f"## Step 2 - the real command\n{self.REAL}\nOn failure: stop.\n\n"
            f"An example, never run:\n\n```\n{self.EXAMPLE}\nOn failure: stop.\n"
        )
        self.assertFalse(os.path.exists(self.MARKERS[1]), "a fenced example was executed")
        self.assertFalse(os.path.exists(self.MARKERS[0]), "a command ran despite FENCE_MISALIGNED")
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))

    def test_e2_a_list_fence_closed_at_column_0_runs_nothing(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - inspect\nOn failure: stop.\n\n"
            "1. The output looks like this:\n   ```\n   all good\n```\n\n"
            f"## Step 2 - shown as code\n{self.REAL}\nOn failure: stop.\n"
        )
        self.assertFalse(os.path.exists(self.MARKERS[0]), "a line shown as code was executed")
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))
        self.assertIn("no command in this document was executed", findings[0].detail)

    def test_e3_a_fence_line_inside_an_html_comment_is_not_a_fence(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - the real command\n<!-- the old example:\n```\n-->\n"
            f"{self.REAL}\nOn failure: stop.\n\nAn example, never run:\n\n```\n{self.EXAMPLE}\n```\n"
        )
        self.assertTrue(os.path.exists(self.MARKERS[0]), "the real command never ran")
        self.assertFalse(os.path.exists(self.MARKERS[1]), "a fenced example was executed")
        self.assertEqual({"FENCED_LINE_SKIPPED"}, codes_at(findings, 1))

    def test_e3_with_the_example_left_open_runs_nothing(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - the real command\n<!-- the old example:\n```\n-->\n"
            f"{self.REAL}\nOn failure: stop.\n\nAn example, never run:\n\n```\n{self.EXAMPLE}\n"
        )
        self.assertFalse(os.path.exists(self.MARKERS[1]), "a fenced example was executed")
        self.assertIn("FENCE_UNCLOSED", codes_at(findings, 1))

    def test_f1_a_fence_opened_on_a_list_marker_line_is_a_fence(self):
        findings = self.run_it(
            self.HEAD + f"## Step 1 - the real command\n{self.REAL}\nOn failure: stop.\n\n"
            "The output looks like this:\n\n- ```\n  all good\n  ```\n"
        )
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")
        self.assertTrue(os.path.exists(self.MARKERS[0]), "the real command never ran")

    def test_an_ordered_list_fence_closes_inside_its_item(self):
        book = parse(fenced_doc("1. ~~~", "   shown", "   ~~~", "Run: `echo real`"))
        self.assertEqual(["echo real"], book.steps[0].commands)
        self.assertIsNone(book.steps[0].unclosed_fence)

    def test_a_wide_list_marker_reads_the_item_from_its_content_column(self):
        """A closer 4 spaces in closes a "10. " item's fence, at the end of the document too.

        The document ends inside the item: with no later line to end the item, a closer
        that was not recognised would leave the fence open.
        """
        book = parse(
            self.HEAD + "## Step 1 - x\nOn failure: stop.\n\n10. ```\n    shown\n    ```\n"
        )
        self.assertIsNone(book.steps[0].unclosed_fence)
        self.assertEqual("stop.", book.steps[0].failure_branch)

    def test_a_list_fence_ends_with_its_item(self):
        """A line indented less than the item ends the item, and its fence (CommonMark)."""
        book = parse(fenced_doc("- ```", "  shown", "Run: `echo after`", FENCE, "Run: `x`", FENCE))
        self.assertEqual(["echo after"], book.steps[0].commands)
        self.assertEqual([10], [line.number for line in book.steps[0].fenced_lines])

    def test_a_fence_closed_less_indented_than_its_opener_is_misaligned(self):
        """The cost of the rule: valid at top level, refused because it could be list content."""
        findings = check(parse(fenced_doc("  ```", "code", FENCE, "Run: `x`")), base_dir=REPO_ROOT)
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))
        self.assertTrue(has_errors(findings))

    def test_an_aligned_or_one_space_fence_is_not_misaligned(self):
        for opener, content, closer in (
            ("  ```", "  code", "  ```"), (" ```", "code", FENCE), ("   ~~~", "   code", "   ~~~")
        ):
            text = fenced_doc(opener, content, closer, "Run: `x`")
            findings = check(parse(text), base_dir=REPO_ROOT)
            self.assertEqual(set(), codes_at(findings, 1), msg=repr((opener, closer)))

    def test_an_indented_fence_with_content_at_column_0_is_misaligned(self):
        """Third review, C2: in a list item that line ends the item and its fence.

        The stated cost: a top-level fence so written, valid Markdown, is refused too.
        """
        findings = check(parse(fenced_doc("  ```", "code", "  ```", "Run: `x`")), base_dir=REPO_ROOT)
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))

    def test_a_one_line_html_comment_opens_no_block(self):
        book = parse(fenced_doc("<!-- note -->", FENCE, "Run: `a`", FENCE, "Run: `b`"))
        self.assertEqual(["b"], book.steps[0].commands)
        self.assertEqual([8], [line.number for line in book.steps[0].fenced_lines])

    def test_a_fence_line_inside_a_pre_block_is_not_a_fence(self):
        book = parse(fenced_doc("<pre>", FENCE, "</pre>", "Run: `a`"))
        self.assertEqual(["a"], book.steps[0].commands)
        self.assertIsNone(book.steps[0].unclosed_fence)


class ContainerEdgesThirdReview(unittest.TestCase):
    """Third review, Yan's pick A: the reviewer's reproductions r1 to r6, and the edges
    its fuzzing and mutants found untested. Each executing case asserts its marker."""

    MARKER = os.path.join(REPO_ROOT, "third-review-marker.tmp")
    WRITE = "Run: `python -c \"open('third-review-marker.tmp', 'w').close()\"`"
    HEAD = "# Runbook: x\n\nWorking directory: `.`\n\n"

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    tearDown = setUp

    def run_it(self, text):
        return check(parse(text), base_dir=REPO_ROOT, execute=True)

    def test_r1_list_fence_content_at_column_0_runs_nothing(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - inspect\n1. The log should show:\n   ```\nall good\n   ```\n"
            f"On failure: stop.\n\n## Step 2 - mark\n{self.WRITE}\nOn failure: stop.\n"
        )
        self.assertFalse(os.path.exists(self.MARKER), "a line shown as code was executed")
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))

    def test_r2b_a_pre_block_ended_by_its_list_item_runs_nothing(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - check\n1. The status page should show:\n\n   <pre>\n   OK\n"
            "2. If it does not, stop.\n\nOn failure: stop.\n\nAn example, never run:\n\n"
            f"```\n{self.WRITE}\n```\n"
        )
        self.assertFalse(os.path.exists(self.MARKER), "a fenced example was executed")
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))

    def test_r3_a_non_breaking_space_line_ends_a_list_item(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - check\n- The status shows:\n- ```\n  status: ok\n \n"
            f"  ```\n\nOn failure: stop.\n\n## Step 2 - mark\n{self.WRITE}\nOn failure: stop.\n"
        )
        self.assertFalse(os.path.exists(self.MARKER), "a line shown as code was executed")
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))

    def test_r5_an_indented_fence_between_list_items_runs_nothing(self):
        findings = self.run_it(
            self.HEAD + "## Step 1 - a\n- one\n  ```\n  code\nPara A\n  ```\n"
            f"{self.WRITE}\n  ```\n- two\n  ```\n  code\nOn failure: stop.\n"
        )
        self.assertFalse(os.path.exists(self.MARKER), "a fenced example was executed")
        self.assertIn("FENCE_MISALIGNED", codes_at(findings, 1))

    def test_r6_a_command_inside_a_pre_block_is_not_read(self):
        findings = self.run_it(
            self.HEAD + f"## Step 1 - show\nThe old procedure was:\n\n<pre>\n{self.WRITE}\n</pre>\n\n"
            "On failure: stop.\n"
        )
        self.assertFalse(os.path.exists(self.MARKER), "a command shown in <pre> was executed")
        self.assertEqual({"FENCED_LINE_SKIPPED"}, codes_at(findings, 1))

    def test_a_command_inside_an_html_comment_is_not_read(self):
        book = parse(fenced_doc("<!--", "Run: `hidden`", "-->", "Run: `shown`"))
        self.assertEqual(["shown"], book.steps[0].commands)
        self.assertEqual([7], [line.number for line in book.steps[0].fenced_lines])

    def test_an_html_block_that_never_closes_stops_every_command(self):
        findings = self.run_it(
            self.HEAD + f"## Step 1 - a\n{self.WRITE}\nOn failure: stop.\n\n<!-- a note never closed\n"
        )
        self.assertFalse(os.path.exists(self.MARKER), "a command ran despite an unclosed HTML block")
        self.assertIn("FENCE_UNCLOSED", codes_at(findings, 1))

    def test_a_blank_line_inside_a_list_fence_does_not_end_it(self):
        book = parse(fenced_doc("- ```", "  a", "", "  b", "  ```", "Run: `x`"))
        self.assertEqual(["x"], book.steps[0].commands)
        self.assertIsNone(book.steps[0].unclosed_fence)

    def test_html_blocks_of_types_3_to_5_hide_fence_lines(self):
        for start, end in (("<?php", "?>"), ("<!DOCTYPE x", ">"), ("<![CDATA[", "]]>")):
            book = parse(fenced_doc(start, FENCE, end, "Run: `a`"))
            self.assertEqual(["a"], book.steps[0].commands, msg=start)
            self.assertIsNone(book.steps[0].unclosed_fence, msg=start)

    def test_a_fence_after_a_pre_block_is_a_fence(self):
        book = parse(fenced_doc("<pre>", "x", "</pre>", FENCE, "Run: `a`", FENCE, "Run: `b`"))
        self.assertEqual(["b"], book.steps[0].commands)

    def test_five_spaces_after_a_list_marker_is_indented_code_not_a_fence(self):
        book = parse(fenced_doc("-     ```", "Run: `a`"))
        self.assertEqual(["a"], book.steps[0].commands)
        self.assertIsNone(book.steps[0].unclosed_fence)

    def test_a_tab_indented_line_stays_inside_its_list_fence(self):
        """Tabs are 4-column stops (CommonMark): a Makefile recipe line inside "- ```make"."""
        book = parse(fenced_doc("- ```make", "\tcc -o x x.c", "  ```", "Run: `echo real`"))
        self.assertEqual(["echo real"], book.steps[0].commands)
        self.assertIsNone(book.steps[0].unclosed_fence)


class DocumentLinesInsideAStep(unittest.TestCase):
    """Working directory: and Elements: belong before the first step (decision C2, KL-0277)."""

    MARKER = os.path.join(REPO_ROOT, "step-line-marker.tmp")
    WRITE = "Run: `python -c \"open('step-line-marker.tmp', 'w').close()\"`"

    def setUp(self):
        if os.path.exists(self.MARKER):
            os.remove(self.MARKER)

    tearDown = setUp

    def two_steps(self, line: str) -> str:
        """Step 2 holds `line` at line 12, then a command that writes the marker."""
        return (
            "# Runbook: x\n\nWorking directory: `.`\n\nElements:\n- Save\n\n"
            "## Step 1 - fine\nOn failure: stop.\n\n"
            f"## Step 2 - the line under test\n{line}\n{self.WRITE}\nOn failure: stop.\n"
        )

    def test_a_working_directory_inside_a_step_is_an_error_at_that_step(self):
        text = self.two_steps("Working directory: `elsewhere`")
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual(set(), codes_at(findings, 1))
        self.assertEqual({"DOCUMENT_LINE_IN_STEP"}, codes_at(findings, 2))
        self.assertIn("line 12", findings[0].detail)
        self.assertTrue(has_errors(findings))

    def test_an_elements_line_inside_a_step_is_an_error_at_that_step(self):
        findings = check(parse(self.two_steps("Elements:")), base_dir=REPO_ROOT)
        self.assertEqual({"DOCUMENT_LINE_IN_STEP"}, codes_at(findings, 2))
        self.assertIn("inventory", findings[0].detail)

    def test_the_same_lines_before_the_first_step_report_nothing(self):
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\nElements:\n- Save\n\n"
            "## Step 1 - fine\nOn failure: stop.\n"
        )
        self.assertEqual([], check(parse(text), base_dir=REPO_ROOT))

    def test_the_same_line_fenced_inside_a_step_is_only_skipped(self):
        text = self.two_steps("```\nWorking directory: `elsewhere`\n```")
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual({"FENCED_LINE_SKIPPED"}, codes_at(findings, 2))
        self.assertFalse(has_errors(findings))

    def test_it_is_not_a_shell_finding(self):
        """SHELL_UNRESOLVED is read by --json consumers; its meaning stays as it was."""
        text = self.two_steps("Working directory: `elsewhere`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertNotIn("SHELL_UNRESOLVED", {f.code for f in findings})
        self.assertEqual({"DOCUMENT_LINE_IN_STEP"}, codes_at(findings, 2))

    def test_a_working_directory_inside_a_step_stops_every_command(self):
        """D1 = A: ignored, it would run the step from a directory its author did not mean."""
        text = self.two_steps("Working directory: `elsewhere`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertFalse(
            os.path.exists(self.MARKER), "a command ran despite a misplaced Working directory:"
        )
        self.assertIn("no command in this document was executed", findings[0].detail)

    def test_a_misplaced_working_directory_stops_commands_in_other_steps_too(self):
        """D1 says every command in the document, not only the step's own."""
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\n"
            f"## Step 1 - runs first\n{self.WRITE}\nOn failure: stop.\n\n"
            "## Step 2 - too late\nWorking directory: `elsewhere`\nOn failure: stop.\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertFalse(os.path.exists(self.MARKER), "step 1's command ran")
        self.assertEqual({"DOCUMENT_LINE_IN_STEP"}, codes_at(findings, 2))

    def test_a_working_directory_after_a_command_is_still_caught(self):
        text = (
            "# Runbook: x\n\nWorking directory: `.`\n\n"
            f"## Step 1 - command first\n{self.WRITE}\nWorking directory: `elsewhere`\n"
            "On failure: stop.\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT)
        self.assertEqual({"DOCUMENT_LINE_IN_STEP"}, codes_at(findings, 1))
        self.assertIn("line 7", findings[0].detail)

    def test_a_misplaced_working_directory_never_asks_for_the_shell(self):
        text = self.two_steps("Working directory: `elsewhere`").replace(
            "Working directory: `.`\n", "Working directory: `.`\nShell: `bash`\n", 1
        )
        with mock.patch(
            "runbook_dry_run.checker.resolve_shell", return_value=(None, "bash is not on PATH")
        ) as resolve:
            findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        resolve.assert_not_called()
        self.assertEqual({"DOCUMENT_LINE_IN_STEP"}, codes_at(findings, 2))

    def test_an_elements_line_inside_a_step_does_not_stop_commands(self):
        check(parse(self.two_steps("Elements:")), base_dir=REPO_ROOT, execute=True)
        self.assertTrue(os.path.exists(self.MARKER), "the control command never ran")


@unittest.skipUnless(sys.platform == "win32", "the console code page is a Windows fact")
class ConsoleCodePage(unittest.TestCase):
    """A runbook's chcp must not outlive the check (measured: it stayed in the terminal).

    chcp sets both of the console's pages, input and output, and chcp.com reports
    the input one: restoring only the output page left `chcp` showing 65001.
    """

    def setUp(self):
        import ctypes

        self.kernel32 = ctypes.WinDLL("kernel32")
        for name in ("GetConsoleCP", "GetConsoleOutputCP"):
            getattr(self.kernel32, name).restype = ctypes.c_uint
        for name in ("SetConsoleCP", "SetConsoleOutputCP"):
            getattr(self.kernel32, name).argtypes = [ctypes.c_uint]
        self.start = self.kernel32.GetConsoleOutputCP()
        self.start_input = self.kernel32.GetConsoleCP()
        if not self.start:
            self.skipTest("no console attached, so there is no code page to keep")
        # A page the console is not already in, or a run that started there would skip.
        self.target = 437 if self.start == 850 else 850
        # Positive control: in this launch context a child's chcp must move the page,
        # or the first test cannot fail and proves nothing.
        subprocess.run(f"chcp {self.target}>nul", shell=True)
        moved = self.kernel32.GetConsoleOutputCP()
        self.tearDown()
        if moved == self.start:
            self.skipTest("this console does not share its code page with a child")

    def tearDown(self):
        self.kernel32.SetConsoleOutputCP(self.start)
        self.kernel32.SetConsoleCP(self.start_input)

    def pages(self):
        return self.kernel32.GetConsoleCP(), self.kernel32.GetConsoleOutputCP()

    def test_a_chcp_in_a_command_does_not_outlive_the_check(self):
        text = one_step("Shell: `cmd`", f"Run: `chcp {self.target}>nul`")
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual([], findings, msg=f"unexpected findings: {findings}")
        self.assertEqual((self.start_input, self.start), self.pages())

    def test_within_the_run_the_new_page_carries_to_the_next_command(self):
        """As in one terminal: step 2 is read in the page step 1 set, never reset per command.

        Discriminates only from a console that starts in a page other than 65001
        (Git Bash on the machine this was written on); from 65001 it cannot fail.
        """
        text = (
            "# Runbook: x\n\nWorking directory: `.`\nShell: `cmd`\n\n"
            "## Step 1 - set the page\nRun: `chcp 65001>nul`\nOn failure: stop.\n\n"
            "## Step 2 - write in it\nRun: `echo 中文 1>&2 & exit 1`\nOn failure: stop.\n"
        )
        findings = check(parse(text), base_dir=REPO_ROOT, execute=True)
        self.assertEqual({"COMMAND_FAILED"}, codes_at(findings, 2))
        self.assertIn("exited 1: 中文", findings[0].detail)


if __name__ == "__main__":
    unittest.main()
