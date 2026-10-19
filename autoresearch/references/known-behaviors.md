# 已知行为——claude / codex / pi / goose / git

只收会改变会话做法的条目：选哪个 harness、上限和预算怎么定、怎么停、怎么介入。runner 自己处理的解析细节写在 `ar.py` 对应函数的注释里。每条标观察日期与版本，**当作可能有效的提示，不当保证**：不符就以眼前为准，再回来更新这份文件。

## harness

- (2026-10-19, claude 2.1.303 / codex-cli 0.162.1 / pi 1.3.0 / goose 1.55.0) **模型与凭据都在工具自己的配置里**，runner 一个都不传：codex 读它的 config，pi 读 `~/.pi/agent/`（`/login` 存 key，`settings.json` 定默认模型），goose 读 `~/.config/goose/config.yaml`（`goose configure`）。`harness.model` 只用来覆盖默认值。没配好时第一轮就以 error 结束，原因在 `harness.err` 或 reason 里。
- (2026-10-19, pi 1.3.0 / goose 1.55.0) **上限**：pi 没有轮数和费用上限，只能靠 `timeout_sec`；goose 有轮数上限（`max_turns`）、没有费用上限。配了工具做不到的上限，runner 拒绝启动。两者报的费用都是客户端按价格表的估算，不是账单。
- (2026-10-19, glm-5.3) **一轮更慢**：kata 的 `cases` 第 1 轮 pi 8.5 分钟 / $0.20、goose 8.8 分钟 / $0.24（2026-10-08 用 Claude Code 订阅跑 kata，16 轮中位约 25 秒）。kata 示例的 `timeout_sec` 是 900，换成 pi / goose 时先放宽。
- (2026-10-08, Claude Code 2.1.294) **`max_budget_usd` 不是硬上限**：第一次 API 调用之后才判定，设 0.01 的一轮实际记了 $0.76。
- (2026-10-10, codex-cli 0.162.1) **循环不能在 codex 的沙箱里启动**（codex 作为会话、用它的 shell 工具跑 `ar.py run`）：`.git` 和账本写不了，嵌套的 `codex exec` 也起不来，runner 直接拒绝。出路是在 codex 之外的终端启动，或 `codex --sandbox danger-full-access`。

## 循环

- (2026-10-08) **停循环用 SIGINT / SIGTERM**：`kill -9` 杀 runner，harness 在自己的进程组里会活下来，还留下过期的 `run.lock`（下次 run 自动替换）。
- (2026-10-08, git 2.54.0) **agent 新建、没 add 的文件也算这一轮的改动**，会被提交进这一轮；目标仓库要有 `.gitignore`。
- (2026-10-08) **一轮进行中手改打分器会被当作越界**：这轮 crash、整轮撤回，diff 在 `artifacts/<subject>/<checkpoint>/locked-changes.patch`，`git apply` 能恢复。
- (2026-10-08, Claude Code 2.1.294) **可枚举的合成任务，强模型一两轮就打满**（kata、retrieval），之后按连续 discard 上限自动停。公开集与隐藏集的分数差距能暴露过拟合。

## 未验证

- 长时间无人值守的限流：还没碰到过。碰到时 harness 非零退出、记 error，连续 `max_consecutive_errors` 次就停。
