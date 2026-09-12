# Design — runbook-dry-run | 设计 — 运行手册预演

> **Dated** 2026-09-12 · **Status** accepted · **Supersedes** nothing
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
Path: `<a path this step depends on>`
Open: `<element>`
Click: `<element>`
On failure: <what the reader does when this step fails>
```

Every directive is optional except that each step needs an `On failure:` line. A step with no failure branch is a step that strands whoever hits it.

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
Path: `<本步骤依赖的路径>`
Open: `<元素>`
Click: `<元素>`
On failure: <本步骤失败时读者该做什么>
```

除了每个步骤都必须有一行 `On failure:` 之外，所有指令都是可选的。没有失败分支的步骤，会把撞上它的人困在原地。

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
