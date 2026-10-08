---
name: autoresearch
description: >-
  Runs an unattended improvement loop outside the session: an external runner spawns a fresh,
  stateless agent each round, a scorer the person owns decides keep or revert, git holds every
  round, and one static report shows the whole run. The session's part is to design the scorer
  and the program with the user, start the loop, and read its progress.
  Use when the user wants an agent to iterate on its own towards a measurable goal — 自动迭代 /
  无人值守跑几十轮 / 让 agent 自己优化这个指标 / 自驱研究 / auto research / loop engineering /
  keep improving X until the score stops moving — wants help writing a scorer or a program for
  such a loop, asks how the running loop is doing or what the report means, wants to change what
  is measured while it runs, or invokes /autoresearch with init / run / status / report / doctor
  / example.
argument-hint: '[init | run <subject> | status [<subject>] | report | doctor | example toy|kata|compress|retrieval <dir>]'
metadata:
  author: xkcoding
  version: "0.2.0"
---

# /autoresearch

把一个**可度量**的目标交给会话之外的循环：`ar.py` 每一轮拉起一个全新的 agent，给它 program、当前最好成绩和缺口清单；它改完退出，打分器打分，比 best 高就留下，否则 `git revert`。几十轮之后，每一轮都在 git 历史和报告里。

没有任何一轮发生在这个会话里。会话做三件事：**和用户把打分器与 program 想清楚、把循环启动起来、读账本回答"现在怎么样了"**。用户要换方向或改度量时，帮他改文件——循环下一轮自己会拿到。

用用户的语言回复；写进目标仓库的 program、commit 用英文。

## 子命令

机械操作都在 `ar.py` 里。每个子命令打印**一个** JSON，`"ok": false` 时 `error` 写着为什么拒绝——拒绝是信息，原样转述给用户，不要替他绕过去。

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ar.py" <子命令> … --repo <目标仓库>
```

| 用户输入 | 跑什么 | 然后 |
|---|---|---|
| 不带子命令 | `status` | 有 research 就按[读进度](#读进度)回答并列出子命令；没有就走 [init](#init) |
| `init` | `init [--name N] [--subject S …] [--harness claude\|codex\|shell]` | 出骨架，再按 [init](#init) 和用户一起填 |
| `run <subject>` | `run <subject> [--rounds N]` | 按 [run](#run) 启动，放后台 |
| `status [<subject>]` | `status [<subject>]` | [读进度](#读进度) |
| `report` | `report` | 给出报告路径，`open` 它 |
| `doctor` | `doctor` | [前置检查](#前置检查) |
| `example <name> <dir>` | `example toy\|kata\|compress\|retrieval <dir>` | 生成一个带 git 仓库的示例 research，见[四个示例](#四个示例) |

`run … --dry-prompt` 只打印下一轮会发出的 prompt，不跑；`report.py <ar-dir>` 在只有账本、没有仓库时单独渲染报告。

## 前置检查

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ar.py" doctor --repo <目标仓库>
```

只读。对 python3 / git / claude / codex **实际执行** version 命令，检查仓库是否干净、有没有 commit、research 定义是否齐全、`harness.env` 引用的变量有没有设置。`problems` 非空就先解决；**不替用户安装或登录任何东西**。

## 原则

**agent 只认分数，所以这个会话最该花时间的是打分器，不是 program 或 prompt。** 几十轮无人值守，agent 的全部方向感来自分数：没有分项的维度不会得到投入；打分器对真正在意的改动不敏感，循环就会产生假进步——曲线在涨，东西没变好。一个坏打分器要烧几十轮、几美元才看得出来，所以第一轮之前必须手跑过、用已知一好一坏的两个版本验过。

**循环不在会话里，会话只读不写。** runner 每轮开始都要求工作树干净；会话在仓库里改任何被循环管着的文件，下一轮就会被拒。会话介入的唯一方式是改 `autoresearch/` 下的定义文件，runner 把它单独提交成 `ar scorer <subject>`，下一轮生效。

**harness 无状态，`remaining` 就是它的记忆。** 每一轮是新进程、新会话，只知道 prompt 里的 program、best 的度量、`remaining` 清单和最近几轮各一行自述。打分器给不出"还差什么"，循环就只能靠随机试探前进。

## init

`init` 生成能直接跑的骨架——`research.json` 和每个 subject 的 `program.md` / `score` / `gate`，已有的不覆盖——但骨架里的打分器是数 `.md` 文件个数的占位。真正的工作是下面这些步，**按顺序**，每一步有产物：

1. **问清三件事**（`AskUserQuestion`，一次问完）：度量什么、怎么变成一个数；agent 可以改哪些路径、哪些东西改了会让分数虚高（测试集、期望值、参考实现——都该锁）；什么时候停（轮数、连续 discard、目标分、时间或 token 预算，至少一个）。第一件答不上来就先别 init——没有分数就没有循环。
2. **`init`**，带上 subject 名。多个 subject 之间要不要 `depends_on`（后者必须等前者至少 keep 一轮才能跑）由用户定，脚本不猜。
3. **写 `score`**。可执行，从仓库根运行，stdout 一个 JSON：`{"score": 数字, "version": "x.y.z", "details": {…}, "remaining": […]}`，`version` 必填。`remaining` 从度量里**直接导出**（没覆盖的名字、失败的用例、最慢的端点）。契约细节、权重配比、冗余扣分、LLM 评委的代价，读 `references/scorer-guide.md`——这一步不要凭记忆写。
4. **手跑验证**，开循环之前必做：（a）`./autoresearch/subjects/<name>/score` 跑一次，输出合契约（手跑时没有 `AR_*` 环境变量，打分器要能没有它们也跑）；（b）拿两个已知一好一坏的版本各跑一次，分数差距对得上直觉吗——对不上先修打分器，不是修循环；（c）估一下**一轮合理的工作量能推进多少分**：推不动是坏的，一轮推到顶更坏。
5. **写 `program.md`**，模板四节：Goal / What you are working with / How you are measured / Ground rules。只写这个 subject 特有的东西——"一轮一个方向、不 commit、不碰锁定路径、结束自述"这些规则 runner 每轮自己加。
6. **`gate`**：快、便宜、能一票否决的检查（编译、lint、schema、冒烟）；没有就留 `exit 0`。它每轮都跑，agent 也可以随时跑，所以要快。
7. **`research.json`**：`editable`（进 prompt 的提示，**不强制**）；`locked`（强制：改到就 crash、不打分；`autoresearch/**` 永远在）；停止条件；`harness`——`type`、`timeout_sec`、`max_turns`（claude 的轮内上限，到了照常打分）、`max_budget_usd`、`env`（写 `"$VAR"` 引用环境变量，key 不落在仓库里）。拼错的键会被拒绝，不会静默忽略。
8. **`doctor`，然后 `run <subject> --dry-prompt`**，把 prompt 给用户看一眼——这就是 agent 每轮看到的全部（这一步会建 `research/<name>` 分支并切过去）。再 **`run <subject> --rounds 1`** 前台跑：先在 HEAD 上测一次基线（round 0），再跑一轮。和用户一起读 `status` 的 `summary` 和报告里的 `note` / `remaining` / `changed_files`，确认分数、缺口、改动范围都对，才放后台无人值守。

## run

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ar.py" run <subject> --repo <仓库> --rounds 20
```

前台跑：进度在 stderr 上滚；Ctrl-C 一次 = 做完这一轮再停，两次 = 立刻杀掉 harness 进程组、这一轮不记账。无人值守就放后台（Bash 工具的后台模式，或 `nohup … >/dev/null 2>&1 &`），然后把三样东西告诉用户：日志 `<研究名>.ar/runs/<run-id>.log`（`tail -f` 看进度）；停法（给 runner 发 SIGINT 或 SIGTERM，**不要 `kill -9`**——harness 在自己的进程组里，会被遗弃）；回来怎么看（`/autoresearch status`）。

runner 开跑前自己守的，任何一条不满足都拒绝并说清是哪条：同一研究没有别的 run 在跑（`run.lock`）；工作树干净（`autoresearch/` 下的手改除外，会被单独提交）；在 `research/<name>` 分支（没有就从当前 HEAD 建）；`depends_on` 的 subject 至少 keep 过一轮；账本里最后一个 checkpoint 和 best 的 commit 都还在 HEAD 的历史里（HEAD 可以更靠前）；账本里没有解析不了的 checkpoint 文件。打分器文件自 best 之后变过，第一轮之前先在 HEAD 上重测作为新基线；`--rounds 0` 就只做这一件事。

## 读进度

`status` 给每个 subject 一行 `summary`：`N checkpoints · K kept · D discarded · C crashed · E errors · best X at #n · score vA → vB · updated <time>`。回答"现在怎么样了"先念这一行，再看：

| 字段 | 含义 |
|---|---|
| `active_run` | 非空 = 有 run 正在跑（run_id、subject、pid、started）；空 = 没在跑 |
| `index.stopped_reason` | `max_rounds` / `consecutive_discards` / `consecutive_errors` / `target_score`：按自己的条件已经停了，再 `run` 也会立刻停；要继续就改 `research.json` 里对应的上限 |
| `index.consecutive_discards` / `consecutive_errors` | 接近上限 = 快停了。crash 计入 discard 那一项 |
| `scorer_changed_since_best` | 打分器改过、还没重测：下一次 `run` 先做新基线 |
| `runnable` / `missing` / `unreadable` | 定义文件缺失或不可执行；账本里有解析不了的 checkpoint（修好或挪走才能 `run`） |

四种结局：**keep**（同版本下分数更高）、**discard**（相等或更低）、**crash**（改了锁定路径，或 gate 失败；不打分）、**error**（harness 挂了、超时，或打分器输出不合契约；不占 discard 配额）。

报告（`report` 字段的路径，每轮重新生成，中文）自上而下回答四件事：现在在哪（最佳、相对基线、轮次、花费、agent 用时、运行中 / 已停止及原因）；还在动吗（穿过 keep 轮次的曲线，discard 空心点、crash / error 打叉；第一轮跳太大时 #0 基线默认移出坐标轴，可勾回）；在做什么（最佳轮次的 `details` 和 `remaining`）；每轮发生了什么（一行一轮，agent 自述的第一句，点开看全文、改动、commit、token）。给用户讲进度时按这个顺序讲。原始材料在 `<研究名>.ar/artifacts/<subject>/<checkpoint>/`：`prompt.md`、`harness.out` / `harness.err`、`gate.out` / `gate.err`、`score.json`。

循环停了或原地打转，先看最后几轮的 `note` 和 best 的 `remaining`：`remaining` 为空 + 连续 discard = 这把尺子已经量到顶，研究完成或该换版本的打分器；`remaining` 不空却连续 discard = agent 在做但分数不动，多半是打分器对它做的事不敏感，或 program 把它引向了别的方向；连续 crash = gate 太严，或 program 让它去改锁定路径；连续 error = 打分器坏了或 harness 起不来，看 `score.err` / `harness.err`。

## 人工介入

| 用户想 | 改什么 | 效果 |
|---|---|---|
| 换方向、加约束 | `subjects/<name>/program.md` | 下一轮的 prompt 就变，不需要动版本 |
| 改"什么算好" | `subjects/<name>/score`，**同时 bump `version`** | 下一轮先在 HEAD 重测作新基线；旧 checkpoint 原样保留，报告换色带 |
| 收紧一票否决 | `subjects/<name>/gate` | 下一轮生效 |
| 调上限、超时、模型、预算 | `research.json` | 下一轮生效，`stopped_reason` 随之重算 |

改 `score` 忘了 bump `version`，新旧分数会被当成同一把尺子比较——每次改 `score` 都要提醒这一句。

改动落在两轮之间最稳（Ctrl-C 一次，等它停在轮次边界）。正好落在一轮进行中：runner 分不清是人改的还是 agent 越界，按越界处理——这一轮 crash 并撤回（agent 的工作一起），但 diff 完整保存在 `artifacts/<subject>/<checkpoint>/locked-changes.patch`，`git apply` 回来即可。

## agent 每轮看到什么

一轮只有一个 prompt：没有历史、没有 diff、没有 git log（它要就自己读）。`run … --dry-prompt` 打印的就是原文，每轮也存在 `artifacts/…/prompt.md`。

- **稳定前缀**（每轮相同）：research 的 description、整份 `program.md`、runner 的五条规则、路径（可改 / 锁定 / gate 命令 / 能否自己跑打分器）。
- **动态尾部**：轮次号、best 的分数与版本、best 的 `details` 与 `remaining`（最多 200 条）、最近几轮各一行（状态、分数、自述前 300 字）。

五条规则在 runner 里、不在文件里，因为它们是账本成立的前提：一轮一个方向（两个改动分数无法归因，discard 会把好的一起扔掉）；不做任何 git 写操作（commit 与 revert 归 runner）；不碰锁定路径；不留临时文件（`git add -A` 会把它一起提交、打分、撤回）；结束时一段自述（假设、改动、预期），它就是后面几轮看到的 `note`。要改的是 `program.md`。

## 四个示例

`ar.py example <name> <dir>` 把 `examples/<name>/` 复制成一个带首个 commit 的 git 仓库；模板里的 `autoresearch/setup.py` 会跑一次，生成这个实例自己的数据（隐藏目标、语料、held-out 集）。

| 示例 | 用来看什么 | 模型 |
|---|---|---|
| `toy` | 机制本身：keep / discard / revert / 版本切换，几秒一轮 | 不需要 |
| `kata` | 两个 subject 的依赖（先写用例、再写实现）；规格写全的小任务一两轮就打满 | `claude` |
| `compress` | **有梯度的研究**：单文件纯 Python 编解码器压一份固定语料，分数 = 压缩后字节 + `codec.py` 自身字节（`direction: min`）。gate 禁掉 `zlib` 等模块、只允许 `codec.py` 变动、往返校验；几十轮内分数一直有得降 | `claude` |
| `retrieval` | **两级管线的模板**：`recall`（召回率 / 召准率）→ `select`（选用率，候选来自 keep 下来的 `recall.py`），都在 held-out 集上打分，`details` 同时给公开集分数——差距就是过拟合；`select` 的 ceiling 是"目标在候选里"的比例。同义词有限，强模型一轮就接近打满 | `claude` |

给用户挑示例时：想看循环跑几十轮的样子用 `compress`；要照着搭自己的多阶段研究用 `retrieval`。两者的每轮代价见技术事实。

## 退出

循环留下三样东西，删掉就回到原状，仓库里没有需要卸载的东西：

```bash
git checkout <原来的分支> && git branch -D research/<name>   # 所有轮次的 commit 都在这条分支上
rm -rf autoresearch && git add -A && git commit -m "remove the autoresearch definition"
rm -rf ../<name>.ar                                          # 账本、产物、报告
```

**先把成果拿回主线再删分支**：`research/<name>` 的 HEAD 就是 best 那棵树，`git merge research/<name>` 即可；删分支等于放弃这次研究的全部产出。想留着复盘就别删，它不影响其他分支。

## 技术事实

当提示，不当保证；不符就以眼前看到的为准，然后更新 `references/known-behaviors.md`——完整清单和数字都在那里。这里只列会改变会话做法的几条：

- (2026-10-08, Claude Code 2.1.294) `claude --help` 不列全部 flag，官方 CLI reference 明说"不在 `--help` 里不等于没有"。`--max-turns`、`--max-budget-usd`、`--no-session-persistence` 都有效（print mode）。上限触发时进程**退出码 1**、JSON 的 `subtype` 为 `error_max_turns` / `error_max_budget_usd`、`result` 为 null——runner 把这种轮次照常打分，不算 error。
- (2026-10-08, 2.1.294) 第三方 Anthropic 兼容端点（GLM 等）：`harness.env` 里给 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`（写成 `"$VAR"`），模型名走 `ANTHROPIC_MODEL`，**不要配 `harness.model`**——`--model glm-5.3` 会被 CLI 以 `unrecognized_model` 拒绝。`total_cost_usd` 是 CLI 按 Anthropic 价格的估算，不是端点的账单，`max_budget_usd` 在那里也就不是预算。
- (2026-10-08, 2.1.294) 每轮是新进程，prompt 缓存跨进程只命中约 11k、每轮重写约 40k token；稳定前缀主要让轮内多个 turn 受益。平凡一轮 18–36 秒、约 $0.4；kata 16 轮中位数 25 秒、$0.435。
- (2026-10-08, codex-cli 0.156.1) `codex exec --json` 在全新仓库里无需 trust 即可无人值守跑；usage 在 `turn.completed` 事件里，没有费用字段。
- (2026-10-08, git 2.54.0) `git revert` 拒绝空 commit：agent 什么都没改的轮次只留一个空 commit，不 revert。
- `kill -9` 杀 runner 不会杀 harness（它在自己的进程组里），还会留下过期的 `run.lock`（下次 run 自动清掉并记一行）。要停就发 SIGINT / SIGTERM。

## References 索引

| 文件 | 何时加载 |
|---|---|
| `references/scorer-guide.md` | init 的第 3–4 步，以及用户任何一次要改"什么算好" |
| `references/known-behaviors.md` | 外部工具行为可疑（CLI 参数、退出码、token、第三方端点），或要回填新观察 |
