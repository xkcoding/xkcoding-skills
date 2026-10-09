# 已知行为——claude / codex / 第三方端点 / git

每条都标观察日期与版本。**当作可能有效的提示，不当保证**：不符就以眼前为准，再回来更新这份文件；没验证的单列在最后。

## Claude Code（`claude`）

- (2026-10-08, 2.1.294) **`claude --help` 不列全部 flag**——官方 CLI reference 明说 "a flag's absence from `--help` does not mean it is unavailable"。`--max-turns` 不在 `--help` 里但有效。adapter 直接传 reference 里的 flag，CLI 不认时这一轮以它自己的报错记为 error。
- (2026-10-08, 2.1.294) **`--max-turns` / `--max-budget-usd` 触发时**：`is_error: true`、`subtype` 为 `error_max_turns` / `error_max_budget_usd`、`result: null`、**进程退出码 1**，stdout 仍是完整 JSON、usage 齐全。runner 把这两种当作"上限起作用了"，照常 gate、打分，`harness.cut_off` 记下是哪个。预算按 CLI 的客户端估价算，`--max-budget-usd 0.01` 一轮实际记了 $0.76——第一次 API 调用之后才判定。
- (2026-10-08, 2.1.294) `-p --output-format json` 返回：`result`、`usage.{input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens}`、`num_turns`、`session_id`、`is_error`、`subtype`、`total_cost_usd`、`stop_reason`。
- (2026-10-08, 2.1.294) `CLAUDECODE=1` 的环境里 `claude -p` 照常运行。adapter 仍去掉 `CLAUDECODE` / `CLAUDE_CODE_SSE_PORT` / `CLAUDE_CODE_ENTRYPOINT`——它们描述的是父会话，不是为了绕开某个故障。
- (2026-10-08, 2.1.294) prompt 缓存跨进程只命中一小部分：连续两个新进程，第二个 cache_read 约 11–14k、cache_write 约 37–41k。带不带 `--exclude-dynamic-system-prompt-sections` 没有可测的差别，仍然传。稳定前缀的收益在轮内（turn 2..n 读 turn 1 写的缓存）。

## Codex（`codex`）

- (2026-10-08, codex-cli 0.156.1) `codex exec <prompt> --json -o FILE -s workspace-write -C DIR --skip-git-repo-check` 在全新仓库里无需 trust 弹层。事件流 `thread.started`（`thread_id`）→ `turn.started` → `item.*` → `turn.completed`；usage 在 `turn.completed`：`input_tokens`、`cached_input_tokens`、`cache_write_input_tokens`、`output_tokens`，没有费用字段。同一个平凡 prompt 56 秒、input 76.5k，比 Claude Code 慢且输入重。
- (2026-09-18, 0.154–0.155) 未受信任目录下用 `--add-dir` 会让 codex 启动即退出；adapter 不传 `--add-dir`。

## 第三方 Anthropic 兼容端点

- (2026-10-08, Claude Code 2.1.294, GLM 5.3) `ANTHROPIC_BASE_URL`（GLM：`https://open.bigmodel.cn/api/anthropic`）+ `ANTHROPIC_AUTH_TOKEN` 两个变量就够；`harness.env` 里写 `"$VAR"`，变量没设 runner 拒绝启动。
- (2026-10-08, 2.1.294) 模型名必须走 `ANTHROPIC_MODEL`：`--model glm-5.3` 被 `[claude-code:unrecognized_model]` 直接拒绝；设了环境变量、不传 `--model`，同一行在 stderr 出现一次但轮次正常。
- (2026-10-08, GLM 5.3) usage 同样四个字段；一轮 181 秒、input 213k（订阅上同一轮 18–36 秒、input 6）。`total_cost_usd` 是按 Anthropic 价格的估算，不是端点账单，`max_budget_usd` 在这里不是真正的上限。

## git

- (2026-10-08, git 2.54.0) `git revert` 拒绝空 commit，所以 agent 什么都没改的轮次只留一个空 commit、不 revert。
- (2026-10-08) `kill -9` 杀 runner，harness 会活着（它在自己的进程组里），还留下过期的 `run.lock`（下次 run 自动替换）。停循环发 SIGINT / SIGTERM。
- (2026-10-08, 2.54.0) 边界检查读 `git status --porcelain -z --untracked-files=all`：agent 新建没 add 的文件也算它的改动，会被 `git add -A` 提交进这一轮。

## 循环本身

- (2026-10-08, 2.1.294, 订阅) **平凡轮次的代价**：kata 16 轮中位 25 秒、$0.435（合计 $7.17），没事可做的一轮也是完整一轮的价钱。15 分钟 25 轮没碰到限流。agent 没留过临时文件，但仓库仍要有 `.gitignore`。
- (2026-10-08) **一轮进行中落下的打分器手改被当作越界**：这轮 crash、整轮撤回，diff 在 `artifacts/<subject>/<checkpoint>/locked-changes.patch`，`git apply` 能恢复（真的发生过一次）。
- (2026-10-08, 2.1.294) **可枚举的合成任务对强模型一两轮就打满**：kata 的 `cases` 第二轮 66/66；`retrieval` 的 `recall` 第 1 轮 28 → 98.7、第 8 轮 100，`select` 第 3 轮 99.75，之后都按连续 discard 上限自动停（两个 subject 共 $7.64）。公开 / 隐藏差距能看见过拟合：`select` 第 1 轮专修公开集，差距 2.0，第 3 轮收到 0.25。
- (2026-10-08, 2.1.294, sonnet) **`compress` 31 轮一直有梯度**：105248 → #1 38694 → #8 28275 → #29 27869（4.04×），21 keep / 11 discard / 0 crash，没触发任何停止条件；discard 第 9 轮起出现、20 轮后成串，每次 keep 从几百字节缩到个位数。sonnet 中位 $0.28、108 秒/轮，合计 $11.76。
- (2026-10-08, 2.1.294) **opus 与 sonnet 一轮代价差一个数量级**：compress 第 1 轮 opus 18 turn、7 分钟、$3.20；sonnet 之后每轮 50–110 秒、$0.3，每轮仍是一个具体的技术。看循环本身的形态，弱一点的模型反而合适。

## 未验证

- MiniMax 等其它兼容端点：只试过 GLM；模型名处理是最可能不同的一处，先核它，stderr 第一行会说认不认。
- 长时间无人值守的限流：没碰到；碰到时 harness 非零退出、记 error，连续 `max_consecutive_errors` 次就停。
- `error_max_turns` / `error_max_budget_usd` 以外的 `is_error` 子类型：没见过；runner 一律记 error，reason 带原文。
