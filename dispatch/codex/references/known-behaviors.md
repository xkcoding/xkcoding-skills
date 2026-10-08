# 已知行为——herdr / codex / openspec

这个 skill 靠三个外部 CLI 的行为立足，而它们都会随版本变。下面每条都标了发现日期与当时的版本。**当作可能有效的提示，而不是保证**：照它操作却失败了，就以眼前的 pane 为准处理，然后回来更新这份文件——只写验证过的事实，不写猜测。

## codex

- (2026-09-18, 0.154–0.155) `/goal <objective>` 的 objective 里带 `$openspec-apply-change <change>` 可以组合：codex 先读该 skill 的 `SKILL.md`（链接 worktree 里的 `.agents/skills/` 可被发现），再走官方 apply 流程，逐 task 勾选、逐 task commit，结束时自己把 goal 置为 `complete`。Codex 里调用 skill 的形式是 `$name`，不认 `/opsx:apply`。
- (2026-09-18, 0.155) `--approve-for-me`（别名 `--not-so-yolo`）与 `--sandbox`、`--dangerously-bypass-approvals-and-sandbox` 互斥；与 `--add-dir` 可组合。它自带 workspace-write 沙箱。
- (2026-09-18, 0.155) 自动审查放行了"写 worktree 之外的路径"和"`git push -u origin <feature 分支>`"，全程不弹给人。它的策略（源码 `codex-rs/prompts/templates/guardian/policy.md`）把"只影响一个用户自有 feature 分支"的 git 操作判为低 / 中风险；判高风险的是动默认或受保护分支、宽泛 refspec、删分支、绕过安全 hook、销毁未 push 的工作。
- (2026-09-18, 0.155) goal 里写明 "Never push, never merge, never open a pull request" 的 4 条 lane，均未 push。
- (2026-09-18, 0.154) 未受信任目录下默认只读沙箱；此时 `--add-dir` 报 `Ignoring --add-dir … because the effective permissions do not allow additional writable roots` 并立刻退出。所以严格姿态必须**显式**传 `--sandbox workspace-write`。
- (2026-09-18, 0.154) 启动期升级弹层：`Update available!`，默认高亮 `1. Update now (runs brew upgrade --cask codex)`，`2. Skip`，`3. Skip until next version`。发按键 `2` 即选中并确认。每逢新版本它都会回来。
- (2026-09-18, 0.154–0.155) 启动期 trust 弹层：`Do you trust the contents of this directory?`，注明 "Trusting will apply to the repository root"，默认 `1. Yes, continue`。接受后写入 `~/.codex/config.toml` 的 `[projects."<主仓库根>"] trust_level = "trusted"`。
- (2026-09-18, 0.155) lane 正在工作时再收到一条 `/goal …`：未见 `Replace goal?` 弹层，原 goal 照常完成。不要依赖这一点——`lane.py` 本来就不会在 lane 工作时发送。
- (2026-09-18, 0.154–0.155) goal 的权威状态在 `~/.codex/goals_1.sqlite` 的 `thread_goals` 表（`thread_id` = herdr 报告的 session id；`status` ∈ `active` / `paused` / `blocked` / `usage_limited` / `budget_limited` / `complete`）。`~/.codex/sqlite/goals_1.sqlite` 也存在但是空的。
- (2026-09-18, 0.155) 3 条 lane 并行、各 3 个小 task：每条约 2.7–3.1 万 token、52–78 秒。

## herdr

- (2026-09-18, 0.9.0) 同一仓库第一次 `herdr worktree create` 新增 2 个 workspace（多出来的对应主仓库本身），之后每次只新增 1 个。
- (2026-09-18, 0.9.0) `herdr worktree list --cwd <repo>` 给出每个 worktree 的 `open_workspace_id`；`herdr pane list --workspace <ws>` 给出 pane 及其 `cwd`；`herdr agent list` 只列有 agent 的 pane，每项带 `cwd` / `foreground_cwd` / `workspace_id` / `agent_session`。lane → workspace → pane → agent 全部可以现查。
- (2026-09-18, 0.9.0) `herdr agent read` / `herdr pane read` 返回纯文本，不是 JSON；必须带 `--source visible`。回滚只留很短一段（实测约 80 行），更早的输出要从 codex 的 rollout 文件取。
- (2026-09-18, 0.9.0) `herdr agent start` 在 agent 进程启动即退出时返回 `timeout`；启动期有弹层时返回 `agent_not_ready`，此时名字已可寻址。
- (2026-09-18, 0.9.0) `agent_session.value` 在首个 turn 结束之前为 null。
- (2026-09-18, 0.9.0) `herdr agent prompt … --wait` 被中断时，prompt 已经送达。
- (2026-09-18, 0.9.0) `herdr agent wait <name> --until <status> --timeout <ms>` 可用来等状态变化，不必 sleep。
- (2026-09-18, 0.9.0) `herdr worktree remove --workspace <ws>` 杀掉其中的 agent 并删除 checkout，分支与 commit 保留；主仓库那个 workspace 用 `herdr workspace close <ws>`。

## 评审请求的 CLI

- (2026-09-18, gh 2.96.0) `gh pr create` 缺任何一个参数都会进入交互式提问，在非交互的调用里就是挂死；所以 `--repo` / `--base` / `--head` / `--title` / `--body-file` 全部显式给出。`gh pr list --head <branch> --state all --json number,url,state,isDraft` 用来复用已有的 PR。
- (2026-09-24, glab 1.113.0，**已对真实的自建 GitLab 验证**：19 条 lane 各开出一个 MR) `glab mr create -R <repo 或 git URL> -s <source> -b <target> -t <title> -d <description> --draft --yes --no-editor`；`glab mr list -R … -s <branch> -A -F json`；`glab auth status --hostname <host>`。`-R` 接受完整的 git URL，所以不必另行解析项目路径。MR 的 JSON 字段按 GitLab API 取 `iid` / `web_url` / `state` / `draft`。
- (2026-09-18) 某内部平台的 MR skill（`yunxiao-mr-review`）创建 MR 的入参是 `--target <branch>` / `--source <branch>` / `--title`，与 `publish` 交出的 `handoff` 字段一一对应。

## 生产使用（2026-09-21 → 09-24）

一次真实的连续使用，不是临时试验：某内部仓库、自建 GitLab（host 名里没有 `gitlab` 字样）、19 条 lane 分 12 批跑完 4 天，全部 `--approve-for-me` 姿态、全部 goal 模式。下面都是那次留下的事实。

- **全部 19 条都走到了发布**：19 个 `pushed_sha`、19 个真实 MR，`publish` 重试 0 次、`last_publish_error` 0 条。
- **续跑路径几乎不触发**：19 条 lane 的 nudge 总数为 **0**。goal 模式 + 自动审查下，lane 基本能自己从头跑到尾；`idle_unfinished` 是修复路径，不是引擎。
- **认不出的 host 只问一次**：`code.devops.xiaohongshu.com` 猜不出来 → 问了一次 → 记为 `glab` → 之后 19 条 lane 再没问过。按 host 记住这个决定是对的。
- **base 可以是非默认分支**：19 条全部以一个 feature 分支为 base，MR 也开在它上面。base 只需在 origin 上存在。
- **一条 lane 可以跑很久**：最长的一条从下达 goal 到被上报间隔 3 小时 17 分，期间没有撞上 context 占满或限流。
- **agent 名截断对着真实 herdr 验证过**：3 个超过 32 字符的 change 名（36 / 36 / 38）按整词从尾部丢弃，落到 27 / 29 / 31 字符，都仍以字母开头、无尾部连字符；正好 32 字符的那个原样保留。herdr 全部接受。
- **`goal_blocked` 真实发生过一次，设计里的人工分支成立**：一条 lane 的 codex 自判 goal blocked，原因是外部依赖失败（CDP 读网络报 `Browser is not available: 1`）。巡检按"`goal_blocked` → 上报，不自行恢复"把原因交给人；人处理之后这条 lane 继续跑完，通过验收并开出 MR。**结论**：模型自判的 blocked 通常是真的外部障碍，不要让巡检去 resume 它。
- **一批同时跑 1–4 条**。更高的并发没试过。

## openspec

- (2026-09-18, 1.13.1) `openspec instructions apply --change <c> --json` 返回 `state`（`blocked` / `ready` / `all_done`）、`progress{total,complete,remaining}`、`tasks[]`、`missingArtifacts`；在 lane worktree 里执行时只看得到该 lane 自己的 change。
- (2026-09-18, 1.13.1) `openspec init --tools codex` 只往仓库写 `.agents/skills/openspec-*`，不碰 home 目录。
- (2026-09-18, 1.13.1) change 目录里 OpenSpec 不认识的文件（`verify.md`）是惰性的：`status` 不受影响，`validate --strict` 通过，`archive` 会把它一并归档。
- (2026-09-18, 1.13.1) 官方 apply skill 写明 "Pause if: Task is unclear → ask for clarification"、"Error or blocker encountered → report and wait for guidance"——无人值守的 lane 会因此合理地停住，所以续跑之前要先看它是不是在提问。

## 没验证过的说法

遇到时小心处理，验证之后挪到上面。每条都注明了为什么那次生产使用没能覆盖它。

- 自动审查**拒绝**一个请求时，是把拒绝回给模型，还是弹给人让 lane 进入 `blocked`。（那次唯一的一条 blocked 是外部工具失败，不是审查拒绝，所以仍未覆盖。两种都按巡检表处理即可。）
- `--strict` 下审批弹层的具体样子与按键。（19 条 lane 全是默认姿态。本 skill 不代答审批，只需要认出"有弹层"并把原文上报。）
- 向已有 goal 的空闲 lane 再发 `/goal <objective>` 会弹出默认项为 Replace 的列表（来自 herdr-dispatch 的文档）。（`lane.py` 本来就不会重发，所以触发不到；万一见到，选"保留现有 goal"的那一项。）
- `/goal resume` 即时生效且无弹层（同上来源）。（那次没遇到限流，被上报的那条是人工处理的，没走 resume。）
- 长任务下的 context 占满、compaction、账号限流的实际表现。（最长的一条跑了 3 小时 17 分也没撞上。）
- 把一条**未完成**的 lane 半路接手——进它的 worktree 直接 `/opsx:apply` 接着做。（那次 19 条都跑到了发布，没有半路接手的场景。分支和 `tasks.md` 都是普通 git 产物，这条路径在设计上成立，但没实际走过。）
