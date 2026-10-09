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
  is measured while it runs, or invokes /autoresearch with init / run / serve / status / report /
  doctor / example.
argument-hint: '[init | run <subject> | serve | status [<subject>] | report | doctor | example toy|kata|compress|retrieval <dir>]'
metadata:
  author: xkcoding
  version: "0.3.0"
---

# /autoresearch

把一个**可度量**的目标交给会话之外的循环：`ar.py` 每一轮拉起一个全新的 agent，给它 program、当前最好成绩和缺口清单；它改完退出，打分器打分，比 best 好就留下，否则 `git revert`。

没有任何一轮发生在这个会话里。会话做三件事：**和用户把打分器与 program 写出来、把循环启动起来、读账本回答"现在怎么样了"**。用用户的语言回复；写进目标仓库的 program、commit 用英文。

## 子命令

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ar.py" <子命令> … --repo <目标仓库>
```

每个子命令打印一个 JSON；`"ok": false` 时 `error` 写着为什么拒绝——原样转述给用户，不要替他绕过去。

| 输入 | 做什么 |
|---|---|
| 不带子命令 | `status`：有 research 就[读进度](#读进度)，没有就走 [init](#init) |
| `init [--subject S …] [--harness claude\|codex\|shell]` | 出骨架 → [init](#init) |
| `run <subject> [--rounds N] [--dry-prompt]` | 跑循环 → [run](#run)；`--dry-prompt` 只打印下一轮的 prompt |
| `status [<subject>]` | [读进度](#读进度) |
| `serve [--port N] [--no-open]` | 起本地服务，报告在固定 URL 上自己刷新 → [run](#run) |
| `report` | 重新生成静态报告；有 serve 在跑时输出里带它的 `url` |
| `doctor` | 只读体检：工具版本、仓库状态、定义是否齐全、`harness.env` 的变量是否已设。`problems` 非空先解决，**不替用户安装或登录** |
| `example toy\|kata\|compress\|retrieval <dir>` | 生成示例 research → [示例](#示例) |

## 原则

- **agent 只认分数。** 没有分项的维度不会得到投入；打分器对真正在意的改动不敏感，曲线会涨而东西没变好，而且要烧几十轮才看得出来。会话的时间花在打分器上，不是 program。
- **会话只读不写。** runner 每轮开始要求工作树干净；要改的只有 `autoresearch/` 下的定义文件，runner 会把手改单独提交成 `ar scorer <subject>`，下一轮生效。
- **harness 无状态，`remaining` 是它唯一的记忆。** 打分器给不出"还差什么"，循环只能随机试探。

## init

`init` 出的骨架能直接跑，但打分器是占位（数 `.md` 文件）。按顺序：

1. **问清三件事**（`AskUserQuestion` 一次问完）：度量什么、怎么变成一个数；agent 可以改哪些路径、哪些东西改了会让分数虚高（测试集、期望值、参考实现——都要锁）；什么时候停。第一件答不上来就不要 init。
2. **`init`**，带 subject 名；多个 subject 的 `depends_on`（后者要等前者 keep 过一轮）由用户定。
3. **写 `score` 并手跑三次验证**，按 `references/scorer-guide.md`——契约、`remaining` 怎么导出、怎么验灵敏度和一轮能推多少，都在那里。
4. **写 `program.md`**：只写这个 subject 特有的目标、材料、度量方式、约束；"一轮一个方向、不 commit、不碰锁定路径、结束自述"这些规则 runner 每轮自己加。
5. **`gate`**：快而便宜的一票否决（编译、lint、冒烟）；没有就留 `exit 0`。
6. **`research.json`**：每个键旁有 `_doc`。两处容易误解：`locked` 是强制（改到即 crash，`autoresearch/**` 永远在），`editable` 只是进 prompt 的提示；`harness.env` 写 `"$VAR"`，key 不进仓库。拼错的键会被拒绝。
7. **`doctor` → `run <subject> --dry-prompt`**（给用户看 agent 每轮看到的全部；这一步会建并切到 `research/<name>` 分支）→ **`run <subject> --rounds 1`** 前台跑一轮（先在 HEAD 测基线 #0，再跑 #1），和用户一起读报告里 #1 的分数、`remaining`、改了哪些文件，都对了才放后台。

## run

前台：进度在 stderr；Ctrl-C 一次 = 做完这轮再停，两次 = 杀掉 harness、这轮不记账。无人值守放后台（Bash 后台模式或 `nohup … &`），同时把 `serve` 也放后台，告诉用户四样：报告 URL（`serve` 输出的第一个 JSON 里）、日志 `<研究名>.ar/runs/<run-id>.log`、停法（SIGINT / SIGTERM，**不要 `kill -9`**——harness 在自己的进程组里，会被遗弃；serve 同样 SIGINT / SIGTERM）、回来看 `/autoresearch status`。

开跑前的守卫（锁、脏树、分支、依赖、历史、坏 checkpoint）runner 自己做，拒绝时转述即可。打分器自 best 之后改过，下一次 run 先在 HEAD 重测作为新基线；`--rounds 0` 只做这一件事。

## 读进度

先念 `status` 的 `summary`，再看：`active_run` 非空 = 正在跑；`stopped_reason` 非空 = 按自己的条件停了，再 run 也立刻停，要继续就改 `research.json` 的上限；`scorer_changed_since_best` = 下次先重测基线；`unreadable` 非空 = 账本有坏文件，修好才能 run。

四种结局：**keep**（同版本下更好）、**discard**（相等或更差）、**crash**（改了锁定路径或 gate 失败，不打分）、**error**（harness 或打分器坏了，不占 discard 配额）。

报告是给人看的：有 serve 就给 URL，页面自己刷新；没有就 `open` `report` 给出的路径（静态快照，运行中不会自己更新）。页面只摆事实、不下判断，判断按下一段。每轮的原始材料（含 `changes.patch`）在 `<研究名>.ar/artifacts/<subject>/<checkpoint>/`。

卡住时看 best 的 `remaining` 和最近几轮的 `note`：`remaining` 为空 + 连续 discard = 这把尺子量到顶了，换版本或结束；`remaining` 不空却连续 discard = 打分器对 agent 做的事不敏感，或 program 把它引偏了；连续 crash = gate 太严或 program 让它改锁定路径；连续 error = 打分器或 harness 坏了，看 `score.err` / `harness.err`。

## 人工介入

| 用户想 | 改什么 | 下一轮 |
|---|---|---|
| 换方向、加约束 | `program.md` | prompt 随之变，不用动版本 |
| 改"什么算好" | `score`，**同时 bump `version`** | 先在 HEAD 重测作新基线，旧 checkpoint 保留 |
| 收紧一票否决 | `gate` | 生效 |
| 调上限、超时、模型、预算 | `research.json` | 生效 |

改动落在两轮之间最稳（Ctrl-C 一次等它停）。落在一轮进行中的手改会被当作 agent 越界：这轮 crash 并撤回，diff 存在 `artifacts/<subject>/<checkpoint>/locked-changes.patch`，`git apply` 回来。

## 示例

`example <name> <dir>` 把 `examples/<name>/` 复制成带首个 commit 的仓库，模板的 `setup.py` 生成这个实例的数据。

- `toy`：不需要模型，几秒一轮，看机制。
- `kata`：两个 subject 的依赖；规格写全的小任务一两轮打满。
- `compress`：**有梯度**——纯 Python 编解码器压固定语料，分数 = 压缩字节 + 编解码器自身字节，几十轮一直有得降。
- `retrieval`：**多阶段模板**——召回 → 选用，held-out 打分，公开 / 隐藏差距即过拟合；一两轮打满。

每轮代价见各自 README。

## 退出

```bash
git checkout <原来的分支> && git branch -D research/<name>   # 先 git merge research/<name> 把成果拿回来；删分支等于放弃
rm -rf autoresearch && git add -A && git commit -m "remove the autoresearch definition"
rm -rf ../<name>.ar
```

## 技术事实

当提示，不当保证；不符以眼前为准，再更新 `references/known-behaviors.md`。

- (2026-10-10, Claude Code 2.1.295) 第三方 Anthropic 兼容端点（GLM 等）：`harness.env` 给 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_MODEL` + `CLAUDE_CODE_MAX_CONTEXT_TOKENS`（模型的真实窗口，GLM 5.3 是 `"1000000"`；不给，Claude Code 对不认识的名字按 200k 算，轮内会提前压缩），**不要配 `harness.model`**（`--model glm-5.3` 会被拒）。`total_cost_usd` 是按 Anthropic 价格的估算，在端点上不是账单。
- (2026-10-08, 2.1.294) 一轮的代价差一个数量级：kata 这种平凡轮次约 $0.4、25 秒；compress 这种要真干活的轮次 opus $3.2 / 7 分钟，sonnet $0.3 / 2 分钟。放后台前先和用户对一次预算。

## References 索引

| 文件 | 何时加载 |
|---|---|
| `references/scorer-guide.md` | init 第 3 步，以及用户任何一次要改"什么算好" |
| `references/known-behaviors.md` | 外部工具行为可疑（CLI 参数、退出码、token、第三方端点），或要回填新观察 |
| `scripts/vendor/README.md` | 要升级报告里内嵌的 ECharts 时：版本、来源、怎么换 |
