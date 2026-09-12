# Design — runbook-dry-run | 设计 — 运行手册预演

> **Dated** 2026-09-12 · **Status** accepted · **Supersedes** nothing · **Amended** 2026-09-12 for v0.2, see §7
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
