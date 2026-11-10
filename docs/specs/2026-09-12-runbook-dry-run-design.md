# Design — runbook-dry-run | 设计 — 运行手册预演

> **Dated** 2026-09-12 · **Status** accepted · **Supersedes** nothing · **Amended** 2026-09-12 for v0.2, see §7 · 2026-11-03 for v0.3, see §8 and §9 · 2026-11-10 for v0.4, see §11
> This document is the contract. The code is one implementation of it, and where the two disagree, this file is the defect report.

---

## EN

### 1. Goal

Prove a written procedure is **executable** before a human is asked to follow it.

The test this project exists to pass: given a procedure that is written, reviewed, merged and CI-green, report every step a reader could not actually perform — and name the step, not the document.

### 2. Non-goals

A goals section without this one is a wish list. Each item below is deliberately outside the contract, and at least one of them is something a reader would reasonably assume was included.

| Not a goal | Why |
|---|---|
| Executing destructive steps | A step marked `Run (destructive):` is reported and never executed, with or without `--execute`. A tool that proves a procedure by performing it is not a dry run. |
| Judging whether the procedure is **correct** | Only whether it is **followable**. A perfectly executable procedure can still be the wrong procedure, and this tool will report zero findings on it. |
| Generating runbooks | It reads them. Authoring is a separate problem with separate failure modes. |
| **Replacing the human walk-through on the day** | This is the one a reader assumes is in scope, and it is the most important exclusion. A clean report means every step *resolved at one instant on one machine*. It does not mean the operator can do the job. |
| Checking a real user interface | Screens and controls are checked against a declared inventory in the document, not against a running application. The inventory can itself be wrong. |
| Linting prose, grammar or formatting | Unreadable and unfollowable are different defects with different owners. |

### 3. The runbook format

Deliberately plain Markdown, because the input is written by the person who owns the procedure, not by a programmer.

```markdown
# Runbook: <title>

Working directory: `<path the reader is told to stand in>`
Shell: `<bash | Git Bash | pwsh | powershell | cmd>`

Elements:
- <every screen or control any step may name>

## Step 1 — <what the reader is doing>
Run: `<command>`
Run (destructive): `<command that is reported, never executed>`
Run (expect-fail): `<command whose success condition is a non-zero exit>`
Run (expect-fail: 128): `<command that must exit exactly 128, and nothing else>`
After manual step: <N>
Path: `<a path this step depends on>`
Open: `<element>`
Click: `<element>`
On failure: <what the reader does when this step fails>
```

Every directive is optional except that each step needs an `On failure:` line. A step with no failure branch is a step that strands whoever hits it.

`After manual step: <N>` declares that this step cannot run until a human has finished step N. Its commands are then reported, not executed, and step N must exist and come first.

`Shell: <name>` declares the shell every command in the document is written for, and `--execute` runs them in it. Names are case-insensitive; `Git Bash` is an alias for `bash`. On Windows, `bash` is found through git's own installation and never through `PATH`, which can resolve to the WSL launcher and run the commands under a different operating system. A document with no `Shell:` line runs its commands in the platform default (`cmd.exe` on Windows, `/bin/sh` elsewhere), exactly as before v0.3.

The line belongs before the first step: a `Shell:` line inside a step, or two lines naming different shells, is refused rather than ignored. A name the tool does not know is reported on every run; whether the named shell exists on this machine is asked only under `--execute`, and only when a command would actually run (§9).

### 4. Finding codes

A finding is always anchored to a step number. `step 0` means the defect belongs to the document rather than to any one step.

| Code | Severity | Fires when |
|---|---|---|
| `MISSING_WORKING_DIRECTORY` | error | the document never says where the reader should stand, so no path in it can be resolved |
| `NO_STEPS` | error | the document declares no steps |
| `NO_FAILURE_BRANCH` | error | a step never says what to do when it fails |
| `PATH_UNRESOLVED` | error | a path does not resolve from the declared working directory |
| `UI_ELEMENT_MISSING` | error | a step names a screen or control absent from the `Elements:` inventory |
| `COMMAND_FAILED` | error | a `Run:` command exited non-zero under `--execute` |
| `COMMAND_SKIPPED_DESTRUCTIVE` | info | a step is marked destructive and was therefore not executed |
| `EXPECTED_FAILURE_NOT_OBSERVED` | error | a `Run (expect-fail):` command exited `0`, or exited a code other than the one the step declared |
| `MANUAL_GATE_UNRESOLVED` | error | an `After manual step:` names no step number, or one the document does not contain, or one that does not precede this step |
| `COMMAND_DEFERRED_MANUAL_GATE` | info | a step waits on a manual step, so its commands were not executed under `--execute` |
| `SHELL_UNRESOLVED` | error | on every run: the `Shell:` line names a shell this tool does not know, appears inside a step (reported at that step), or is one of two lines naming different shells; under `--execute`, when a command would run: the named shell is not on this machine. No command in the document is then executed |
| `FENCED_LINE_SKIPPED` | info | a line the parser would read sits inside fenced code, so it was not read (§11) |
| `FENCE_UNCLOSED` | error | a code fence never closes; reported at the step where it opened, or at the document. No command in the document is then executed (§11) |
| `DOCUMENT_LINE_IN_STEP` | error | a `Working directory:` or `Elements:` line sits inside a step; a misplaced `Working directory:` also stops every command in the document (§11) |

Exit code is `1` if any finding has severity `error`, otherwise `0`.

### 5. Design decisions, with the reasoning that would let you overturn them

**The step is the unit, never the document.** "This runbook has a broken path" is not actionable. "Step 3 names a path that does not resolve from the directory step 1 told you to stand in" is. Every test in this repository asserts a code *and a step number*, because a suite that only asserts "a finding was produced" passes on a checker that reports every step as broken.

**Exit codes are read off the process, never through a pipe.** `returncode` is taken from the completed process itself. Piping a command into a pager, a formatter or `tee` makes the pipeline's status the one you see, and a failing step then reports success. This is the single defect the tool most often finds in real procedures, and it would be embarrassing to reproduce it internally.

**Commands are not executed by default.** `--execute` is opt-in. A checker that runs arbitrary commands the moment it is pointed at a file is a hazard in exactly the environments where procedures matter most.

**The parser never raises.** A parser that throws on malformed input converts a document defect into a tool defect, and the reader is then told nothing about the eleven steps that were fine.

**The UI inventory is declared, not discovered.** Driving a real application would make the tool heavier than the problem, and would make a network or credential failure indistinguishable from a missing button. The cost is honest and is recorded in `LIMITS.md`: the inventory can be wrong, and then the check is wrong with it.

### 6. What would show this design is wrong

- Real runbooks turn out not to be writable in this format without contortion, so authors keep two copies. Two copies drift, and the checked one stops being the followed one.
- The `Elements:` inventory is maintained so rarely that `UI_ELEMENT_MISSING` becomes noise, and readers start passing a flag to silence it.
- A finding count goes to zero across a repository while operators keep getting stuck, which would mean the codes do not cover the defects that actually strand people.

### 7. Amendment, 2026-09-12 — what the first real use added

This section records why the format grew, because the growth is itself the evidence.

The first procedure ever checked with this tool was the procedure that publishes this tool. It produced two findings, and neither was about that procedure — both were about this format.

**A step whose success condition is a failure had to give up its command.** The step confirming the target repository did not yet exist wanted `git ls-remote` to exit `128`. `Run:` means *must exit 0*, so there was no way to write it; the author deleted the command and moved the real check into the `On failure:` prose. The most consequential step in the procedure ended up as the only one the tool could not check. `Run (expect-fail):` exists so that does not happen again.

**The optional exit code is not decoration.** `git ls-remote` exits `128` when the repository is absent, and also exits non-zero when the network is down or the credential is wrong. A bare *any non-zero passes* would accept the second as proof of the first — the safe-looking answer arrived at for the wrong reason, which is the failure class this tool exists to surface. `Run (expect-fail: 128):` is the stronger declaration and is usually the right one.

**A step that waits on a human reported a failure that was not a defect.** The steps verifying the push and the CI run cannot succeed until the operator has created the repository and pushed. Under `--execute` they failed — correctly, and uselessly. A finding that is noise is a finding readers learn to silence, and §6 above already names that as a sign this design is wrong. `After manual step:` puts the dependency in the document instead.

**The gate is validated, and that is the whole point of `MANUAL_GATE_UNRESOLVED`.** A gate naming a step that does not exist would quietly stop the tool from ever executing those commands, and would report a clean run while doing it. A check that stops checking must say so out loud.

**What was deliberately not done.** Both gaps were recorded at the moment of first use and fixed afterwards, never during. Patching a tool while it is being used for the first time destroys the evidence that the first use found anything.

**Recorded by the second use, not built: the shell a procedure requires.** Re-checking the same procedure at v0.2 produced three `COMMAND_FAILED` findings that are not defects in it. The document declares *Shell: Git Bash* in its own header, and the format cannot express that, so `--execute` ran `cd /g/Projects/...` through `cmd.exe` — Python's `shell=True` resolves to the platform default no matter which shell launched the checker. This is the same shape as the two gaps above: something true, load-bearing and currently only expressible in prose. A `Shell:` directive is the obvious answer and it is not obviously right — honouring it means either refusing to run when the declared shell is unavailable, or invoking it and inheriting a second set of quoting rules. Recorded here, following the same rule that produced this section: the use that finds a gap does not get to patch it.

> **Corrected 2026-11-03 (v0.3, §8)** — the "not built" above is no longer current: the `Shell:` directive was built afterwards, outside any use, and §8 records the decision.

### 8. Amendment, 2026-11-03 — the shell, decided

**The two horns in §7 were not alternatives.** Invoking the declared shell and inheriting its quoting is not a cost: the reader will type the commands into that shell, so running them there is the faithful test, and running them anywhere else is the defect §7 recorded. The only real decision was what to do when the declared shell cannot be found, and the answer is to **refuse out loud**. One document-level `SHELL_UNRESOLVED` (error) names the cause and where the tool looked, and no command in the document is executed. Falling back to the platform default was rejected because it is precisely the behaviour that produced §7's three `COMMAND_FAILED` lines that were not defects — a fallback would reinstate the bug under a warning.

**It fires with or without `--execute`.** A shell the machine lacks strands the reader on the day whether or not this check ran the commands, and the path checks already report environment facts without executing anything.

> **Corrected 2026-11-03 (§9)** — superseded by Yan's ruling on the v0.3 code review: only a name the tool does not know fires on every run. Whether the shell exists is asked only under `--execute`, when a command would run, because the checking machine is not the reader's machine.

**Git Bash is found through git, never through `PATH`.** On Windows, `PATH` can resolve `bash` to `C:\Windows\System32\bash.exe` or the `WindowsApps` alias, both of which are the WSL launcher: the commands would run under Linux, with Linux paths — a third shell, chosen silently. The tool walks up from `git --exec-path` to the installation's `bin\bash.exe` instead, and reports `SHELL_UNRESOLVED` if git is absent.

**A document that declares no shell is unchanged.** It runs in the platform default and produces no new finding. A finding that fired on every existing runbook would be the noise §6 names as a sign this design is wrong.

**What remains a limit, not a feature.** The declared shell is the one the commands run in, not proof that the reader's own terminal is that shell. Under PowerShell, `-Command` collapses any failure of the final statement to exit `1` — measured 2026-11-03 on PowerShell 7, even a native command's own code (`cmd /c exit 7` arrives as `1`) — and a failure followed by a success arrives as `0`; only an explicit `exit N` survives. A `Run (expect-fail: <code>):` step under `Shell: pwsh` therefore needs its command to end in `; exit $LASTEXITCODE`. Both are recorded in `LIMITS.md`.

> **Corrected 2026-11-03 (§9)** — the `; exit $LASTEXITCODE` ending is right for a native program only. `$LASTEXITCODE` does not track cmdlets, so after a failing cmdlet the ending turns the failure into `0`, or into an earlier native program's code. The measurements are in §9.

### 9. Amendment, 2026-11-03 — what the code review changed

A code review of v0.3, run before the release rather than after it, reported fifteen findings. Every one was reproduced or read against the code before it was acted on. This section records the ones that changed the contract or the reasoning above; the rest are in the changelog.

**An unknown name and a missing shell are different facts** (Yan's ruling). A name the tool does not know is a defect in the document on any machine, so it is reported on every run. Whether the shell exists is a fact about the machine running the check, which is not the reader's: a Windows runbook declaring `cmd` must not fail a path-only CI run on Linux. That question is asked only under `--execute`, and only when a command would actually run — gated and destructive commands never do. A path-only run therefore starts no process at all.

**A misplaced or conflicting `Shell:` line is refused, not ignored** (Yan's ruling). Dropped silently, a `Shell:` line written inside a step left a bash runbook running in `cmd.exe` and producing the same false `COMMAND_FAILED` findings this directive exists to remove. It is now `SHELL_UNRESOLVED` at the step where it appears; two lines naming different shells are `SHELL_UNRESOLVED` at the document; and nothing executes. Two names for one shell (`Git Bash`, `bash`) are not a conflict.

**The command reaches bash in an environment variable.** Passed as an argument, the command crossed two parsers: Windows builds the command line by MSVC rules and Git Bash's runtime splits it by its own, so a backslash pair before a quote arrived halved — `x='a\\'` measured length 2 instead of 3. Bash now receives a fixed argument, `eval "$RUNBOOK_DRY_RUN_COMMAND"`, and the command travels in that variable, which nothing re-parses.

**On Windows, a timeout stops the whole command, not only its first process.** Measured before the fix: a 2-second timeout took 10.3 seconds under `Shell: Git Bash`, and so did a `cmd.exe` command whose program was a grandchild — a pre-existing defect that Git Bash's launcher stub made universal. Two obvious fixes were measured and rejected: `taskkill /T` cannot start while the output pipes are being read (12 to 16 seconds measured), and a walk by parent process id never finds the program, because an MSYS fork that has exited breaks the parent chain. The command now starts suspended inside a Job Object that is terminated on timeout. On POSIX the command stays where v0.2 put it, in the checker's own session and process group. The hang never happened there, because after a kill only the process is waited for, not its pipes; a timeout stops the command's first process, as it always did.

> **Corrected 2026-11-03 (second review)** — this paragraph first said that on POSIX the command leads its own process group. That was built, then reverted before release on Yan's ruling: a new session took the terminal away from every command, so `sudo` and `ssh` could no longer prompt and Ctrl+C no longer reached it — a change that §3 and §8 promise a runbook without `Shell:` never sees — to fix a hang that had been measured only on Windows.

**The PowerShell ending applies to native programs only.** Measured through the tool's own launcher on PowerShell 7: `cmd /c exit 7` arrives as `1`, and with `; exit $LASTEXITCODE` as `7`; a failing `Get-Item` arrives as `1`, but with the ending as `0`, and after an earlier `cmd /c exit 5` as `5`. A failing cmdlet is therefore declared `Run (expect-fail: 1):` with no ending.

**Shell resolution never searches the current directory.** `shutil.which` on Windows looks in the current directory first, so a `git.bat` planted where the checker ran was executed during resolution. Only absolute `PATH` entries are searched now. The regression test removes `NoDefaultCurrentDirectoryInExePath`, which some launchers set and Windows leaves unset; with it present, the test also passed on the vulnerable code.

### 10. Amendment, 2026-11-03 — what the second review changed

A second code review, over the first review's fixes (`6f35c5b..dacaf75`), reported fifteen more findings before anything was pushed. Each was reproduced, measured or read against the code before it was acted on. The ones that change the contract or the reasoning are below; the rest are in the changelog.

**POSIX commands stay in the checker's session** (Yan's ruling). The first timeout fix moved every POSIX command into a new session so that a timeout could stop it as a tree. That broke §3 and §8 for every runbook, declared or not — `sudo` and `ssh` could no longer prompt, and Ctrl+C no longer reached the command — to fix a hang that had been measured only on Windows; on POSIX the old code never waited on the pipes after a kill. It was reverted before release and checked on Linux (WSL Ubuntu, the first run of this code on Linux): a command's process group is the checker's again.

**An interrupted check stops its command.** `subprocess.run` kills the child on any exception; the bare `Popen` that replaced it did not, so Ctrl+C left the command running and unreported. A timeout and an interruption now both kill the command and collect it.

**`cmd.exe` and PowerShell are read in the console's output code page.** Measured: the same failing `echo` arrived as `Schl�ssel` when the checker was started from Git Bash (console 437) and as `SchlÃ¼ssel` from PowerShell (console 65001), because Python decodes in the ANSI page, cp1252. The page is read when each command starts; Git Bash stays UTF-8.

**`Runbook.shell` is derived, not stored.** `check()` read the declarations for conflicts and `shell` for resolution, so a caller could set the two apart. It is now a read-only property, the first declaration, changed before release while the public API still costs nothing to change.

**What stays a limit** (Yan's ruling). The parser does not know fenced code, so a fenced `Run:` example is executed, and a `Working directory:` or `Elements:` line inside a step is ignored. Changing either would change what existing runbooks do, so both are recorded in `LIMITS.md` instead of changed in this release.

> **Corrected 2026-11-10 (§11)** — both are changed in v0.4, and the code-page limit is corrected by measurement.

### 11. Amendment, 2026-11-10 — fenced code, document lines inside a step, and the console's code page

The three limits §10 kept, changed in v0.4 on Yan's picks C1 to C3 (2026-11-05), D1 and D2 (2026-11-10), and, on the first code review, D3 (2026-11-10).

**Fenced code is an example, never an instruction.** A line inside a CommonMark fence (up to three spaces, then three or more backticks or tildes, closed by the same character at least as long) is not read. Each one the parser would otherwise read is reported as `FENCED_LINE_SKIPPED`, informational, at the step it sits in. Before v0.4 a fenced `Run:` example was a command that `--execute` ran, a fenced `## Step N` became a step, and a fenced `Shell:` example inside a step refused the whole document; this repository's own README, checked as a runbook, showed all three. ```` ```x``` ```` on one line is inline code, not a fence.

**A fence that never closes is an error.** A renderer shows everything after it as code, so read that way every later step would vanish from the check without a word. `FENCE_UNCLOSED` is reported at the step where the fence opened, or at the document when it opened before the first step, and no command in the document runs then (D3, Yan's pick on the first review). The checker does not model list items, block quotes or HTML blocks, so a fence a renderer closes where its container ends stays open here, and the rest of the document reads inverted: in the review's reproduction, a fence left open in a list item ran a fenced example and skipped the real command. Such a fence leaves one open at the end, so refusing then stops the inversion from running anything; the line the finding names may be far from the mistake.

**Document lines inside a step are refused.** `Working directory:` and `Elements:` belong before the first step; inside one they are `DOCUMENT_LINE_IN_STEP` at that step. `SHELL_UNRESOLVED` keeps its meaning, which `--json` consumers read. A misplaced `Working directory:` also stops every command in the document, as a misplaced `Shell:` does (§9): ignored, it would run that step's commands from a directory its author did not mean. A misplaced `Elements:` moves no command and stops nothing.

**The code page: the planned fix was measured and not built.** The plan was to decode a command's output after it exits, in the page current then. Measured from Git Bash (console 437) and PowerShell (65001): in a one-line command, cmd.exe keeps the page it started with for the rest of the line — `chcp 437 & echo Schlüssel` arrives as UTF-8 from a 65001 start, so decoding after exit would read `Schl├╝ssel` where v0.3 reads it correctly — and a character the starting page cannot hold becomes `?` inside cmd.exe, beyond any decoder. Only a script the command runs writes its later lines in the new page. The bytes do not say which happened, so decoding is unchanged. What was built instead: both of the console's code pages, input and output, are put back when the check ends. A child's `chcp` sets both on the console the checker shares with it, and the change outlived the checker in both shells (437 to 65001, 65001 to 850); `chcp` itself reports the input page, so restoring only the output page would have left the change visible. Inside a run the pages are left alone, as one terminal carries them from step to step.

**What the first code review changed.** A review before release reported findings that were each reproduced first. Besides D3: lines split only on CommonMark's line endings, because `str.splitlines()` also split on U+2028 and form feed and shifted every reported line number after one; a fence closes only before spaces or tabs, because a closing fence followed by a non-breaking space, as Word pastes it, closed here but not in CommonMark, and a line a renderer shows as code ran; and a report quoting non-ASCII text no longer crashes when its output is redirected, where it exited 1 like a report with errors.

---

## 中文

### 一、目标

在任何人被要求照做之前，证明一份写好的流程是**可执行的**。

这个项目要通过的检验是：给定一份已写好、已评审、已合并、CI 已通过的流程，报出读者实际做不了的每一个步骤——而且要点到**步骤**，不是点到文档。

### 二、非目标

一份没有非目标的目标清单只是愿望清单。下面每一条都是刻意排除在契约之外的，其中至少有一条是读者会理所当然以为包含在内的。

| 不是目标 | 为什么 |
|---|---|
| 执行破坏性步骤 | 标记为 `Run (destructive):` 的步骤只被报告、永不执行，加不加 `--execute` 都一样。靠把流程做一遍来证明流程的工具，不是预演。 |
| 判断流程是否**正确** | 只判断是否**可照做**。一份完全可执行的流程仍然可能是错的流程，而本工具会对它报出零个发现。 |
| 生成运行手册 | 它只读。撰写是另一个问题，有另一套失败模式。 |
| **替代当天的人工走一遍** | 这是读者最会以为包含在内的一条，也是最要紧的排除项。报告干净只说明每一步**在某一台机器上的某一个瞬间解析通过**，不说明操作员能把活干下来。 |
| 检查真实的用户界面 | 屏幕与控件是对照文档里声明的清单检查的，不是对照运行中的应用。清单本身就可能是错的。 |
| 检查文字、语法或排版 | 读不懂和照不了做是两种缺陷，归属不同的人。 |

### 三、运行手册格式

刻意用朴素的 Markdown，因为输入是由流程的主人写的，不是由程序员写的。

```markdown
# Runbook: <标题>

Working directory: `<读者被告知站在哪个目录>`
Shell: `<bash | Git Bash | pwsh | powershell | cmd>`

Elements:
- <任何步骤可能提到的每一个屏幕或控件>

## Step 1 — <读者在做什么>
Run: `<命令>`
Run (destructive): `<只报告、永不执行的命令>`
Run (expect-fail): `<成功条件是非零退出码的命令>`
Run (expect-fail: 128): `<必须恰好退出 128、别的都不算的命令>`
After manual step: <N>
Path: `<本步骤依赖的路径>`
Open: `<元素>`
Click: `<元素>`
On failure: <本步骤失败时读者该做什么>
```

除了每个步骤都必须有一行 `On failure:` 之外，所有指令都是可选的。没有失败分支的步骤，会把撞上它的人困在原地。

`After manual step: <N>` 声明本步骤在人完成第 N 步之前无法运行。它的命令于是只被报告、不被执行，而第 N 步必须存在且在本步骤之前。

`Shell: <名称>` 声明文档里每一条命令是为哪个 shell 写的，`--execute` 就在那个 shell 里运行它们。名称不区分大小写；`Git Bash` 是 `bash` 的别名。在 Windows 上，`bash` 通过 git 自己的安装目录找到，绝不通过 `PATH`——`PATH` 可能解析到 WSL 启动器，把命令放到另一个操作系统里去跑。没有 `Shell:` 行的文档，命令在平台默认 shell 里运行（Windows 上是 `cmd.exe`，其他平台是 `/bin/sh`），与 v0.3 之前完全一样。

这一行应写在第一个步骤之前：写在某个步骤里的 `Shell:` 行，或者点名不同 shell 的两行，都会被拒绝，而不是被忽略。本工具不认识的名称，每次运行都会报；点名的 shell 在这台机器上是否存在，只在 `--execute` 下、并且确实有命令要运行时才会询问（第九节）。

### 四、发现代码

发现永远锚定到步骤编号。`step 0` 表示缺陷属于文档本身，而不属于任何单一步骤。

| 代码 | 严重度 | 触发条件 |
|---|---|---|
| `MISSING_WORKING_DIRECTORY` | error | 文档从未说明读者该站在哪里，于是其中任何路径都无法解析 |
| `NO_STEPS` | error | 文档没有声明任何步骤 |
| `NO_FAILURE_BRANCH` | error | 某个步骤从未说明失败时该做什么 |
| `PATH_UNRESOLVED` | error | 某个路径从声明的工作目录解析不到 |
| `UI_ELEMENT_MISSING` | error | 某个步骤提到的屏幕或控件不在 `Elements:` 清单里 |
| `COMMAND_FAILED` | error | 在 `--execute` 下某个 `Run:` 命令退出码非零 |
| `COMMAND_SKIPPED_DESTRUCTIVE` | info | 某个步骤被标记为破坏性，因而未被执行 |
| `EXPECTED_FAILURE_NOT_OBSERVED` | error | 某条 `Run (expect-fail):` 命令退出码为 `0`，或退出码不是步骤声明的那一个 |
| `MANUAL_GATE_UNRESOLVED` | error | 某个 `After manual step:` 没有点出步骤编号，或点的步骤文档里没有，或点的步骤不在本步骤之前 |
| `COMMAND_DEFERRED_MANUAL_GATE` | info | 某个步骤在等一个手工步骤，因而在 `--execute` 下它的命令未被执行 |
| `SHELL_UNRESOLVED` | error | 每次运行都会报：`Shell:` 行点名的 shell 本工具不认识、写在了某个步骤里（报在那一步），或者是点名不同 shell 的两行之一；在 `--execute` 下且有命令要运行时：点名的 shell 不在这台机器上。此时文档里任何命令都不执行 |
| `FENCED_LINE_SKIPPED` | info | 本会被解析器读取的一行位于围栏代码块内，因而未被读取（第十一节） |
| `FENCE_UNCLOSED` | error | 某个代码围栏没有关闭；报在它开启的那一步，或报在文档。此时文档里任何命令都不执行（第十一节） |
| `DOCUMENT_LINE_IN_STEP` | error | `Working directory:` 或 `Elements:` 行写在了步骤里；写错位置的 `Working directory:` 还会让文档里的任何命令都不执行（第十一节） |

只要有任何一个发现的严重度是 `error`，退出码为 `1`，否则为 `0`。

### 五、设计决策，以及可以据以推翻它们的理由

**单位是步骤，永远不是文档。**「这份手册有一个坏掉的路径」没法行动，「第 3 步提到的路径，从第 1 步让你站的那个目录解析不到」可以。本仓库里每个测试都同时断言代码**和步骤编号**，因为只断言「产生了某个发现」的测试套件，在一个把每一步都报成坏掉的检查器上也会通过。

**退出码直接从进程读，不经过管道。**`returncode` 取自已完成的进程本身。把命令接进分页器、格式化器或 `tee`，你看到的就变成管道的状态，于是失败的步骤报成了成功。这是本工具在真实流程里最常发现的那一种缺陷，在内部重现它会很难看。

**默认不执行命令。**`--execute` 是显式选择。一个指向文件就立刻运行任意命令的检查器，恰恰在流程最要紧的那些环境里是个危险品。

**解析器永不抛异常。**遇到畸形输入就抛出的解析器，会把文档缺陷变成工具缺陷，而读者就再也听不到另外十一个没问题的步骤的消息。

**界面清单是声明的，不是探测的。**去驱动一个真实应用会让工具比问题本身还重，而且会让网络或凭证失败与按钮缺失变得无法区分。这个代价是诚实的，并记录在 `LIMITS.md` 里：清单本身可能是错的，那么检查就跟着错。

### 六、什么迹象会说明这个设计是错的

- 真实的运行手册在这个格式里写不下来，除非扭曲，于是作者维护两份。两份会漂移，而被检查的那份就不再是被照做的那份。
- `Elements:` 清单维护得太少，以至于 `UI_ELEMENT_MISSING` 变成噪音，读者开始加参数把它关掉。
- 整个仓库的发现数降到零，而操作员照样被卡住——那意味着这些代码没有覆盖真正会困住人的缺陷。

### 七、修订，2026-09-12 —— 第一次真实使用带来了什么

这一节记录格式为什么长大，因为这个生长过程本身就是证据。

本工具检查的第一份流程，正是发布本工具的那份流程。它产生了两个发现，而两个都不是关于那份流程的——两个都是关于这个格式的。

**成功条件是失败的步骤，只能放弃自己的命令。** 确认目标仓库尚不存在的那一步，要的是 `git ls-remote` 退出 `128`。而 `Run:` 的含义是*必须退出 0*，于是这一步根本写不出来；作者删掉了命令，把真正的检查挪进了 `On failure:` 的散文里。流程中最要紧的一步，最后成了工具唯一检查不到的一步。`Run (expect-fail):` 的存在就是为了不再发生这件事。

**那个可选的退出码不是装饰。** `git ls-remote` 在仓库不存在时退出 `128`，在网络断了或凭证不对时同样退出非零。光是*任何非零都算通过*，就会把后者当成前者的证据——用错误的理由得到那个看起来安全的答案，而这正是本工具存在所要揭示的失败类别。`Run (expect-fail: 128):` 是更强的声明，通常也是对的那一个。

**等待人的步骤，报出了一个并非缺陷的失败。** 验证推送与验证 CI 的那两步，在操作者建好仓库并推送之前不可能成功。在 `--execute` 下它们失败了——正确地、且毫无用处地失败。噪音式的发现，会训练读者学会把发现关掉，而上面第六节恰恰把这一点列为「这个设计是错的」的迹象。`After manual step:` 改为把这个依赖写进文档。

**闸口是要校验的，这正是 `MANUAL_GATE_UNRESOLVED` 的全部意义。** 一个指向不存在步骤的闸口，会悄悄让工具永远不再执行那些命令，而且一边这么做一边报告运行干净。一个停止检查的检查，必须把这件事说出来。

**刻意没有做的事。** 两个缺口都是在第一次使用的当下记录、事后修复的，绝不在使用过程中。在一个工具第一次被使用的过程中把它补掉，会毁掉「第一次使用确实发现了东西」这个证据。

**第二次使用记录下、但没有建的：流程所要求的 shell。** 用 v0.2 重新检查同一份流程，产生了三个 `COMMAND_FAILED`，而它们都不是那份流程的缺陷。那份文档在自己的头部声明了 *Shell: Git Bash*，而格式表达不了这件事，于是 `--execute` 把 `cd /g/Projects/...` 交给了 `cmd.exe`——Python 的 `shell=True` 在 Windows 上总是解析到平台默认 shell，不管检查器是从哪个 shell 启动的。这与上面两个缺口是同一个形状：一件为真的、承重的、目前只能写在散文里的事。`Shell:` 指令是显而易见的答案，却不是显而易见正确的答案——要遵守它，就得在声明的 shell 不可用时拒绝运行，或者去调用它并因此继承第二套引号规则。记录在此，遵循的正是产生本节的那条规则：发现缺口的那次使用，没有资格顺手把它补掉。

> **Corrected 2026-11-03 (v0.3，第八节)** —— 上面的「没有建」已不再成立：`Shell:` 指令是事后、在任何一次使用之外建成的，决定记录在第八节。

### 八、修订，2026-11-03 —— shell 的决定

**第七节里的两个选项其实不是二选一。** 调用声明的 shell 并继承它的引号规则，并不是代价：读者会把命令敲进那个 shell，所以在那里运行才是忠实的检验，在别处运行恰恰就是第七节记录的那个缺陷。真正要决定的只有一件事：声明的 shell 找不到时怎么办，答案是**大声拒绝**。一个文档级的 `SHELL_UNRESOLVED`（error）说明原因和工具找过的地方，文档里任何命令都不执行。退回平台默认 shell 的方案被否决，因为那正是产生第七节那三个并非缺陷的 `COMMAND_FAILED` 的行为——退回去就是给那个 bug 换上一个警告重新装回来。

**加不加 `--execute` 都会报。** 机器上缺这个 shell，当天就会把读者困住，不管本检查有没有运行那些命令；路径检查本来就在不执行任何东西的情况下报告环境事实。

> **Corrected 2026-11-03 (第九节)** —— 已被 Yan 对 v0.3 代码审查的裁决取代：只有本工具不认识的名称才会在每次运行时报出。shell 是否存在，只在 `--execute` 下、有命令要运行时才询问，因为做检查的机器不是读者的机器。

**Git Bash 通过 git 找，绝不通过 `PATH`。** 在 Windows 上，`PATH` 可能把 `bash` 解析到 `C:\Windows\System32\bash.exe` 或 `WindowsApps` 别名，两者都是 WSL 启动器：命令会在 Linux 里、用 Linux 的路径运行——一个被悄悄选中的第三个 shell。工具改为从 `git --exec-path` 往上找到安装目录下的 `bin\bash.exe`，没有 git 就报 `SHELL_UNRESOLVED`。

**没有声明 shell 的文档保持不变。** 它在平台默认 shell 里运行，不产生新的发现。一个对每一份现有手册都触发的发现，正是第六节列为「这个设计是错的」迹象的那种噪音。

**仍然是限制、而不是功能的部分。** 声明的 shell 是命令被运行的那个 shell，并不证明读者自己的终端就是那个 shell。在 PowerShell 下，`-Command` 会把最后一条语句的任何失败压成退出码 `1`——2026-11-03 在 PowerShell 7 上实测，连原生命令自己的代码也一样（`cmd /c exit 7` 到达时是 `1`）——而先失败后成功到达时是 `0`；只有显式的 `exit N` 能原样传出。因此 `Shell: pwsh` 下的 `Run (expect-fail: <代码>):` 步骤，命令需要以 `; exit $LASTEXITCODE` 结尾。两者都记录在 `LIMITS.md` 里。

> **Corrected 2026-11-03 (第九节)** —— `; exit $LASTEXITCODE` 这个结尾只对原生程序成立。`$LASTEXITCODE` 不跟踪 cmdlet，所以在一个失败的 cmdlet 之后，这个结尾会把失败变成 `0`，或者变成更早某个原生程序的代码。实测数据见第九节。

### 九、修订，2026-11-03 —— 代码审查改变了什么

v0.3 的一次代码审查是在发布之前、而不是之后做的，报告了十五条发现。每一条在采取行动之前都经过复现，或对照代码读过。本节记录改变了契约或改变了上文推理的那几条；其余的在变更日志里。

**不认识的名称和缺失的 shell 是两件不同的事**（Yan 的裁决）。本工具不认识的名称，在任何机器上都是文档的缺陷，所以每次运行都会报。shell 是否存在，是关于运行检查的那台机器的事实，而那台机器不是读者的机器：一份声明了 `cmd` 的 Windows 手册，不应该让 Linux 上只检查路径的 CI 失败。这个问题只在 `--execute` 下、并且确实有命令要运行时才会询问——被闸住的命令和破坏性命令永远不会运行。于是只检查路径的运行根本不启动任何进程。

**写错位置或互相冲突的 `Shell:` 行会被拒绝，而不是被忽略**（Yan 的裁决）。写在某个步骤里的 `Shell:` 行原先会被悄悄丢掉，让一份 bash 手册在 `cmd.exe` 里运行，产生的正是这条指令要消除的那种假 `COMMAND_FAILED`。现在它在所在的那一步报 `SHELL_UNRESOLVED`；点名不同 shell 的两行在文档级报 `SHELL_UNRESOLVED`；什么都不执行。同一个 shell 的两个名称（`Git Bash`、`bash`）不算冲突。

**命令通过环境变量交给 bash。** 作为参数传递时，命令要经过两个解析器：Windows 按 MSVC 规则拼接命令行，Git Bash 的运行时按自己的规则拆分，于是引号前成对的反斜杠到达时被减半——`x='a\\'` 实测长度是 2 而不是 3。现在 bash 收到的是一个固定参数 `eval "$RUNBOOK_DRY_RUN_COMMAND"`，命令放在这个变量里传递，没有任何东西会重新解析它。

**在 Windows 上，超时会停下整条命令，而不只是它的第一个进程。** 修复前实测：在 `Shell: Git Bash` 下，2 秒的超时用了 10.3 秒；一条程序是孙进程的 `cmd.exe` 命令也一样——这是一个早已存在的缺陷，Git Bash 的启动器使它变得无处不在。两种显而易见的修法都实测过并被否决：读取输出管道期间，`taskkill /T` 根本启动不了（实测 12 到 16 秒）；按父进程号遍历永远找不到那个程序，因为一个已经退出的 MSYS fork 进程会让父子链断开。现在命令以挂起状态在一个作业对象（Job Object）里启动，超时时终止整个作业。在 POSIX 上，命令留在 v0.2 放它的地方，即检查器自己的会话和进程组里。那里从来没有卡住过，因为杀掉之后只等进程，不等它的管道；超时停下的是命令的第一个进程，一向如此。

> **更正于 2026-11-03（第二轮审查）**——本段原先说，在 POSIX 上命令自成一个进程组。这一点做出来了，又在发布之前按 Yan 的裁决撤回：新会话让每一条命令都失去了终端，于是 `sudo` 和 `ssh` 无法再提示输入，Ctrl+C 也到不了命令——而第三节和第八节承诺，没有 `Shell:` 的手册永远不会遇到这种变化——为的却是修一个只在 Windows 上测到过的卡死。

**PowerShell 的那个结尾只适用于原生程序。** 在 PowerShell 7 上通过本工具自己的启动方式实测：`cmd /c exit 7` 到达时是 `1`，加上 `; exit $LASTEXITCODE` 是 `7`；失败的 `Get-Item` 到达时是 `1`，加上这个结尾却是 `0`，如果前面运行过 `cmd /c exit 5` 则是 `5`。因此失败的 cmdlet 应声明为 `Run (expect-fail: 1):`，不加这个结尾。

**查找 shell 时绝不搜索当前目录。** Windows 上的 `shutil.which` 会先查当前目录，于是放在检查器运行目录里的一个 `git.bat` 在查找过程中被执行了。现在只搜索 `PATH` 里的绝对路径。回归测试会去掉 `NoDefaultCurrentDirectoryInExePath`——有些启动器会设置它，而 Windows 默认不设置；它在场时，这个测试在有漏洞的代码上也会通过。

### 十、修订，2026-11-03 —— 第二轮审查改变了什么

第二轮代码审查针对的是第一轮的修复（`6f35c5b..dacaf75`），在任何东西推送之前又报告了十五条发现。每一条在采取行动之前，都经过复现、实测，或对照代码读过。改变了契约或推理的那几条记在下面；其余的在变更日志里。

**POSIX 上的命令留在检查器的会话里**（Yan 的裁决）。第一轮的超时修复把每一条 POSIX 命令都挪进了一个新会话，好让超时能把它连同子孙一起停下。这对每一份手册——无论是否声明了 shell——都破坏了第三节和第八节：`sudo` 和 `ssh` 无法再提示输入，Ctrl+C 也到不了命令；为的却是修一个只在 Windows 上测到过的卡死，而在 POSIX 上，旧代码杀掉进程之后从来不等管道。这一改动在发布前撤回，并在 Linux 上验证过（WSL Ubuntu，这段代码第一次在 Linux 上运行）：命令的进程组重新是检查器的进程组。

**被中断的检查会停下它的命令。** `subprocess.run` 遇到任何异常都会杀掉子进程；取代它的裸 `Popen` 不会，于是 Ctrl+C 让命令继续运行，而且无人报告。现在超时和中断都会杀掉命令并回收它。

**`cmd.exe` 和 PowerShell 的输出按控制台的输出代码页读取。** 实测：同一条失败的 `echo`，检查器从 Git Bash 启动时（控制台 437）到达为 `Schl�ssel`，从 PowerShell 启动时（控制台 65001）到达为 `SchlÃ¼ssel`，因为 Python 按 ANSI 代码页 cp1252 解码。代码页在每条命令启动时读取；Git Bash 仍按 UTF-8。

**`Runbook.shell` 是推导出来的，不是存下来的。** `check()` 用声明列表判断冲突，又用 `shell` 解析 shell，于是调用者可以让两者不一致。现在它是一个只读属性，即第一条声明；趁发布之前公开接口还改得起，就改了。

**仍然是局限的部分**（Yan 的裁决）。解析器不认识围栏代码块，所以围栏里作为示例的 `Run:` 会被执行；写在步骤里的 `Working directory:` 或 `Elements:` 行会被忽略。改动任何一项都会改变现有手册的行为，所以这两项记进 `LIMITS.md`，而不在这个版本里修改。

> **2026-11-10 更正（第十一节）** —— 这两项都在 v0.4 改了，代码页那一项的局限也按实测作了更正。

### 十一、修订，2026-11-10 —— 围栏代码块、写在步骤里的文档级行，以及控制台的代码页

第十节保留的三项局限，在 v0.4 按 Yan 的选择 C1 至 C3（2026-11-05）、D1 与 D2（2026-11-10），以及第一轮代码审查时的 D3（2026-11-10）作了修改。

**围栏代码块是示例，永远不是指令。** 位于 CommonMark 围栏内的行（最多三个空格，然后是三个或更多反引号或波浪号，由同一种字符、长度不短于开头的围栏关闭）不会被读取。其中每一条本会被解析器读取的行，都在它所在的那一步报为 `FENCED_LINE_SKIPPED`（提示性）。v0.4 之前，围栏里作为示例的 `Run:` 是一条 `--execute` 会运行的命令，围栏里的 `## Step N` 会变成一个步骤，写在某一步里的围栏示例 `Shell:` 会让整份文档被拒绝；本仓库自己的 README 当作手册检查时，三种情况都出现了。写在一行里的 ```` ```x``` ```` 是行内代码，不是围栏。

**没有关闭的围栏是错误。** 渲染器把它之后的一切都显示为代码；照这样读，后面的每一步都会悄无声息地从检查里消失。`FENCE_UNCLOSED` 报在围栏开启的那一步；围栏在第一步之前开启时，报在文档；此时文档里任何命令都不运行（D3，Yan 在第一轮审查时的选择）。检查器不模拟列表项、引用块和 HTML 块，所以渲染器在容器结束处关闭的围栏，在这里仍然开着，文档其余部分就被反过来读了：在审查的复现里，列表项中没有关闭的围栏让一个围栏示例被运行，真正的命令却被跳过。这样的围栏会在文档末尾留下一个没有关闭的围栏，所以此时拒绝执行，就能让这种反转什么也运行不了；这条发现点出的那一行，可能离真正的错误很远。

**写在步骤里的文档级行被拒绝。** `Working directory:` 和 `Elements:` 应该写在第一步之前；写在某一步里时，在那一步报为 `DOCUMENT_LINE_IN_STEP`。`SHELL_UNRESOLVED` 的含义不变，`--json` 的使用者读的就是它。写错位置的 `Working directory:` 还会让文档里的任何命令都不执行，和写错位置的 `Shell:` 一样（第九节）：忽略它，那一步的命令就会在作者并不打算的目录里运行。写错位置的 `Elements:` 不改变任何命令，因此什么也不阻止。

**代码页：原计划的修复经实测后没有做。** 原计划是在命令退出之后，按那时的代码页解码它的输出。在 Git Bash（控制台 437）和 PowerShell（65001）下实测：一行命令在这一行剩下的部分里沿用 cmd.exe 启动时的代码页——从 65001 启动时，`chcp 437 & echo Schlüssel` 以 UTF-8 到达，退出后再解码会读成 `Schl├╝ssel`，而 v0.3 读得正确——启动代码页装不下的字符则在 cmd.exe 里就变成了 `?`，任何解码都救不回来。只有命令所运行的脚本，才会把后面的行按新代码页写出。字节本身看不出是哪种情况，所以解码方式不变。改为做了这件事：检查结束时，把控制台的两个代码页（输入和输出）都改回原样。子进程的 `chcp` 会同时改变它与检查器共用的控制台的这两个代码页，而且这一改变在两种 shell 下都比检查器活得更久（437 变 65001，65001 变 850）；`chcp` 本身报告的是输入代码页，所以只改回输出代码页，改变仍然看得见。在一次运行之内，代码页保持不动，就像同一个终端从一步带到下一步那样。

**第一轮代码审查改变了什么。** 发布前的一轮审查报告了若干发现，每一条都先经过复现。除了 D3：行只按 CommonMark 的换行符切分，因为 `str.splitlines()` 还会在 U+2028 和换页符处切分，使其后报告的每个行号都错一位；围栏只在后面只有空格或制表符时才关闭，因为后面跟着不换行空格（Word 粘贴时会这样）的结束围栏在这里关闭了，在 CommonMark 里却没有，于是渲染器显示为代码的一行被运行了；引用了非 ASCII 文字的报告在输出被重定向时不再崩溃，以前它会像有错误的报告一样以 1 退出。
