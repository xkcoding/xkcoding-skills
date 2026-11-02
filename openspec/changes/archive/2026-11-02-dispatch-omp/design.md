# Design

## Context

动机见 proposal.md「Why」，要求见各 spec。这里只记影响做法的现状与约束。

**现状**（`dispatch-pi` 合并后）：`dispatch/codex/scripts/lane.py` 的 `EXECUTORS` 有 `codex`、`pi` 两行；pi 行用到 `pi_goal_probe`、`pi_pane_state` / `pi_layout` / `pi_input_box`、`pi_startup_problem`、`pi_launch_flags`、`pi_label`、`PI_GOAL_EXTENSION`，以及与执行者无关、只是名字带 `pi_` 的沙箱策略部分（`pi_policy`、`pi_cache_dirs`、`pnpm_store`、`registry_hosts`、`PI_GUARD_DIR`、`PI_PUBLIC_REGISTRIES`、`PI_CACHE_DIRS`）。`doctor.sh --executor pi`。`dispatch/sync-engine.sh` 的目标是 `dispatch/pi/scripts`。lane-guard 在 `dispatch/pi/scripts/lane-guard/`。

**约束**：skill 目录自包含；codex 行为逐字节不变；不写用户的工具配置；没有 yolo（沙箱与守卫是边界，见 D4）。

### 已实测的事实（2026-11-02，omp 18.15.0，herdr 0.9.0 + omp 集成 v9，glm-5.3，macOS）

| # | 事实 |
|---|---|
| O1 | `herdr agent start --kind omp --pane <p> -- --tools read,bash,edit,write,goal --no-pty --no-lsp -e <lane-guard> --lane-policy <file> --goal "<goal 文本>"`：omp 画出界面即开工，不需要再发 prompt；没有项目信任框 |
| O2 | herdr 立即报 session（`kind:"path"`，`~/.omp/agent/sessions/<cwd 编码>/<时间>_<id>.jsonl`）；结束后 agent 状态是 `idle`（pi 是 `done`）；herdr 先于 TUI 报就绪 |
| O3 | 2 task change：76 秒、约 1.36 万 token；每 task 一个 commit 且含 `tasks.md` 勾选；`openspec instructions apply` 得 `all_done` |
| O4 | omp 读 skill 走 `read skill://openspec-apply-change`；`openspec init --tools oh-my-pi` 写 `.omp/skills/` 与 `.omp/commands/`；omp 发现 `.omp/skills`、`.agents/skills`、`.claude/skills` |
| O5 | goal 状态：`type:"mode_change"` 行的 `data.goal`（`id`、`objective`、`status`、`tokensUsed`、`timeUsedSeconds`…），`status` 取值 `active` / `paused` / `complete` / `budget-limited` / `dropped`；完成时另有 `type:"custom"`、`customType:"goal-completed"`；完成后还会有 `data.goal` 为 null 的 `mode_change` |
| O6 | lane-guard 经 omp 的 pi 兼容垫片加载：注册的 `bash` 替换原生 bash（越界写 `Operation not permitted`），`tool_call` 守卫对 `write` / `read` 生效，`user_bash` 事件存在 |
| O7 | 不传 `--tools` 时模型可用 `read, bash, edit, eval, glob, grep, task, wait, todo, web_search, write` 及 `xd://ast_edit`、`xd://debug`；传 `--tools read,bash,edit,write`（+`goal`）时只剩这几个 |
| O8 | omp 的 `read` 支持 `http(s)://`、`www.` 与内部 URI（`agent artifact attachment cfg conflict history issue local mcp memory mr omp out pr proc rule security skill ssh vault xd`）；`read https://example.com` 在沙箱外取回网页，同一 lane 里 bash 的 `curl` 被沙箱拒（403） |
| O9 | 4 个 omp 同时启动、同时请求模型：全部正常；凭据在 `~/.omp/agent/agent.db`（SQLite），未见 pi 的配置锁问题 |
| O10 | print 模式下 stdin 不是终端时 omp 卡在 `readPipedInput`，需 `< /dev/null`（仅影响探针，lane 是交互模式） |
| O11 | 用户配置：`modelRoles.default = zhipu-coding-plan/glm-5.3`；`tools.approvalMode` 默认值是 `yolo`（源码 `tools/settings.ts`）；`omp models --json` 返回 `{"models": [...]}`，即已登录 provider 下可用的模型 |
| O13 | （2026-11-02，实跑）刚建好的 pane 里立即 `herdr agent start` 一千多字符的 omp 命令，一次出现命令结尾丢字（`…git status is clea`）、引号未闭合、omp 没起来；pane 前台曾见到提示符钩子调用的 `gh`。偶发，未能稳定复现 |
| O14 | （同上）`herdr agent start` 要等 agent 就绪才返回；omp 带 `--goal` 一启动就进入工作，herdr 有时 4 秒就返回，有时一直等到 goal 那一轮结束（实测一条 2 task lane 在 launch 返回时已经 `claims_done`），上限是 `--timeout` |
| O15 | （2026-11-02，实跑）带 `--tools` 白名单时 omp 仍会在启动时于沙箱外拉起配置里的 MCP server（实测 worktree 里 `.omp/mcp.json` 声明的 context7 被 omp 进程拉起）；MCP 工具不作为独立工具出现，而是 `xd://mcp__<server>_<tool>` 设备，经 `write` 调用——lane-guard 拒绝任何 `协议://` 写入，实测拦下。用户决定不再追加关闭 MCP 的手段：MCP 不可调用即可，server 在沙箱外启动这一点写进文档 |
| O12 | 界面：工作中有一行 `Working…`，底栏带转圈符与秒数（`⠧ 4s · GLM-5.3 · Goal 0 · <dir> · <branch> · 0.6%/1M`）；空闲时输入框是两条 `───` 之间的 `❯`，底栏首段换成静态图标；上边框可能带标题（`─── 󰗇 GREET: … ─`）；扩展状态行（`🔒 lane-guard: …`）在最后 |

未实测：omp 的选择框 / 确认框长什么样（`--strict` 的 lane-guard 询问）、退出后的 pane、`paused` / `budget-limited` / `dropped` 的真实出现、Linux。

## Goals / Non-Goals

**Goals**
- `/dispatch:omp` 走与 codex 相同的派发 / 巡检 / 验收 / 发布流程；codex 行为不变。
- 把 omp 在本地实测到的绕过路径（工具面、`read` 的 URL / URI）全部关上。

**Non-Goals**
- 不保留 pi 的任何执行路径（用户决定彻底删除）；不做 pi lane 的迁移工具。
- 不利用 omp 的子代理、记忆、浏览器等能力。
- 不接 omp 的 `--max-cost` / `--max-time`（可做，但没有被要求；见 Open Questions）。

## Decisions

### D1：引擎里 pi 行换成 omp 行；与执行者无关的沙箱部分去掉 `pi_` 前缀

`EXECUTORS` 只剩 `codex` 与 `omp`。沙箱策略相关的函数和常量本来就与执行者无关，改名为 `guard_policy`、`guard_cache_dirs`、`GUARD_DIR`、`PUBLIC_REGISTRIES` 等，供 omp 行使用。删掉所有 pi 专属函数与 `PI_GOAL_EXTENSION`。`sync-engine.sh` 的目标改为 `dispatch/omp/scripts`；`dispatch/pi/` 整个删除，lane-guard 移到 `dispatch/omp/scripts/lane-guard/`（`git mv`，保留历史）。

已有 pi lane：herdr 报的 agent 是 `pi`、或记录里 `executor: pi` → `lane_executor` 返回 None → `unknown_executor`（现有逻辑即如此，spec 已写明）。

### D2：omp 的启动参数与 goal 下达

```
herdr agent start <name> --kind omp --pane <p> -- \
  --tools read,bash,edit,write,goal --no-pty --no-lsp --approval-mode yolo \
  -e <skill>/scripts/lane-guard --lane-policy <policy> \
  --goal "<GOAL_TEXT>"
```

- goal 在启动时下达（O1）。`launch` 因此需要 change 名来生成 goal 文本：执行者行的 `launch_flags` 增加参数，并新增 `goal_at_launch: True`。`launch` 成功时记 `goal_sent_at` / `goal_mode: "goal"`；`prompt --goal` / `--plain` 对这类 lane 一律以"已下达"拒绝（spec "Goal requested again"）。
- `--approval-mode yolo`：omp 的审批层只决定"调用工具前问不问人"，用户若把全局默认改成会问的模式，无人值守的 lane 会卡在每条 bash 上（O11）。lane 的边界是沙箱 + 守卫 + 工具白名单，而不是 omp 的审批；`--strict` 的人工确认由 lane-guard 发起。确认页与文档如实写明。
- 不传 `--model`：用 omp 的默认模型（spec 要求），doctor 校验存在且可用；`launch` 时读出写进 bookkeeping，供 `verify.md` 写"用的模型"。
- 不传 MCP 相关参数：MCP 工具只能经 `write xd://mcp__…` 调用，守卫一律拒绝（O15）。omp 仍会在沙箱外启动配置里的 MCP server（含仓库自带的 `.omp/mcp.json`）——用户接受，文档如实写明。

### D3：lane-guard 对 `read` 收窄到普通路径与 `skill://`

`tool_call` 里 `read` 的 `path`：
- 匹配 `^[A-Za-z][A-Za-z0-9+.-]*://` → 取协议名，只放行 `skill`，其余（含 `http`、`https`、`file`、O8 列出的全部内部协议）block 并给出原因；
- 以 `www.` 开头 → block（omp 把它当网址读，O8）；
- 其余按现有逻辑（`~` 展开、软链解析、`denyRead` 及其祖先）。

这条对 codex 无关（codex 不加载 lane-guard）。`grep` / `find` / `ls` 不在白名单里，现有守卫逻辑保留无害。

### D4：omp 的 goal 探针

读 herdr 报的 session 路径（O2），逐行解析：`type == "mode_change"` 且 `data.goal` 是对象 → 记下它的 `status` / `tokensUsed` / `timeUsedSeconds`；`type == "custom"` 且 `customType == "goal-completed"` → 状态记为 `complete`。取最后一次记下的值（O5 的 null 行被跳过）。连字符写法规范为下划线（`budget-limited` → `budget_limited`）。`dropped` 视同需要上报：巡检表新增 `goal_dropped`，与 `goal_paused` / `goal_budget_limited` 一样上报、不恢复。omp 没有 `usage_limited` / `blocked`，对应路径不会触发。

### D5：omp 的界面识别、空闲与提交确认

- `pane_state`：最近几行有 `Working…` 或底栏首段是转圈符 → `working`；两条 `───`（上边框可带标题）之间是 `❯` 且其后无文字 → `ready`；`❯` 后有文字 → `typed`；`↑↓` / `enter select` / `(y/n)` 类选择提示 → `dialog`；其余 `unknown`。退出后的样子与选择框样子未实测，任务里先抓真实 pane 再定稿，样例覆盖 O12 的各态。
- herdr 的 `idle` 与 `done` 都视为不在工作（O2）。
- `confirm_submit`：沿用 pi 时代的逻辑（只在输入框里正是刚发的文字时补一次回车，选择框永不按键），仅用于 `--continue` / `--correct` 这类后续 prompt；输入框解析按 omp 的 `❯` 行实现。
- `session_proves_primed: False`（O2：session 先于任何 turn 出现），但 omp 的 goal 在 launch 时已下达，"已下达"的证据就是 launch 记下的 `goal_sent_at`。
- `launch_gap: 0`、无 `startup_problem`（O9）；`launch` 的 90 秒等界面逻辑保留（O2）。
- 启动的送达（O13，对所有执行者）：`herdr agent start` 之前等 pane 的前台只剩 shell、连续两次读到相同（最多 20 秒）；启动后若 lane 里没有 agent、前台仍是 shell，判定命令没送达——发 ctrl+c 清掉输入，再启动一次，结果带 `start_retried: "start_not_delivered"`。已经起来又退出的 agent 不重试。
- `goal_at_launch` 的执行者在 launch 返回时可能已经在工作（O14），`working` 也算启动成功。

### D6：doctor 与 setup

`doctor.sh --executor omp`（取代 `--executor pi`）：`omp --version`、`rg --version`、`npm --version`、skill 目录内 sandbox-runtime 版本、`omp config get modelRoles`（默认模型）、`omp models --json` 里是否含该默认模型（不输出凭据）、`herdr integration status` 里 omp 是否 `current`、目标仓库是否提交了 `.omp/skills`、`.agents/skills` 或 `.claude/skills` 下的 `openspec-apply-change/SKILL.md`、平台（Linux 另需 bwrap / socat）。不再检测 pi、Node ≥ 24。

### D7：文案与版本

确认页的姿态句、`verify.md` 的 `executor:`（`omp <版本>`，另起一行 `model: <默认模型>`）、评审出处、"共享限流"提醒（omp：同一 provider 凭据）从执行者行取。`dispatch/codex` 升到 0.3.0，`dispatch/omp` 从 0.1.0 开始；CHANGELOG 标 **BREAKING**。`dispatch-executors` 主 spec 的 Purpose 写的是"codex or pi"，按 OpenSpec 规则需在主 spec 里直接改，列为任务。

## Risks / Trade-offs

- [omp 版本迭代快（18.x），兼容垫片、工具名、URI 协议、session 格式都可能变] → 版本写进 doctor 的 `verified_against`，known-behaviors 每条带版本；doctor 发现版本不同报告一行。lane-guard 对 `read` 采用"只放行普通路径与 `skill://`"的白名单写法，新增协议默认被拦。
- [`--approval-mode yolo` 这个词读起来像放开了边界] → 文档说明它只关掉 omp 自己的问人环节，边界由沙箱、守卫、工具白名单给出；`--strict` 的问人由 lane-guard 发起。
- [彻底删除 pi，进行中的 pi lane 失去巡检] → 用户已知情（本机 1 条）；升级插件前收尾，或升级后按 `unknown_executor` 手动处理。CHANGELOG 与 README 写明。
- [omp 的选择框 / 退出样式未实测，`--strict` 下可能识别为 `unknown`] → `unknown` 不发任何输入；任务里实测补规则。
- [lane 能写共享包缓存，可被植入代码] → 沿用 dispatch-pi 时用户的选择，文档已写明，不在本 change 改变。

## Migration Plan

- 合并前：用户把进行中的 pi lane 收尾（或接受它在新版里变成 `unknown_executor`）。
- 合并后：`claude plugin marketplace update xkcoding-skills` → `claude plugin update dispatch@xkcoding-skills` → 新会话 → `/dispatch:omp setup`（`npm ci` 装 lane-guard 依赖）。
- 回滚：revert 合并提交即恢复 `/dispatch:pi`；omp lane 在旧版里显示为 `unknown_executor`。

## Open Questions

- 是否给 omp lane 加 `--max-cost` / `--max-time` 默认值：不影响本方案的结构，可在用上一段时间后按真实花费再定。
