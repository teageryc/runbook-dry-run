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

**I find Git Bash only through git.** *(Added 2026-11-03, v0.3.)* On Windows I walk up from `git --exec-path` to the installation's `bin\bash.exe` and never ask `PATH`, because on the machine this was built on `PATH` answered `bash` with the WSL launcher, which runs the command under Linux. The cost: a Git Bash the reader has, but whose git is not on `PATH`, is invisible to me, and I report `SHELL_UNRESOLVED` for a shell that exists. I ask only the first `git` on `PATH`, so a bash-less git earlier on it - MinGit, or the one Visual Studio bundles - hides an installed Git Bash the same way. Asking runs `git --exec-path`, which I do only under `--execute`, and I search only absolute `PATH` entries, never the current directory.

**A timeout stops the whole command only on Windows, and even there not always.** *(Added 2026-11-03, v0.3.)* On Windows the command runs inside a Job Object, and a timeout terminates the job with everything the command started. If Windows refuses to put the command in the job, I still run it, and a timeout then stops only its first process; I wait at most ten more seconds for the output and move on to the next step. On Linux and macOS a command runs in my own session, as it did in v0.2, so a terminal prompt and Ctrl+C still reach it, and a timeout stops only its first process. Whenever only the first process stops, a program the command started keeps running - through the later steps and after I exit - and keeps whatever files or ports it holds. The report says `timed out` either way and does not say which of these happened.

**Under PowerShell, the exit code I read is PowerShell's summary, not the command's.** *(Added 2026-11-03, v0.3.)* `-Command` collapses any failure of the last statement to `1` - even a native program's own code - and reports a failure followed by a success as `0`. To pass a native program's own code through, end its command with `; exit $LASTEXITCODE`. Never after a cmdlet: `$LASTEXITCODE` tracks native programs only, so a failing cmdlet then arrives as `0`, or as an earlier native program's code. Declare a failing cmdlet `Run (expect-fail: 1):`, with no ending.

**A runbook that declares no shell is checked in mine, and I say nothing about it.** *(Added 2026-11-03, v0.3.)* Without a `Shell:` line I use the platform default - `cmd.exe` on Windows - and add no finding, because a finding on every existing runbook would be noise. A bash runbook checked on Windows without the line still fails in exactly the way that made this directive necessary; the only defence is to declare it.

**I do not know what a fenced code block is.** *(Added 2026-11-03, v0.3.)* A line inside a fenced code block is read like any other line. A `Run:` line shown there as an example is a command, and `--execute` runs it; a `Shell:` line shown there inside a step refuses the whole document. A line that starts with a space is never read as a directive, so indent an example, or change its directive word.

> **Corrected 2026-11-10 (v0.4)** — fenced code is now known. A line inside a backtick or tilde fence is not read; each one that would have been is reported as `FENCED_LINE_SKIPPED`. A fence that never closes is `FENCE_UNCLOSED`, and a fence opened two or three spaces in and closed less indented is `FENCE_MISALIGNED`; both are errors, and then no command in the document runs. A fence opened on a list item's marker line is read as CommonMark reads it, and a fence line inside an HTML comment, `<pre>`, `<script>`, `<style>`, `<textarea>`, `<?…?>`, `<!…>` or CDATA block is not a fence. What remains: inside other HTML blocks (`<div>` and the like, up to the next blank line) a fence line is still read as a fence, and that can turn the rest of the document inside out; a top-level fence indented two or three spaces and closed less indented is refused although it is valid Markdown, so align the closer; block quotes and nested lists are not modelled; and a directive inside an HTML comment is still read, though a rendered page hides it.

**A document-level line written inside a step is ignored.** *(Added 2026-11-03, v0.3.)* `Working directory:` and `Elements:` belong before the first step. Written inside one, they are dropped without a word, and that step's paths still resolve from the document's working directory. Only `Shell:` is refused there, because ignoring it would change the shell every command runs in.

> **Corrected 2026-11-10 (v0.4)** — no longer ignored: inside a step, both are `DOCUMENT_LINE_IN_STEP`, an error, and a misplaced `Working directory:` stops every command in the document.

**A command that changes the console's code page is read in the old one.** *(Added 2026-11-03, v0.3.)* On Windows I read `cmd.exe` and PowerShell output in the console's output code page as it was when the command started. A command that runs `chcp` changes the page its own later output arrives in, and a non-ASCII detail then reads wrongly; the exit code and the finding do not change.

> **Corrected 2026-11-10 (v0.4)** — measured, and partly wrong as first written. A one-line command keeps the page cmd.exe started with for the rest of the line, so its output is read correctly, and a character that page cannot hold becomes `?` inside cmd.exe before I see it. Only a script the command runs writes its later lines in the new page, and those I read in the old one, wrongly. The bytes do not say which happened, so I read every command in the page it starts with. Since v0.4 I also put both of the console's code pages, input and output, back when the check ends: a command's `chcp` used to stay in your terminal after I exited.

**A redirected text report escapes what its encoding cannot hold.** *(Added 2026-11-10, v0.4.)* Sent to a file or a pipe, the report is written in your locale's encoding (cp1252 on Windows), and text it cannot hold, such as Chinese, arrives as `\u4e2d\u6587` instead of crashing the report. `--json` carries the same escapes, which a JSON reader turns back into the text; to get the text itself, set `PYTHONIOENCODING=utf-8`.

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

**我只通过 git 找 Git Bash。**（2026-11-03 补记，v0.3）在 Windows 上，我从 `git --exec-path` 往上找到安装目录下的 `bin\bash.exe`，从不询问 `PATH`——在构建本工具的那台机器上，`PATH` 对 `bash` 给出的是 WSL 启动器，它会把命令放到 Linux 里运行。代价是：读者确实装了 Git Bash、但 git 不在 `PATH` 上时，我看不见它，会对一个存在的 shell 报出 `SHELL_UNRESOLVED`。我只问 `PATH` 上的第一个 `git`，所以排在前面、不带 bash 的 git——MinGit，或 Visual Studio 自带的那一份——同样会遮住一个已安装的 Git Bash。询问要运行 `git --exec-path`，而我只在 `--execute` 下才这样做；我只搜索 `PATH` 里的绝对路径，从不搜索当前目录。

**只有在 Windows 上，超时才会停下整条命令，而且即便在那里也不总是。**（2026-11-03 补记，v0.3）在 Windows 上，命令在一个作业对象（Job Object）里运行，超时时我终止这个作业，连同命令启动的一切。如果 Windows 拒绝把命令放进作业，我照样运行它，而超时时就只能停下它的第一个进程；我最多再等十秒读取输出，然后转到下一步。在 Linux 和 macOS 上，命令在我自己的会话里运行，和 v0.2 一样，所以终端提示和 Ctrl+C 仍然能到达它，而超时只停下它的第一个进程。凡是只停下第一个进程的情况，命令启动的程序都会继续运行——贯穿后面的步骤，在我退出之后也一样——并继续占着它打开的文件或端口。两种情况下报告都只说 `timed out`，不会说明发生的是哪一种。

**在 PowerShell 下，我读到的退出码是 PowerShell 的总结，不是命令自己的。**（2026-11-03 补记，v0.3）`-Command` 会把最后一条语句的任何失败压成 `1`——连原生程序自己的代码也一样——并把先失败后成功报成 `0`。要让原生程序自己的退出码传出来，就在它的命令末尾加 `; exit $LASTEXITCODE`。但绝不能加在 cmdlet 之后：`$LASTEXITCODE` 只跟踪原生程序，于是一个失败的 cmdlet 到达时会变成 `0`，或者变成更早某个原生程序的代码。失败的 cmdlet 应声明为 `Run (expect-fail: 1):`，不加这个结尾。

**没有声明 shell 的手册，是在我的默认 shell 里检查的，而我对此一言不发。**（2026-11-03 补记，v0.3）没有 `Shell:` 行时，我用平台默认 shell——Windows 上是 `cmd.exe`——而且不加任何发现，因为对每一份现有手册都报的发现就是噪音。一份为 bash 写的手册，在 Windows 上不带这一行检查，仍然会以当初促成这条指令的那种方式失败；唯一的防线是把它声明出来。

**我不知道什么是围栏代码块。**（2026-11-03 补记，v0.3）围栏代码块里的一行，和别的行一样被读取。作为示例写在那里的 `Run:` 行就是一条命令，`--execute` 会运行它；写在某个步骤里的示例 `Shell:` 行会让整份文档被拒绝。以空格开头的行永远不会被读成指令，所以请把示例缩进，或者改掉它的指令词。

> **2026-11-10 更正（v0.4）** —— 现在认得围栏代码块了。反引号或波浪号围栏里的行不会被读取；其中每一条本会被读取的行都报为 `FENCED_LINE_SKIPPED`。没有关闭的围栏报为 `FENCE_UNCLOSED`，以两到三个空格缩进开启、却以更少缩进关闭的围栏报为 `FENCE_MISALIGNED`；两者都是错误，此时文档里任何命令都不运行。在列表项标记那一行开启的围栏，按 CommonMark 的读法读；HTML 注释、`<pre>`、`<script>`、`<style>`、`<textarea>`、`<?…?>`、`<!…>` 或 CDATA 块里的围栏行不是围栏。仍然存在的局限：在其他种类的 HTML 块里（`<div>` 之类，直到下一个空行），围栏行仍被当作围栏读取，这可能把文档其余部分整个读反；以两到三个空格缩进、又以更少缩进关闭的顶层围栏，虽然是合法的 Markdown，也会被拒绝，所以请把结束围栏对齐；引用块和嵌套列表不在模拟范围内；HTML 注释里的指令依然会被读取，尽管渲染后的页面看不见它。

**写在步骤里的文档级行会被忽略。**（2026-11-03 补记，v0.3）`Working directory:` 和 `Elements:` 应该写在第一步之前。写在某一步里时，它们会被悄无声息地丢掉，那一步的路径仍然从文档的工作目录解析。只有 `Shell:` 写在那里会被拒绝，因为忽略它会改变每一条命令运行所用的 shell。

> **2026-11-10 更正（v0.4）** —— 不再被忽略：写在步骤里时，两者都报为 `DOCUMENT_LINE_IN_STEP`，属于错误；写错位置的 `Working directory:` 还会让文档里的任何命令都不执行。

**改变控制台代码页的命令，会按旧代码页读取。**（2026-11-03 补记，v0.3）在 Windows 上，我按命令启动时控制台的输出代码页读取 `cmd.exe` 和 PowerShell 的输出。一条运行了 `chcp` 的命令会改变它自己后续输出所用的代码页，于是非 ASCII 的细节会读错；退出码和发现不受影响。

> **2026-11-10 更正（v0.4）** —— 经过实测，原先的写法部分不对。一行命令在这一行剩下的部分里，沿用 cmd.exe 启动时的代码页，所以它的输出读得正确；那个代码页装不下的字符，在我看到之前就已经在 cmd.exe 里变成了 `?`。只有命令所运行的脚本，才会把后面的行按新代码页写出，而这些行我按旧代码页读，读错了。从字节上看不出是哪一种，所以我按每条命令启动时的代码页读它。从 v0.4 起，检查结束时我还会把控制台的两个代码页（输入和输出）都改回原样：以前，命令里的 `chcp` 会在我退出后仍然留在你的终端里。

**重定向的文本报告会把编码装不下的字符转义。**（2026-11-10 补记，v0.4）把报告输出到文件或管道时，它按你所在区域的编码写出（Windows 上是 cp1252），装不下的文字（例如中文）会以 `\u4e2d\u6587` 的形式出现，而不会让报告崩溃。`--json` 里也是同样的转义，JSON 读取器会把它还原成原文；若要直接得到原文，请设置 `PYTHONIOENCODING=utf-8`。

**它无法判断需要人做决定的步骤。**「比较两个数字并决定是否继续」——我只能检查它的失败分支。读者是否真的做得出那个判断，恰恰是走一遍流程要回答的问题，而这正是我最希望被理解为"本工具不替代"的那件事。
