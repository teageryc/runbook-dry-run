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

### What it checks

| Code | Fires when |
|---|---|
| `PATH_UNRESOLVED` | a path does not resolve from the declared working directory |
| `COMMAND_FAILED` | a `Run:` command exited non-zero under `--execute` |
| `UI_ELEMENT_MISSING` | a step names a screen or control absent from the `Elements:` inventory |
| `NO_FAILURE_BRANCH` | a step never says what to do when it fails |
| `MISSING_WORKING_DIRECTORY` · `NO_STEPS` | the document itself is unusable |
| `COMMAND_SKIPPED_DESTRUCTIVE` | informational: a destructive step was reported, not executed |

### Two things worth knowing before you trust it

A step marked `Run (destructive):` is **never** executed, with or without `--execute`. A tool that proves a procedure by performing it is not a dry run, and a test in this repository asserts the absence of the side effect rather than taking the promise on faith.

**A clean report is necessary and never sufficient.** It proves executability at one instant on one machine. It cannot see a button that exists but is disabled for the reader's role, and it does not know whether the procedure is the *right* procedure. The full list is in [`LIMITS.md`](LIMITS.md), and the design contract — including what this deliberately does **not** do — is in [`docs/specs/2026-09-12-runbook-dry-run-design.md`](docs/specs/2026-09-12-runbook-dry-run-design.md).

### Tests

```bash
python -m unittest discover -s tests -v
```

Twelve cases. Every one asserts a finding code **and** the step number it must land on, because a suite that only asserts "a finding was produced" also passes on a checker that reports every step as broken.

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

### 它检查什么

| 代码 | 触发条件 |
|---|---|
| `PATH_UNRESOLVED` | 路径从声明的工作目录解析不到 |
| `COMMAND_FAILED` | 在 `--execute` 下某条 `Run:` 命令退出码非零 |
| `UI_ELEMENT_MISSING` | 步骤提到的屏幕或控件不在 `Elements:` 清单里 |
| `NO_FAILURE_BRANCH` | 步骤从未说明失败时该做什么 |
| `MISSING_WORKING_DIRECTORY` · `NO_STEPS` | 文档本身不可用 |
| `COMMAND_SKIPPED_DESTRUCTIVE` | 提示性：破坏性步骤被报告，未被执行 |

### 信任它之前值得知道的两件事

标记为 `Run (destructive):` 的步骤**永不**执行，加不加 `--execute` 都一样。靠把流程做一遍来证明流程的工具不是预演，而本仓库里有一个测试是通过断言"副作用不存在"来验证这一点的，不是靠相信承诺。

**报告干净是必要条件，永远不是充分条件。**它只证明某一台机器上某一个瞬间的可执行性。它看不见"存在但因读者角色而禁用"的按钮，也不知道这份流程是不是**对的**流程。完整清单见 [`LIMITS.md`](LIMITS.md)；设计契约，包括它刻意**不做**的事，见 [`docs/specs/2026-09-12-runbook-dry-run-design.md`](docs/specs/2026-09-12-runbook-dry-run-design.md)。

### 测试

```bash
python -m unittest discover -s tests -v
```

十二个用例。每一个都同时断言发现代码**和**它必须落在的步骤编号，因为只断言"产生了某个发现"的套件，在一个把每一步都报成坏掉的检查器上也会通过。

MIT 许可证。
