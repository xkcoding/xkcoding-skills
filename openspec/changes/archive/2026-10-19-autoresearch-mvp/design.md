# Design

## Context

动机见 proposal.md「Why」。这里只记影响做法的现状与约束。

**参照物一：Koala 俱乐部视频**（2026-09-29 发布，2026-10-08 逐分钟看完）。视频里没有代码、终端或 prompt，能看到的只有报告页、Excalidraw 概念图、讲者笔记大纲和 playground。下表是画面里看到的事实，是本设计的主要依据：

| # | 看到的 | 对设计的含义 |
|---|---|---|
| V1 | 笔记大纲第一条「Research, subject, round」；报告标题 `nano-grafana autoresearch`，下挂 `case-gen`、`render` 两个 subject，各自有 checkpoints / kept / discarded / crashed / best / 打分器版本区间 | Research 是一等概念，报告按 research 出 |
| V2 | 报告路径 `…/nano-grafana-autoresearch.ar/report/index.html`；大纲写「账本（`researches/*.json`）与 commit 分离：message 只带 Checkpoint-Id」 | 账本在仓库旁的 `<research>.ar/`，commit 只带 id |
| V3 | 大纲：每轮一个 commit（`--allow-empty`，append-only）；discard / crash 用 `git revert` 撤回，历史保留失败 | git 语义原样采用 |
| V4 | checkpoint 字段：status、score（带版本）、at、commit、`task` ms、`agent` min、`gate` ms、tokens「out · in · cache read · cache write」；render subject 改为 `observe` / `judge` / `agent` 三段 | 阶段分别计时；usage 四项原样记账；打分器可自报子阶段耗时 |
| V5 | 指标面板「90 cases · 2 redundant · 66/66 gauge values · 1879/1904 pairs」+ 可展开「gauge: 10 values uncovered」；讲者口述：告诉它"当前生成到多少、你自己找没跑过的来修" | 打分器输出结构化 `details` 和 `remaining`，`remaining` 是下一轮的状态载体 |
| V6 | 每个 checkpoint 带一段 agent 自述（"Only the two intended files changed, no stray probe files remain…"） | harness 收尾文本进账本；prompt 要求自述改动范围 |
| V7 | 曲线有 v5.0.0 / v5.1.0 色带；#8 143.6（v5.0.0）之后 #9 140.3（v5.1.0）仍为 keep | 打分器中途可改版本，比较只在同版本内，旧分保留 |
| V8 | #2 `crash`：`vp check failed … Run vp check --fix`，`No measurement recorded` | gate 失败不打分，直接 crash |
| V9 | case-gen #1 00:19 → #21 02:15；render #2 11:06 → #7 13:49；render 的 judge 8.6–17.7 min 大于 agent 6.6 min | 每轮 5–20 分钟、整夜无人值守；打分器成本要计入预算 |
| V10 | 口述：harness 做过 Claude Code 和 Codex，也可用 LLM API；无状态指"开始一轮时不追溯历史，靠文件和账本知道该干嘛" | adapter 可替换；prompt 不带对话历史 |

视频里**没有**的、本设计自行决定的：harness 怎么被拉起、prompt 模板、账本 JSON 的内部切分、subject 之间的并行。

**参照物二：karpathy/autoresearch**。单一可编辑面（`train.py`）、打分代码只读、固定时间预算、`results.tsv` 不入库、没有提升就 `git reset`、永不停止。本设计保留"单一可编辑面 + 打分器只读 + 账本不入库"，不采用 reset 和永不停止。

**本仓库的约束**：skill = 自包含目录（`SKILL.md` + `references/` + `scripts/`），脚本纯标准库、子命令各输出一个 JSON、永不崩溃；外部工具行为标日期和版本。

### 已核对的环境事实（2026-10-08）

| # | 事实 | 来源 |
|---|---|---|
| E1 | 本机 `python3` 为 3.9.6，无 `tomllib` | `python3 --version` |
| E2 | Claude Code 2.1.293：`claude -p` 支持 `--output-format json`、`--max-turns`、`--max-budget-usd`、`--model`、`--dangerously-skip-permissions`、`--permission-mode`、`--allowedTools`、`--no-session-persistence` | `claude --help` |
| E3 | `claude -p --output-format json` 的输出是一个 JSON 对象，含 `result`、`usage`（`input_tokens` / `output_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens`）、`num_turns`、`session_id`、`is_error` | 2026-06 在本机另一个评测 harness 里用过；阶段 2 复核 |
| E4 | 在 Claude Code 会话内嵌套拉起 `claude -p` 需去掉 `CLAUDECODE` 环境变量 | 同上 |
| E5 | codex-cli 0.156.1：`codex exec [PROMPT]` 支持 `--json`（事件 JSONL 到 stdout）、`-o/--output-last-message FILE`、`-s/--sandbox workspace-write`、`-C DIR`、`--skip-git-repo-check`、`-m MODEL`、`--approve-for-me` | `codex exec --help` |
| E6 | 未受信任目录下 codex 默认只读沙箱，带 `--add-dir` 会启动即退出；trust 记在仓库根 | 本仓库 `dispatch/codex/references/known-behaviors.md`（2026-09-18, 0.154–0.155） |
| E7 | git 2.54.0 | `git --version` |

**尚未验证**（阶段 2 实测后回填到 skill 的技术事实）：`git revert` 对空 commit 的行为；`codex exec --json` 事件里 token 用量的字段；GLM / MiniMax 的 Anthropic 兼容端点在 Claude Code 里用哪几个 env（预期 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`，需实测）。

## Goals / Non-Goals

**Goals:**

- 一条命令让一个 subject 无人值守地跑几十轮，中途可 Ctrl-C、可续跑、可改打分器。
- 人看循环只需要一份报告；人介入循环只需要改 `autoresearch/` 下的文件。
- 循环的每个机械步骤都在脚本里，可以不开 Claude Code 会话、用 cron 直接跑。
- 用一个两 subject 的示例研究端到端验证，再接真实项目。

**Non-Goals:**

- 直接调 LLM API 的 adapter（OpenAI / Anthropic SDK 循环）。第三方模型先走 Claude Code 的端点 env。
- 一轮多个候选并行取优（beam search）；subject 并行。
- 自动改打分器、自动 bump 版本。打分器永远是人的杠杆。
- 把 DRR 的打分器做进来。那是下一个 change。
- 自定义 OpenSpec schema、修改任何 OpenSpec 命令。

## Decisions

### D1 外部程序驱动外环；agent 只是每轮的无状态工人

三种形态里只有这一种满足 V9 的数量级（每轮 1–5M cache read、整夜几十轮）：

| 形态 | 为什么不行 |
|---|---|
| skill 自驱（autoresearch 的 program.md 路线） | 循环状态在会话里，几十轮后要么爆上下文要么压缩后忘规矩；预算、超时、停止靠模型自觉 |
| Claude Code 当 driver、每轮 spawn subagent | driver 仍是 LLM 会话，subagent 结果回流累积；没有进程级超时；会话会被压缩 |
| 外部 runner + 每轮 headless harness（视频做法） | runner 是哑的、确定性的，智能全在每轮的 agent 和打分器里 |

skill 的角色因此是人机界面：引导写定义、拉起 runner、读报告；不参与循环。

### D2 Research 一等；定义在仓库内，账本在仓库旁

```
<repo>/autoresearch/                       # 定义，建议提交；默认锁定
  research.json                            # 名称、描述（进 prompt 的稳定前缀）、harness 默认值、subjects 顺序与依赖
  subjects/<name>/program.md               # 这个 subject 的研究目标、约束、可改范围的说明
  subjects/<name>/score                    # 可执行：stdout 输出打分 JSON
  subjects/<name>/gate                     # 可执行：退出码 0 = 通过
<repo>/../<research>.ar/                   # 账本，不入库（V2）
  researches/<subject>/index.json          # subject 汇总：轮次计数、best、当前版本、停止原因
  researches/<subject>/<checkpoint-id>.json
  artifacts/<subject>/<checkpoint-id>/     # prompt.md、harness.out、harness.meta.json、gate.log、score.json、打分器自己写的文件
  runs/<run-id>.log                        # 每次 run 的日志
  report/index.html
```

定义放仓库内的理由：打分器和 program 的每次人工修改都应与代码历史同步可追溯（V7 的版本切换就是一次人工修改）；放仓库旁则无法回答"当时的打分器长什么样"。代价是必须防 agent 改它——见 D4。

账本放仓库旁而不是仓库内 gitignore：视频做法（V2）；且 `.ar` 里会有截图等大文件，不该出现在 `git status` 里干扰 agent。目录名取 research 名，位置 = 仓库父目录；`research.json` 可用 `ar_dir` 覆盖。

**subject 顺序与依赖**：`subjects` 是有序数组，每个可带 `depends_on`；`run` 一次只跑一个 subject，依赖未达成（被依赖 subject 没有任何 keep 的 checkpoint）则拒绝。不做并行：V9 两个 subject 本来就是先后跑的，并行会让同一仓库的 commit 历史交错、revert 互相干扰。

*否决*：只有 subject 没有 research。用户明确要贴近视频；而且 research 描述是 prompt 稳定前缀的来源，两个 subject 共享它。

### D3 打分器契约：自报版本，带缺口清单

```json
{
  "score": 155.95,
  "version": "5.1.0",
  "details": {"cases": 90, "redundant": 2, "values": "66/66", "pairs": "1879/1904"},
  "remaining": ["gauge.orientation=vertical", "gauge.showThresholdMarkers × reduceOptions.calcs=last"],
  "timings_ms": {"observe": 228000, "judge": 516000}
}
```

- `score` 必须是数字，越大越好（`research.json` 可声明 `direction: "min"` 取反）；`version` 必填；`details` 任意 JSON，报告原样展示；`remaining` 字符串数组，可空；`timings_ms` 可选，报告按 key 展示为子阶段（V4 的 observe / judge）。
- 打分器退出码非 0 或输出不是合法 JSON → 本轮结局 `error`（不是 crash，也不是 discard）：revert 本轮、单独计数、连续 `max_consecutive_errors` 次停止。打分器坏了不该消耗 discard 配额，也不该把 agent 的工作算成失败。
- **版本切换**（V7）：runner 在每轮开始读上一次 checkpoint 的 version；本轮 score 的 version 与 best 的 version 不同 → 本轮不与旧 best 比较，直接成为新版本下的基线（status `keep`，报告里曲线换色带），旧 checkpoint 原样保留。
- **人改了打分器**：runner 要求树干净才开始一轮；唯一的例外是改动只落在 `autoresearch/` 内——此时 runner 先单独提交 `ar scorer <subject>`（路径限定的 commit），再开始本轮。这样打分器的变更在 git 历史里是独立的一笔，不会混进 agent 的 commit。

*否决*：版本写在 `research.json` 里由人维护。会漏改；由打分器代码自报，改代码时顺手改版本号更自然。

### D4 gate 与 score 分离；边界违规按 crash

一轮的结局判定顺序：

1. **边界**：`git status --porcelain` 的变更路径与 `locked` 匹配（默认 `autoresearch/**`，可加）→ `crash`，reason `locked:<path>`。
2. **gate**：执行 `gate`，非 0 → `crash`，reason 取 stderr 末尾；不打分（V8）。
3. **score**：按 D3。
4. 同版本下 `score > best` → `keep`；否则 `discard`。相等算 discard：分数没动就是没进展，"少 token 但分数相同"这类收益应写进分数而不是另开规则。

agent 在一轮里**可以自己跑 gate**（它就是 lint，越早知道越好），**默认不能跑 score**（`subject.agent_may_score: false`）——打分可能很贵（V9 的 judge），且让 agent 对着测试集反复打分会过拟合；需要的 subject 自行打开。

### D5 git：research 分支、每轮一个 commit、revert 不 reset

- `run` 要求：工作树干净（D3 的例外除外）、当前在 `research/<research>` 分支（不在则从当前 HEAD 创建）。推荐用户先 `git worktree add` 再在 worktree 里跑，runner 不替用户建 worktree（monorepo 里建在哪、叫什么都是用户的事）。
- 每轮结束 `git add -A && git commit --allow-empty -m "ar <checkpoint-id>"`（V3）。message 只带 id，状态、分数都在账本（V2）。
- `discard` / `crash` / `error` → `git revert --no-edit HEAD`；本轮 commit 为空（agent 没改东西）则不 revert，账本记 `reverted: null`。revert 失败（理论上只会因为工作树不干净）→ runner 停止并报告，不自动 `reset`。
- `keep` 不动。下一轮从 HEAD 开始，HEAD 恒等于当前 best 的工作树状态。

*否决*：`git reset --hard` 回滚（autoresearch 做法）。失败轮次从历史里消失，无法复盘（视频明确反对）。

### D6 Checkpoint-Id 与账本切分

- id = `<subject>-<n>-<6 位 hex>`，`n` 从 0 起（0 = 基线）。commit message `ar <id>`；revert commit 保留 git 默认 message（含原 id）。
- 账本每个 checkpoint 一个 JSON（V2 只说明了目录名 `researches/`，内部切分是本设计决定）：

```json
{
  "id": "case-gen-21-23b28e", "n": 21, "subject": "case-gen", "status": "keep",
  "at": "2026-10-08T02:15:00+08:00", "commit": "23b28ee1b5", "reverted_by": null,
  "score": 155.95, "version": "5.1.0", "best_before": 155.4,
  "details": {...}, "remaining": [...],
  "timings_ms": {"agent": 342000, "gate": 925, "score": 531, "observe": 0, "judge": 0},
  "usage": {"input": 54, "output": 14856, "cache_read": 1077096, "cache_write": 41219},
  "harness": {"type": "claude", "model": "...", "session_id": "...", "turns": 31, "exit": 0},
  "note": "All 5 cases written successfully, covering 11 of the 36 remaining missing pairs …",
  "changed_files": ["cases/gauge-…json"], "reason": null
}
```

`index.json` 只放汇总（`n_next`、`best`、`best_id`、`version`、`consecutive_discards`、`consecutive_errors`、`stopped_reason`、`totals`），删掉它可以从各 checkpoint 文件重建。

### D7 Prompt 组装：稳定前缀 + 动态尾部

V9 里 cache read 占 token 的 95% 以上，prompt 的结构直接决定费用：

```
[稳定前缀 — 跨轮不变]
  research.description
  subjects/<name>/program.md 全文
  规则：一轮只做一个方向的改动；不要 commit；不碰 locked 路径；可以跑 gate（命令给出）；结束时用一段话写明：假设 → 改了什么 → 预期；不要创建探测用的临时文件
  路径：可改范围 editable、锁定 locked、gate 命令、仓库根
[动态尾部 — 每轮变化]
  本轮 id、当前 best（分数、版本）、best 的 details 与 remaining（V5：这是"你还差什么"）
  最近 K 轮（默认 5）的一行摘要：n、status、score、note 前 300 字
```

harness 的最终文本输出原样进账本 `note`（V6）。不把 git log、diff 喂进 prompt——需要的话 agent 自己会看。

### D8 harness adapter：统一接口，三种实现

接口：`run(prompt, cwd, timeout_sec, env) → {exit, text, usage, meta}`；`usage` 归一化为 `input / output / cache_read / cache_write`，拿不到的填 `null`。

| adapter | 命令 | 备注 |
|---|---|---|
| `claude` | `claude -p <prompt> --output-format json --max-turns N [--model M] [--max-budget-usd X] --dangerously-skip-permissions --no-session-persistence` | 去掉 `CLAUDECODE` env（E4）；`usage` 从 JSON 取（E3）；第一版用订阅登录 |
| `codex` | `codex exec <prompt> --json -o <file> -s workspace-write -C <cwd> --skip-git-repo-check [-m M]` | `text` 读 `-o` 文件；`usage` 从 JSONL 事件解析，字段未验证则填 `null`；trust 弹层会让它启动即退出（E6），doctor 里提示 |
| `shell` | `research.json` 里给的任意命令，prompt 经 stdin 传入 | 自测与自定义 harness 用；`usage` 全 `null` |

共同约定：prompt 走 argv 或 stdin，不过 shell 解析；`start_new_session=True` 起进程组，超时 `SIGKILL` 整组；stdout / stderr 落 `artifacts/…/harness.out`。

**第三方端点**：`research.json` 的 `harness.env` 原样透传给子进程（支持 `$VAR` 引用宿主环境变量，避免把 key 写进文件）。GLM / MiniMax 的 Anthropic 兼容端点预期只需 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`（+ 模型名），是否够用阶段 2 之后实测，列为任务 4.5。

*否决*：直接调 LLM API 的 adapter。要自己实现工具循环，和"agent 读 program.md 自己干活"的前提冲突；留作后续 change。

### D9 停止条件与续跑

- 停止：`max_rounds`、`max_consecutive_discards`、`target_score`、`budget.minutes`、`budget.tokens`（四项之和）、`max_consecutive_errors`；任一命中写 `index.json.stopped_reason` 并退出 0。
- Ctrl-C：收到 SIGINT 后让当前 harness 跑完（再按一次立即杀进程组），本轮照常 gate / score / commit / 记账，然后退出。半轮状态不会出现在账本里；若被 `SIGKILL`，下次 `run` 发现工作树不干净 → 拒绝并指出是上次残留，由人决定 commit 还是丢弃。
- 续跑：`run` 从 `index.json` 读 `n_next` 和 best，HEAD 必须等于 best 的 commit（或其 revert 链末端），否则拒绝。

### D10 报告：单文件静态 HTML

从账本生成 `report/index.html`：数据内嵌为 JSON，vanilla JS 渲染，无外部依赖。每个 subject：标题行（`N checkpoints · K kept · D discarded · C crashed · E errors · best X at #n · score vA → vB · updated`）、SVG 折线（按版本分色带，discard / crash 用空心点或红叉）、checkpoint 列表、点击展开详情（D6 的全部字段 + `details` 表格 + `remaining` 折叠列表）。每轮结束重新生成一次（毫秒级）。

### D11 配置用 JSON

E1：3.9 没有 `tomllib`，不引入第三方解析器。`research.json` 允许 `_doc` 键作注释。`init` 生成的模板里每个字段带 `_doc`。

### D12 示例研究 `examples/kata`：仿视频的两 subject

目的：阶段 2 的真实试跑对象，也是 `init` 生成骨架的范本。选"query string 解析器"这种规格小、确定性强、agent 一轮能推进的题目。

- `cases`（仿 case-gen）：`spec/features.json` 列出约 12 个特性（键值对、重复键成列表、百分号解码、`+` 作空格、空值、缺 `=`、`a[]=1` 数组、`a[b]=1` 嵌套、布尔标志、保持顺序……）。agent 往 `cases/` 写 `{input, expected, features[]}`。打分器用锁定目录里的参考实现校验 `expected`，不一致的 case 不计分；分数 = 覆盖特性 ×1 + 覆盖两两组合 ×0.05 − 冗余（特性集合完全相同）×2，即视频的公式；`remaining` = 未覆盖的特性和组合。
- `impl`（仿 render，`depends_on: cases`）：agent 写 `src/qs.py`；gate = `python3 -m py_compile`；打分器逐 case 子进程运行（超时 2s），分数 = 通过数，`remaining` = 失败 case 的 id 与期望/实际摘要。

阶段 1 另用一个不需要 LLM 的玩具（`shell` harness 随机扰动一个向量，打分器算与隐藏目标的负距离）验证循环机制本身。

## Risks / Trade-offs

- [打分器被 agent 绕过或改写] → `autoresearch/**` 默认锁定，边界检查在 gate 之前；prompt 明说；报告里 `changed_files` 可人工抽查。锁定只能防改文件，防不了"把答案硬编码进实现"这类作弊——那是打分器设计的问题（kata 的 `impl` 打分器用隐藏在锁定目录里的 case 副本）。
- [LLM 判分有随机性，同一代码两次分数不同] → 不在 runner 层做去噪（没有通用办法）；打分器自己决定是否重复采样取均值；相等算 discard 避免靠噪声"进步"。
- [订阅限流 / 单轮超时] → `timeout_sec` 杀进程组；harness 非 0 退出按 `error` 记，连续 N 次停止；限流表现在阶段 2 实测后写进技术事实。
- [agent 把临时文件留在仓库里] → `git add -A` 会把它们带进 commit；prompt 要求不留探测文件（V6 说明这是可以被要求的），`changed_files` 在报告里可见；kata 的 gate 可加"仓库里不得出现 `*.tmp`"。
- [codex adapter 没验证过] → 阶段 2 以 `claude` 为主；codex 的 usage 字段拿不到就填 `null`，不阻塞。
- [revert 的 commit 让历史变长] → 这是视频刻意的选择（可复盘）；report 和 `git log --oneline` 都能一眼看出 revert 对。
- [人改 program.md 不改版本] → prompt 变了但分数可比，不算问题；只有打分器变了才需要版本。

## Migration Plan

无迁移。退出：删除目标仓库的 `autoresearch/` 目录、`research/<name>` 分支和 `<research>.ar/` 目录，仓库回到原状。本仓库侧卸载插件即可。

## Open Questions

- GLM / MiniMax 在 Claude Code 里的接入 env 是否只需 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`；模型名怎么传。阶段 2 试跑稳定后单独验证，不影响接口（走 `harness.env`）。
- `codex exec --json` 的事件里有没有 token 用量。有就填，没有就 `null`，不影响接口。
