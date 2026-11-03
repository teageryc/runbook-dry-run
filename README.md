# runbook-dry-run | 运行手册预演

**Committed is not executable.** A procedure can be written, reviewed, merged, deployed and CI-green, and still be impossible for the person holding it. This reads the procedure and reports every step they could not actually perform — naming the step, not the document.

**提交不等于可执行。** 一份流程可以写好、评审、合并、部署、CI 全绿，却仍然让拿着它的人做不下去。本工具读这份流程，报出他们实际做不了的每一个步骤——点到步骤，不是点到文档。

---

## EN

### Run it

No dependencies. Standard library only, Python 3.11 or newer.

```bash
git clone https://github.com/teageryc/runbook-dry-run.git
cd runbook-dry-run
python -m runbook_dry_run tests/fixtures/bad-path.md --base-dir .
```

```
tests/fixtures/bad-path.md: 1 finding(s).
[error] step 3 (Open the operator handbook): PATH_UNRESOLVED - docs/operator-handbook-that-was-never-written.md does not resolve from ...
```

Exit code is `1` when any finding is an error, so it drops straight into CI. Add `--execute` to actually run each `Run:` command and read its exit code. Add `--json` for machine-readable output.

### Write a runbook it can read

```markdown
# Runbook: close the quarter

Working directory: `/srv/ledger`

Elements:
- Variance report
- Approve

## Step 1 — Freeze the baseline
Run: `./bin/freeze --dry-run`
Path: `config/period.yml`
On failure: stop and call the controller. Do not proceed to step 2.

## Step 2 — Approve the variance
Open: `Variance report`
Click: `Approve`
On failure: you are not an approver. Ask for the role; do not work around it.
```

Every directive is optional except `On failure:`. A step without a failure branch strands whoever hits it, so its absence is itself a finding.

Two more directives exist for the steps that broke the first version of this format:

```markdown
## Step 3 — Confirm the target repository does not exist yet
Run (expect-fail: 128): `git ls-remote https://github.com/you/thing.git`
On failure: exit 0 means it already exists. Stop and read it before pushing into it.

## Step 5 — Verify the push landed
After manual step: 4
Run: `git ls-remote --heads origin refs/heads/main`
On failure: nothing reached the remote. Re-read step 4's output.
```

`Run (expect-fail:)` is for a step whose success condition is a command that **fails**. Name the exact code where you can: `git ls-remote` exits `128` when a repository is absent and also exits non-zero when your network is down, and only one of those answers the question.

`After manual step:` is for a step that cannot run until a human has done something. Its commands are reported rather than executed, instead of failing for a reason that is not a defect.

One directive belongs to the document rather than to a step:

```markdown
Working directory: `/srv/ledger`
Shell: `Git Bash`
```

`Shell:` names the shell the commands are written for - `bash` (or `Git Bash`), `pwsh`, `powershell` or `cmd` - and `--execute` runs them in it. On Windows, Git Bash is found through git's own installation, never through `PATH`, which can answer with the WSL launcher. If the declared shell cannot be found, nothing is executed and the report says so. A document with no `Shell:` line runs in the platform default, as before.

### What it checks

| Code | Fires when |
|---|---|
| `PATH_UNRESOLVED` | a path does not resolve from the declared working directory |
| `COMMAND_FAILED` | a `Run:` command exited non-zero under `--execute` |
| `UI_ELEMENT_MISSING` | a step names a screen or control absent from the `Elements:` inventory |
| `NO_FAILURE_BRANCH` | a step never says what to do when it fails |
| `MISSING_WORKING_DIRECTORY` · `NO_STEPS` | the document itself is unusable |
| `EXPECTED_FAILURE_NOT_OBSERVED` | a `Run (expect-fail):` command exited `0`, or exited a code other than the declared one |
| `MANUAL_GATE_UNRESOLVED` | an `After manual step:` names a step that does not exist or does not come first |
| `SHELL_UNRESOLVED` | the `Shell:` line names a shell this tool does not know, or one this machine does not have; nothing is then executed |
| `COMMAND_SKIPPED_DESTRUCTIVE` · `COMMAND_DEFERRED_MANUAL_GATE` | informational: a step was reported, not executed |

### Two things worth knowing before you trust it

A step marked `Run (destructive):` is **never** executed, with or without `--execute`. A tool that proves a procedure by performing it is not a dry run, and a test in this repository asserts the absence of the side effect rather than taking the promise on faith.

**A clean report is necessary and never sufficient.** It proves executability at one instant on one machine. It cannot see a button that exists but is disabled for the reader's role, and it does not know whether the procedure is the *right* procedure. The full list is in [`LIMITS.md`](LIMITS.md), and the design contract — including what this deliberately does **not** do — is in [`docs/specs/2026-09-12-runbook-dry-run-design.md`](docs/specs/2026-09-12-runbook-dry-run-design.md).

### Tests

```bash
python -m unittest discover -s tests -v
```

Thirty-five cases, a few of them platform-specific and skipped elsewhere. Every one asserts a finding code **and** the step number it must land on, because a suite that only asserts "a finding was produced" also passes on a checker that reports every step as broken.

Two of them assert a side effect rather than a report: a destructive command must leave **no** marker on disk, and an `expect-fail` command must leave **one**. Without the second, a clean report is indistinguishable from a directive the parser silently ignored. A runbook declaring `Shell:` must leave its marker too, and one whose shell cannot be found must leave none.

MIT licensed.

---

## 中文

### 运行

无依赖。仅用标准库，Python 3.11 或更新版本。

```bash
git clone https://github.com/teageryc/runbook-dry-run.git
cd runbook-dry-run
python -m runbook_dry_run tests/fixtures/bad-path.md --base-dir .
```

```
tests/fixtures/bad-path.md: 1 finding(s).
[error] step 3 (Open the operator handbook): PATH_UNRESOLVED - docs/operator-handbook-that-was-never-written.md does not resolve from ...
```

只要有任何一个发现是 error，退出码就是 `1`，所以它可以直接放进 CI。加 `--execute` 会真正运行每条 `Run:` 命令并读取其退出码。加 `--json` 得到机器可读的输出。

### 写一份它读得懂的手册

```markdown
# Runbook: close the quarter

Working directory: `/srv/ledger`

Elements:
- Variance report
- Approve

## Step 1 — Freeze the baseline
Run: `./bin/freeze --dry-run`
Path: `config/period.yml`
On failure: stop and call the controller. Do not proceed to step 2.

## Step 2 — Approve the variance
Open: `Variance report`
Click: `Approve`
On failure: you are not an approver. Ask for the role; do not work around it.
```

除 `On failure:` 外所有指令都是可选的。没有失败分支的步骤会把撞上它的人困在原地，所以它的缺席本身就是一个发现。

还有两条指令，是为那些把这个格式的第一版撑破的步骤而存在的：

```markdown
## Step 3 — Confirm the target repository does not exist yet
Run (expect-fail: 128): `git ls-remote https://github.com/you/thing.git`
On failure: exit 0 means it already exists. Stop and read it before pushing into it.

## Step 5 — Verify the push landed
After manual step: 4
Run: `git ls-remote --heads origin refs/heads/main`
On failure: nothing reached the remote. Re-read step 4's output.
```

`Run (expect-fail:)` 用于成功条件是命令**失败**的步骤。能点明确切退出码就点明：`git ls-remote` 在仓库不存在时退出 `128`，在你网络断了时同样退出非零，而只有其中一个回答了你要问的问题。

`After manual step:` 用于在人做完某件事之前无法运行的步骤。它的命令只被报告、不被执行，而不是因为一个并非缺陷的理由失败。

有一条指令属于整份文档，而不属于某个步骤：

```markdown
Working directory: `/srv/ledger`
Shell: `Git Bash`
```

`Shell:` 点明命令是为哪个 shell 写的——`bash`（或 `Git Bash`）、`pwsh`、`powershell` 或 `cmd`——`--execute` 就在那个 shell 里运行它们。在 Windows 上，Git Bash 通过 git 自己的安装目录找到，绝不通过 `PATH`，因为 `PATH` 可能给出 WSL 启动器。声明的 shell 找不到时，什么都不执行，报告会说明这一点。没有 `Shell:` 行的文档照旧在平台默认 shell 里运行。

### 它检查什么

| 代码 | 触发条件 |
|---|---|
| `PATH_UNRESOLVED` | 路径从声明的工作目录解析不到 |
| `COMMAND_FAILED` | 在 `--execute` 下某条 `Run:` 命令退出码非零 |
| `UI_ELEMENT_MISSING` | 步骤提到的屏幕或控件不在 `Elements:` 清单里 |
| `NO_FAILURE_BRANCH` | 步骤从未说明失败时该做什么 |
| `MISSING_WORKING_DIRECTORY` · `NO_STEPS` | 文档本身不可用 |
| `EXPECTED_FAILURE_NOT_OBSERVED` | 某条 `Run (expect-fail):` 命令退出码为 `0`，或不是声明的那一个 |
| `MANUAL_GATE_UNRESOLVED` | 某个 `After manual step:` 点的步骤不存在，或不在本步骤之前 |
| `SHELL_UNRESOLVED` | `Shell:` 行点名的 shell 本工具不认识，或这台机器上没有；此时什么都不执行 |
| `COMMAND_SKIPPED_DESTRUCTIVE` · `COMMAND_DEFERRED_MANUAL_GATE` | 提示性：步骤被报告，未被执行 |

### 信任它之前值得知道的两件事

标记为 `Run (destructive):` 的步骤**永不**执行，加不加 `--execute` 都一样。靠把流程做一遍来证明流程的工具不是预演，而本仓库里有一个测试是通过断言"副作用不存在"来验证这一点的，不是靠相信承诺。

**报告干净是必要条件，永远不是充分条件。**它只证明某一台机器上某一个瞬间的可执行性。它看不见"存在但因读者角色而禁用"的按钮，也不知道这份流程是不是**对的**流程。完整清单见 [`LIMITS.md`](LIMITS.md)；设计契约，包括它刻意**不做**的事，见 [`docs/specs/2026-09-12-runbook-dry-run-design.md`](docs/specs/2026-09-12-runbook-dry-run-design.md)。

### 测试

```bash
python -m unittest discover -s tests -v
```

三十五个用例，其中几个只适用于特定平台，在别的平台上跳过。每一个都同时断言发现代码**和**它必须落在的步骤编号，因为只断言"产生了某个发现"的套件，在一个把每一步都报成坏掉的检查器上也会通过。

其中两个断言的是副作用而不是报告：破坏性命令必须在磁盘上**不留**标记，而 `expect-fail` 命令必须留下**一个**。没有后者，「报告干净」与「解析器默默忽略了这条指令」就分不出来。声明了 `Shell:` 的手册同样必须留下标记，而 shell 找不到的手册必须一个都不留。

MIT 许可证。
