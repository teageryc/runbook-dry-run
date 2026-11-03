# What this tool cannot tell you | 本工具无法告诉你的事

> Written in the first person, by the author, on 2026-09-12. It is part of the deliverable, not an appendix to it. A defensibility claim that never names its own limits is not defensible.

---

## EN

**A clean report is necessary and never sufficient.** Everything below is a way this tool can report zero findings on a procedure that will still strand the person holding it. I would rather you knew these before you trusted it than after.

**It proves executability at one instant, on one machine.** The check ran where and when it ran. A path that resolved this morning can be gone this afternoon — and the most common version of that is a path inside a temporary working copy, which resolves perfectly right up until the procedure's own cleanup step deletes the directory it points into. The check passes, and the deletion that invalidates it happens afterwards, inside the same procedure.

**It cannot see a control that exists but is not available to the reader.** The `Elements:` inventory is a list in the document. If the button is on the screen but greyed out for this operator's role, disabled until an earlier record is approved, or behind a feature flag, I report nothing and the operator is stuck in front of a button they can see and cannot press.

**The inventory itself can be wrong.** I check the document against the document. If the author listed a screen that was renamed last month, I will happily confirm a step that names the old label.

**It does not know whether the procedure is the right procedure.** Every step can be perfectly followable and the sequence can still lose data, skip an approval, or do the wrong thing entirely. Correctness is not in scope and I will report zero findings on a procedure that should never be run.

**`--execute` runs commands with your privileges.** I refuse only what the author marked `Run (destructive):`. A command the author did not mark, I will run. If the marking is wrong, the protection is wrong with it — the safety here is a convention, not a sandbox.

**Shell quoting is inherited, not normalised.** Commands run through the shell the document declares with `Shell:`, or through the platform's own when it declares none. A command that works on the author's machine and fails in a Linux container is a real finding about the runbook, but I will report it as `COMMAND_FAILED` without telling you that portability, rather than the command, is the problem.

**It cannot see anything that depends on time or on state I did not touch.** A credential that expires next week, a queue that is empty today, a report that only exists after month-end, a step whose command is read-only today and destructive under a different flag — all invisible.

**A gated step is a step I did not check, and the report does not shout about it.** When a step declares `After manual step:`, I report its commands rather than running them, and the finding that says so is informational. Under `--execute` the sentence *every command was run and passed* is therefore false for exactly those steps — read the `COMMAND_DEFERRED_MANUAL_GATE` lines as the list of what a clean report does not cover. The more honestly a runbook declares its human dependencies, the less of it I have actually proven.

**An expected failure proves less than it looks like it proves.** `Run (expect-fail):` with no code accepts any non-zero exit, and a command can fail for reasons that have nothing to do with the question the step is asking — an unreachable network, a wrong credential, a missing binary. I will report that as satisfied. Naming the exact code narrows this and does not close it: the same code can still arrive by a different road.

**A declared shell is the shell I ran, not the shell the reader will open.** *(Added 2026-11-03, v0.3.)* `Shell: Git Bash` makes me run every command in Git Bash. It does not make the operator open Git Bash, and if they type the same commands into PowerShell, the document told them not to and I cannot see that it did not work.

**I find Git Bash only through git.** *(Added 2026-11-03, v0.3.)* On Windows I walk up from `git --exec-path` to the installation's `bin\bash.exe` and never ask `PATH`, because on the machine this was built on `PATH` answered `bash` with the WSL launcher, which runs the command under Linux. The cost: a Git Bash the reader has, but whose git is not on `PATH`, is invisible to me, and I report `SHELL_UNRESOLVED` for a shell that exists.

**Under PowerShell, the exit code I read is PowerShell's summary, not the command's.** *(Added 2026-11-03, v0.3.)* `-Command` collapses any failure of the last statement to `1` - even a native program's own code - and reports a failure followed by a success as `0`. A `Run (expect-fail: <code>):` step under `Shell: pwsh` must end its command with `; exit $LASTEXITCODE`, or the code it names can never arrive.

**A runbook that declares no shell is checked in mine, and I say nothing about it.** *(Added 2026-11-03, v0.3.)* Without a `Shell:` line I use the platform default - `cmd.exe` on Windows - and add no finding, because a finding on every existing runbook would be noise. A bash runbook checked on Windows without the line still fails in exactly the way that made this directive necessary; the only defence is to declare it.

**It cannot judge a step that requires a human decision.** "Compare the two figures and decide whether to proceed" is checkable only for its failure branch. Whether the reader can actually make that judgement is exactly what a walk-through is for, and that is the thing I most want to be understood as not replacing.

---

## 中文

> 由作者以第一人称写于 2026-09-12。它是交付物的一部分，不是附录。一项从不点明自身边界的可辩护性主张，是不可辩护的。

**报告干净是必要条件，永远不是充分条件。**下面每一条，都是本工具可能对一份仍会把执行者困住的流程报出零个发现的方式。我宁愿你在信任它之前知道这些，而不是之后。

**它只证明某一台机器上某一个瞬间的可执行性。**检查在它运行的那个地点和那个时刻完成。今天早上解析得到的路径，下午可能就没了——最常见的版本是指向临时工作副本内部的路径，它一路解析正常，直到流程自己的清理步骤删掉了它所指向的目录。检查通过了，而让它失效的删除动作发生在之后，就在同一份流程里面。

**它看不见"存在但读者用不了"的控件。**`Elements:` 清单是文档里的一个列表。如果按钮就在屏幕上，却因为这位操作员的角色而变灰、因为前序记录未审批而禁用、或者藏在功能开关后面，我什么都不会报，而操作员就卡在一个看得见、按不下去的按钮前面。

**清单本身可能是错的。**我拿文档去对照文档。如果作者列的是上个月已改名的屏幕，我会心安理得地确认一个引用旧名称的步骤。

**它不知道这份流程是不是对的流程。**每一步都可以完全可照做，而整个序列照样会丢数据、跳过审批，或者干脆做错事。正确性不在范围内，我会对一份根本不该执行的流程报出零个发现。

**`--execute` 会以你的权限运行命令。**我只拒绝作者标记为 `Run (destructive):` 的那些。作者没标记的命令，我会运行。如果标记错了，保护就跟着错——这里的安全性是一个约定，不是一个沙箱。

**Shell 的引号规则是继承的，不是归一化的。**命令通过文档用 `Shell:` 声明的那个 shell 运行，没有声明时通过平台自己的 shell 运行。一条在作者机器上成功、在 Linux 容器里失败的命令，确实是关于这份手册的真实发现，但我会把它报成 `COMMAND_FAILED`，而不会告诉你问题出在可移植性而不是命令本身。

**凡是依赖时间、或依赖我没有触碰的状态的，我都看不见。**下周过期的凭证、今天恰好为空的队列、只在月结之后才存在的报表、今天只读但换个参数就具破坏性的命令——全都不可见。

**被闸住的步骤是我没有检查的步骤，而报告不会为此大声说话。**当某一步声明了 `After manual step:`，我只报告它的命令而不运行它们，并且说明这件事的那个发现是提示性的。于是在 `--execute` 下，*每条命令都运行过且通过了*这句话，对这些步骤恰恰是假的——请把 `COMMAND_DEFERRED_MANUAL_GATE` 那几行读作「一份干净的报告没有覆盖到什么」的清单。一份手册越诚实地声明它对人的依赖，我真正证明过的部分就越少。

**预期中的失败，证明的东西比它看起来要少。**不带退出码的 `Run (expect-fail):` 接受任何非零退出，而一条命令失败的原因，可能与这一步要问的问题毫无关系——网络不通、凭证不对、可执行文件不存在。我都会报成满足。点明确切的退出码能收窄这一点，但不能封死它：同一个退出码仍然可能是从另一条路来的。

**声明的 shell 是我运行时用的 shell，不是读者会打开的那个。**（2026-11-03 补记，v0.3）`Shell: Git Bash` 让我在 Git Bash 里运行每一条命令，但不会让操作员去打开 Git Bash。如果他们把同样的命令敲进 PowerShell，文档已经告诉过他们不要这样做，而我看不见那样行不通。

**我只通过 git 找 Git Bash。**（2026-11-03 补记，v0.3）在 Windows 上，我从 `git --exec-path` 往上找到安装目录下的 `bin\bash.exe`，从不询问 `PATH`——在构建本工具的那台机器上，`PATH` 对 `bash` 给出的是 WSL 启动器，它会把命令放到 Linux 里运行。代价是：读者确实装了 Git Bash、但 git 不在 `PATH` 上时，我看不见它，会对一个存在的 shell 报出 `SHELL_UNRESOLVED`。

**在 PowerShell 下，我读到的退出码是 PowerShell 的总结，不是命令自己的。**（2026-11-03 补记，v0.3）`-Command` 会把最后一条语句的任何失败压成 `1`——连原生程序自己的代码也一样——并把先失败后成功报成 `0`。`Shell: pwsh` 下的 `Run (expect-fail: <代码>):` 步骤，命令必须以 `; exit $LASTEXITCODE` 结尾，否则它点名的那个代码永远到不了。

**没有声明 shell 的手册，是在我的默认 shell 里检查的，而我对此一言不发。**（2026-11-03 补记，v0.3）没有 `Shell:` 行时，我用平台默认 shell——Windows 上是 `cmd.exe`——而且不加任何发现，因为对每一份现有手册都报的发现就是噪音。一份为 bash 写的手册，在 Windows 上不带这一行检查，仍然会以当初促成这条指令的那种方式失败；唯一的防线是把它声明出来。

**它无法判断需要人做决定的步骤。**「比较两个数字并决定是否继续」——我只能检查它的失败分支。读者是否真的做得出那个判断，恰恰是走一遍流程要回答的问题，而这正是我最希望被理解为"本工具不替代"的那件事。
