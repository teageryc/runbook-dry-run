"""Every test asserts a finding lands on the RIGHT step, not merely that one exists.

A suite that asserts "some finding was produced" passes on a checker that reports
every step as broken. The step number is what makes the assertion worth anything.
"""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
