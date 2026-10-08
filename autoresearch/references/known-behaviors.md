# 已知行为——claude / codex / 第三方端点 / git

循环靠几个外部 CLI 立足，而它们都会随版本变。下面每条都标了观察日期与当时的版本。**当作可能有效的提示，不当保证**：照它做却不符，以眼前看到的为准，然后回来更新这份文件——只写验证过的事实，没验证的单列在最后一节。

## Claude Code（`claude`）

- (2026-10-08, 2.1.294) **`claude --help` 不列全部 flag。** 官方 CLI reference（code.claude.com/docs/en/cli-reference）明写 "a flag's absence from `--help` does not mean it is unavailable"。`--max-turns` 不在 `--help` 里，但有效。所以 adapter 不看 `--help`，直接传 reference 里有的 flag；CLI 真不认时这一轮会以它自己的报错记为 error，不会静默少传。
- (2026-10-08, 2.1.294) **`--max-turns N` 真的截断**（print mode）。要求三次独立 Bash 调用、`--max-turns 1`：返回 `subtype: "error_max_turns"`、`is_error: true`、`num_turns: 2`、`result: null`、`stop_reason: "tool_use"`，**进程退出码 1**。stdout 仍是完整 JSON，usage 齐全。runner 把 `error_max_turns` / `error_max_budget_usd` 当作"上限起作用了"：照常边界检查、gate、打分；`harness.cut_off` 记下是哪个。
- (2026-10-08, 2.1.294) **`--max-budget-usd` 触发时同样形状**：`subtype: "error_max_budget_usd"`、`is_error: true`、`result: null`。上限按 CLI 自己的客户端估价算（官方文档："client-side cost estimate, which can differ from your bill"），`--max-budget-usd 0.01` 一轮实际记了 $0.76——第一次 API 调用之后才判定。
- (2026-10-08, 2.1.294) **`-p --output-format json` 返回一个对象**：`result`、`usage.input_tokens` / `output_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens`、`num_turns`、`session_id`、`is_error`、`subtype`、`total_cost_usd`、`stop_reason`。四个 usage 数和 session id 都有值。
- (2026-10-08, 2.1.294) **在 `CLAUDECODE=1` 的环境里 `claude -p` 照常运行**（从一个 Claude Code 会话里直接起子进程，exit 0、JSON 正常）。adapter 仍然去掉 `CLAUDECODE`、`CLAUDE_CODE_SSE_PORT`、`CLAUDE_CODE_ENTRYPOINT`，因为它们描述的是父会话，不该传给一个本该独立的子进程；这不是为了绕开某个已观察到的故障。
- (2026-10-08, 2.1.294) **平凡一轮的代价**：单文件仓库、订阅登录、prompt 约 1.5k token，6 轮：18–36 秒，3 个 turn，输出 540–665 token，`total_cost_usd` 0.40–0.42。
- (2026-10-08, 2.1.294) **prompt 缓存跨进程只命中一小部分。** 同一目录、一分钟内连续两个新进程：第二个 `cache_read` 10.8k、`cache_write` 40.7k；另一次 14.5k / 37.1k。kata 真跑的每轮也是 cache_write 46–49k。带与不带 `--exclude-dynamic-system-prompt-sections` 各测 2 轮，差别在噪声内；flag 仍然传（它把 git 状态这种每轮必变的段落移出系统提示）。稳定前缀的收益主要在轮内：一轮多个 turn，turn 2..n 读的是 turn 1 写的缓存（kata 每轮 cache_read 118–122k 就是这个）。

## Codex（`codex`）

- (2026-10-08, codex-cli 0.156.1) `codex exec <prompt> --json -o FILE -s workspace-write -C DIR --skip-git-repo-check` 在全新 git 仓库里**无需 trust 弹层**即可无人值守跑。
- (2026-10-08, 0.156.1) **事件流**：`thread.started`（带 `thread_id`）、`turn.started`、`item.started` / `item.completed`、`turn.completed`。usage 在 `turn.completed` 上：`input_tokens`、`cached_input_tokens`、`cache_write_input_tokens`、`output_tokens`、`reasoning_output_tokens`。adapter 取前四个映射成 `input` / `cache_read` / `cache_write` / `output`；没有费用字段。
- (2026-10-08, 0.156.1) 同一个平凡 prompt：56 秒、input 76.5k、cached 63.4k、output 346。比 Claude Code 慢、输入更重。
- (2026-09-18, 0.154–0.155) 未受信任目录下用 `--add-dir` 会让 codex **启动即退出**；trust 记在仓库根上。adapter 不传 `--add-dir`，`doctor` 仍会提醒。

## 第三方 Anthropic 兼容端点

- (2026-10-08, Claude Code 2.1.294, GLM 5.3) **两个环境变量就够**：`ANTHROPIC_BASE_URL`（GLM 是 `https://open.bigmodel.cn/api/anthropic`）和 `ANTHROPIC_AUTH_TOKEN`。写进 `harness.env` 时用 `"$VAR"` 引用，key 不进仓库；变量没设 runner 拒绝启动。
- (2026-10-08, 2.1.294) **模型名必须走 `ANTHROPIC_MODEL`，不能用 `--model`。** `--model glm-5.3` 被直接拒绝：stderr `[claude-code:unrecognized_model] {"model":"glm-5.3","query_source":"sdk"}`，什么都不跑。`ANTHROPIC_MODEL=glm-5.3` 且不传 `--model`，同一行出现一次在 stderr，轮次正常。所以第三方端点不要配 `harness.model`。
- (2026-10-08, GLM 5.3) **usage 回来是同样四个字段**：往 README 追加一行的一轮——input 213216、cache_read 375872、cache_write 0、output 696、6 个 turn、181 秒。`total_cost_usd`（那一轮 1.22）是 Claude Code 按 Anthropic 价格的估算，不是端点的账单，不能拿来当预算；`max_budget_usd` 在这里也就不是真正的上限。
- (2026-10-08) 同一轮在端点上比订阅**慢得多、输入重得多**：181 秒 vs 18–36 秒，213k input vs 6。

## git

- (2026-10-08, git 2.54.0) **`git revert` 拒绝空 commit**（`nothing to commit`）。runner 比较轮次 commit 与父 commit 的 tree，agent 什么都没改就跳过 revert；空 commit 留在历史里，证明这一轮发生过。
- (2026-10-08) **`kill -9` 杀 runner，harness 会活着。** 每个 harness 在自己的进程组里（这样终端的 Ctrl-C 才打不到它），所以 SIGKILL runner 等于遗弃它。停循环发 SIGINT 或 SIGTERM；SIGKILL 之后再启动前，看看有没有残留的 `claude` / `codex` 进程。过期的 `run.lock` 下次 run 会自动替换并记一行。
- (2026-10-08, 2.54.0) 边界检查读的是 `git status --porcelain -z --untracked-files=all`：agent 新建却没 add 的文件也是它的改动，`git add -A` 会把它提交进这一轮。

## 循环本身

- (2026-10-08, Claude Code 2.1.294) **kata 无人值守 16 轮的代价**：两个 subject、订阅登录、prompt 约 2k token：每轮 15–135 秒（中位 25 秒）、$0.40–$0.61（中位 $0.435，16 轮合计 $7.17）、cache_read 约 121k、cache_write 约 49k、2–4 个 turn。没事可做的一轮也是完整一轮的价钱：agent 读仓库、得出没什么可加、说一句。
- (2026-10-08) 订阅账号 15 分钟内约 25 轮，**没有碰到限流**。
- (2026-10-08) 那些轮次里 agent **没留下任何临时文件**；有一轮的自述明说它压掉了 `__pycache__` 以保持树干净。研究仓库仍然值得放一个 `.gitignore`，因为 `git add -A` 会扫进一切没被忽略的东西。
- (2026-10-08) **一轮进行中落下的打分器手改，被当作越界处理。** runner 分不清是谁改的，保护打分器优先：这一轮 `crash`、reason `locked:<path>`、整轮撤回（agent 的工作一起）。diff 写在 `artifacts/<subject>/<checkpoint>/locked-changes.patch`，`git apply` 能恢复——真的发生过一次，就是这样恢复的。改动落在两轮之间，或先停循环。
- (2026-10-08, Claude Code 2.1.294) **kata 大小、规格写全的研究一两轮就打满。** 示例 kata 的 `cases` 第一轮 0 → 12/12 特性、40/66 组合，第二轮 66/66，共 26 个用例；`impl` 第一轮就通过全部 26 个。之后全是 discard，直到连续 discard 上限停下。要跑几十轮的研究，打分器的上限得远高于强模型一轮能到的地方——见 scorer-guide 里"一轮能打满"那一条。

## 示例研究真跑的结果

- (2026-10-08, Claude Code 2.1.294, sonnet) **`retrieval`：两级管线各自一轮就接近打满，然后按连续 discard 上限自动停。** `recall` 基线 28.2 → 第 1 轮 98.7 → 第 8 轮 100.0（召回 1.0、召准 1.0），之后 8 轮全是 discard，17 个 checkpoint、$4.17、中位 36 秒/轮；`select` 等 `recall` keep 之后自动可跑，基线 95.0（候选已经排得很好）→ 第 3 轮 99.75（ceiling 100%，隐藏集只剩 1 条）→ 连续 8 轮 discard 停，12 个 checkpoint、$3.47。同义词是有限集合，模型一轮就把中英同义词、hex 色相、`difflib` 容错写全——可枚举的合成任务对强模型都是这样。
- (2026-10-08, sonnet) **公开 / 隐藏差距真的能看见过拟合。** `select` 第 1 轮专门修公开集的 miss：公开 99.5、隐藏 97.5，`gap_public_minus_heldout` = 2.0；到第 3 轮两边都接近 100，差距收到 0.25。`recall` 全程差距 ≤ 1.1，说明它学的是语言不是题。
- (2026-10-08, Claude Code 2.1.294, sonnet) **`compress` 跑满 31 轮一直有梯度，没有触发任何停止条件。** 基线 105248 → #1 38694（opus，order-2 上下文模型 + 二进制算术编码）→ #2 29719（五阶逻辑混合）→ #8 28275 → #17 27973 → #29 **27869**（语料 26035 + `codec.py` 1834 字节，4.04×），32 个 checkpoint、21 keep、11 discard、0 crash、0 error。discard 从第 9 轮开始出现、后半段成串（`KKKKKKKKKdKdKKKdKKdKKKdddKddKKdd`），每次 keep 从几百字节缩到个位数——研究后期就长这样。sonnet 的 30 轮：中位 $0.28、108 秒/轮（51–276 秒），全程 $11.76。逐文件：repeats.txt 27.6×、orders.csv 7.9×、events.jsonl 7.0×、zh.txt 5.8×、source.py 4.0×、english.txt 3.6×、noise.bin 1.00×（多 1 字节，正确）。gate 0 次失败：agent 每轮都先自己跑 gate 再停。
- (2026-10-08, 2.1.294) **同一任务 opus 与 sonnet 的一轮代价差一个数量级。** `compress` 第 1 轮用 opus：18 个 turn、7 分钟、$3.20（一轮就写出 order-2 上下文模型 + 算术编码，105248 → 38694）；换 sonnet 之后每轮 50–110 秒、中位 $0.31，而且每轮仍是一个具体的压缩技术（混合、更长上下文、SSE、权重组选择……）。要看循环本身的形态，弱一点的模型反而更合适：梯度更长、discard 更多。

## 未验证

- MiniMax 等其它兼容端点：只试过 GLM。两个变量的形状大概率相同，但模型名的处理正是 GLM 上和官方不同的那一点，换端点先核这一处；不成立就看 stderr 第一行，它会说认不认这个模型名。
- 长时间无人值守下订阅账号的限流：这些跑法里没碰到。碰到的话 harness 会非零退出、这一轮记 error，连续 `max_consecutive_errors` 次就停。
- `--max-budget-usd` 以外的 `is_error` 子类型：只见过 `error_max_turns` 和 `error_max_budget_usd`。其它子类型 runner 一律记为 error（`harness_error:<subtype>`），reason 里带着原文。
