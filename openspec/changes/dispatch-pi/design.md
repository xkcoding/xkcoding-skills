# Design

## Context

动机见 proposal.md「Why」，要求见各 spec。这里只记影响做法的现状与约束。

**现状**：`dispatch/codex/scripts/lane.py`（约 1000 行）里与执行者相关的只有几处：`cmd_launch` 的 `--kind codex` 与 codex 参数、`GOAL_TEXT` / `CONTINUE_TEXT` 里的 `$openspec-apply-change`、`goal_probe()` 读 codex 的 sqlite、`pane_state()` 匹配 codex 的界面、`cmd_prompt` 里"有 session 即已下达 goal"的判断、`cmd_record_verify` / `cmd_publish` 里写死的 "codex"。worktree、分支、bookkeeping、验收、发布、forge 都与执行者无关。`doctor.sh` 同理：只有 codex 的版本、登录、`.agents/skills` 检查是执行者相关的。

**约束**：skill 目录自包含（skill-craft 原则，`check.py` 会把跨目录引用报为错误）；目标仓库零安装物；不写用户的工具配置；没有 yolo。

### 已实测的事实（2026-10-29）

herdr 0.9.0、pi 1.3.0（goal 轮）/ 1.4.0（沙箱与守卫轮）、pi-codex-goal 0.6.1、@anthropic-ai/sandbox-runtime 0.0.26、openspec 1.12.0、模型 glm-5.3。均在 `/tmp` 一次性仓库 + herdr worktree 里跑过。

| # | 事实 |
|---|---|
| P1 | `herdr agent start --kind pi --pane <p> -- -e npm:pi-codex-goal@0.6.1 --approve --tui-mode regular` 一次就绪；扩展被装进 pi 自己的临时目录（`~/.pi/agent/tmp/extensions/npm/<hash>`），不改 `settings.json` |
| P2 | `--approve` 后无信任弹窗，`.pi/skills/` 下的 `openspec-apply-change` 被发现；pi 也发现 `.agents/skills/` |
| P3 | `/goal <objective>` 直接 "Goal set."，无确认弹窗。objective 写"使用 openspec-apply-change skill（先读它的 SKILL.md）"即可，模型照做 |
| P4 | 2 task 的 change：读 SKILL.md → `openspec instructions apply` → 每 task 勾选 + 显式 `git add` + 单独 commit → `update_goal complete`；130 秒、18.6k token、约 $0.10 |
| P5 | goal 状态在 session JSONL：`type:"custom"`、`customType:"pi-codex-goal"`；过程中 `kind:"usage"`、`status:"active"`，结束 `kind:"set"`、`status:"complete"` |
| P6 | herdr 在首个 turn 结束**之前**就报告 pi 的 session（`kind:"path"`，值为 JSONL 路径）；codex 要到首个 turn 结束 |
| P7 | 界面：工作中有 `── ⠙ Working ──` 行；空闲时两条 `───` 之间的输入框为空；底栏 goal 行 `Pursuing goal` / `Goal achieved (2m)`；退出后打印 `To resume this session: pi --session …`；升级后首启打印整段 changelog，有新版本时有 "Update Available" 横幅，均不阻塞 |
| P8 | 一轮普通对话结束后 herdr 报 `done` 而非 `idle` |
| P9 | `agent start` 后立即 `agent prompt`：文字留在输入框未提交，补一次 `send-keys enter` 即开始工作 |
| P10 | sandbox-runtime（allowWrite = worktree + 主仓库 `.git`，denyWrite = `.git/hooks`、`.git/config`）：worktree 内 `git commit` 成功；写主 checkout、home、`.git/hooks`、`git config` 写入、读 `~/.ssh` 全部 `Operation not permitted`；网络白名单内 200，其余 403 |
| P11 | pi 官方 sandbox 示例只替换 `bash` 工具：经 pi 的 bash 越界写被拒，`write` 工具越界写**成功** |
| P12 | `tool_call` 守卫（`pi.registerFlag` 传可写根，符号链接先解析）：worktree 内相对路径、`/tmp` 别名路径放行；越界 `write` / `edit` 被 block，模型收到原因且未绕 |
| P13 | 官方 sandbox 示例的配置合并按键浅合并：给出 `filesystem` 即整体替换默认值（默认里有 `/tmp`） |
| P14 | （源码，pi 1.4.0）`dist/core/auth-storage.js`、`settings-manager.js`、`trust-manager.js` 对 `auth.json` / `settings.json` / `trust.json` 的同步锁都是 proper-lockfile `lockSync`，重试 10 次 × 20ms，约 200ms 拿不到就抛 `ELOCKED`；`auth-storage` 的异步路径另有 30 秒的等待上限 |
| P15 | （另一会话的实地反馈，2026-10-29）同一时间启动多个 pi，部分进程抢不到全局配置锁、读不到 API key 就退出；启动之间隔 4 秒、只重跑失败的那些即可恢复 |
| P16 | （2026-11-02，pi 1.4.0，临时 `PI_CODING_AGENT_DIR`、空 `auth.json`）print 模式读不到 key 时打印 `No API key found for the selected model.` 并退出 1；**交互模式不退出**：界面照常就绪，底栏统计行为 `0.0%/0 (auto)`、模型位显示 `unknown`，发 prompt 后输出 `Error: No API key found for the selected model.`，lane 回到空闲 |
| P18 | （2026-11-02，sandbox-runtime 0.0.26）可写范围只有工作目录时，沙箱里的 `npm install` 失败：npm 要写 `~/.npm` 缓存（报 `sudo chown -R … ~/.npm`），依赖装不上 |
| P17 | （同上）pi 的项目信任弹层：分隔线之间是 `Trust project folder?`、路径、说明，选项行以 `→ ` 标出高亮项（`Trust` / `Trust parent folder (…)` / `Trust (this session only)` / `Do not trust` / `Do not trust (this session only)`），末行 `↑↓ navigate  enter select  escape/ctrl+c cancel` |

## Goals / Non-Goals

**Goals**
- codex lane 的行为与今天逐条一致；pi 只是第二行适配。
- 一个仓库里两种 lane 混跑时，任一入口的巡检都判断正确。

**Non-Goals**
- 不做第三个执行者的抽象层（适配表够用；第三个来了再看）。
- 不给 pi 加审查模型（codex `--approve-for-me` 的对应物）。
- 不支持 Windows（sandbox-runtime 不支持）。
- 不做"同一 change 换执行者重新派发"的迁移命令：用户可手动清掉旧 lane 再派。

## Decisions

### D1：一份引擎，两份逐字节相同的副本

`lane.py` 与 `doctor.sh` 改成执行者无关，执行者相关的部分收进一张表（`EXECUTORS = {"codex": {...}, "pi": {...}}`：launch 参数构造、skill 调用写法、goal / continue / resume 文本、goal 探针、`pane_state` 规则、"已下达 goal"的证据、版本命令、verify / 评审文案）。`dispatch/codex/scripts/` 与 `dispatch/pi/scripts/` 各放一份**完全相同**的文件；`dispatch/sync-engine.sh` 以 codex 那份为源复制，`--check` 模式比对并在不同时以非零退出、列出文件。

- 为什么不各写各的：两种 lane 共用 `<repo>.lanes/` 与 `change/` 前缀，`find_lanes()` 会看到对方的 lane；各自一套规则就会拿 codex 的 sqlite 与界面规则去判 pi 的 lane。
- 为什么不放插件根目录共享：skill 目录自包含是本仓库的硬原则，`${CLAUDE_SKILL_DIR}` 之外的路径不保证存在。
- 为什么 codex 那份是源：它有生产使用记录；pi 的副本只是镜像。
- 代价：仓库里多 ~1000 行重复；靠 `sync-engine.sh --check` 与 CLAUDE.md 的开发规范兜住。

### D2：执行者是 lane 的属性，按"herdr → bookkeeping → 未知"推出

`create` / `launch` 带 `--executor`（由各自的 SKILL.md 传入，不靠脚本猜自己在哪个目录），launch 时写进 bookkeeping。巡检时先看 herdr 报的 agent 类型（`agent` 字段：`codex` / `pi`），没有 agent 再看 bookkeeping，都没有记为 `unknown` 且不操纵。旧 bookkeeping 无该字段 + herdr 报 codex → codex，零迁移。

`plan` 发现目标 change 已有 lane 时，返回那条 lane 的执行者，供确认页说明。

### D3：pi lane 的启动参数

```
herdr agent start <name> --kind pi --pane <p> -- \
  -e <skill>/scripts/lane-guard \
  -e npm:pi-codex-goal@0.6.1 \
  --approve --no-mcp --tui-mode regular \
  --lane-policy ~/.claude/dispatch/<repo-id>/<change>-policy.json
```

- `--approve`：本次运行信任项目资源（P2），不写 `trust.json`。
- `--no-mcp`：MCP 工具跑在沙箱外。不用 `--no-extensions`，否则 herdr 的 pi 状态集成也会被关掉。
- `--tui-mode regular`：让回滚区保留输出，便于读 pane（类似 codex 的 `--no-alt-screen`）。
- 版本号钉死在适配表里；升级是一次显式改动，需重跑实测并更新 known-behaviors。

### D4：一个 lane-guard 扩展管 bash 与文件工具，策略来自 lane 之外的文件

`dispatch/pi/scripts/lane-guard/`（`index.ts` + 钉死 `@anthropic-ai/sandbox-runtime` 的 `package.json`）。以官方 sandbox 示例为起点，但：

- 策略只从 `--lane-policy <file>` 读，不读 `<cwd>/.pi/sandbox.json` 或全局 `sandbox.json`（P13 的合并规则会让仓库里的文件改写策略）。策略文件由 `lane.py launch` 生成在 `~/.claude/dispatch/<repo-id>/`，内容：`allowWrite`（worktree、`git rev-parse --git-common-dir`、包管理器缓存 `~/.npm`、`~/.cache`、macOS 的 `~/Library/Caches`——P18，用户选择放行真实缓存而不是给每条 lane 私有缓存）、`denyWrite`（common dir 下的 `hooks`、`config`）、`denyRead`（`~/.ssh`、`~/.aws`、`~/.gnupg`）、`allowedDomains`、`posture`。
- **fail closed**：策略文件缺失、解析失败或 sandbox 初始化失败时，替换后的 `bash` 与 `user_bash` 直接返回错误，不回落到本地 bash（官方示例在初始化失败时会回落）。
- `tool_call` 拦 `write` / `edit`（P12 的做法），可写根与沙箱同源；`denyWrite` 同样生效（否则 `edit` 能改 `.git/config`）。默认姿态 `block` + 原因；`--strict` 用 `ctx.ui.confirm` 弹给人。
- 网络白名单：官方示例的默认公共源（npm、yarn、pypi、github）加 `files.pythonhosted.org`，再加从用户配置读出的包源 host（`npm config get registry`、`pip config get global.index-url`，取得到才加）。本机 npm 源就是 npmmirror，只用公共列表会让 lane 装不了依赖。

替代方案：
- 用社区包（pi-better-sandbox、@erichll/pi-sandbox、@buyong/pi-codex-auto-review）：前者只能经 TUI 开启且对 `.git` 的放行粒度过粗；中者只管 bash 且要求 pi ≥ 1.4.0 加 pi-subagents；后者明说不是 OS 沙箱、上线三周。安全边界不交给这些包。
- 整个 pi 进程包进 `sandbox-exec`：`--kind pi` 启动的是 pi 本体，无处套壳；herdr 的状态 socket 也会被隔离。

### D5：pi 的 goal、续跑与状态

- goal 文本与 codex 同一组边界，skill 写成自然语言"use the openspec-apply-change skill (read its SKILL.md first)"（P3）；continue 文本同理。
- `goal_probe` 的 pi 版：读 herdr 报的 session 路径（P6），倒序找最后一条 `customType == "pi-codex-goal"` 且带 `status` 的记录；`budget-limited` 等连字符写法规范成下划线，与现有 verdict 名对齐。实测只见过 `active` / `complete`；`paused` / `blocked` / `waiting` / `budget_limited` 按 README 映射，验证前在 known-behaviors 里标为未验证。
- pi-codex-goal 会自己对 provider 限流排队重试，所以 pi 不会出现 `goal_usage_limited`；`--resume` 对 pi 发 `/goal resume`，只在人工明确要求时用。
- "已下达 goal"的证据：codex 继续用 session / goal 记录；pi 不能用 session（P6），改用 bookkeeping 的 `goal_sent_at`、session 文件里存在 `pi-codex-goal` 记录、或 lane 已有超过 propose 的 commit。
- 空闲判断：herdr 的 `done` 与 `idle` 都算不在工作（P8）；仍以 `pane_state` 为准。

### D6：pi 的 pane 识别与提交确认

`pane_state` 的 pi 规则（P7）：最近几行出现 `Working` 分隔行 → `working`；出现 `To resume this session` 或 shell 提示符且无 pi 底栏 → `exited`；两条 `───` 之间为空且有底栏 → `ready`；选择列表 / 确认框（`ctx.ui.confirm` 的样子尚未实测）→ `dialog`，未认出的一律 `unknown`，保守不发。

提交确认（P9）：`prompt` 发出后等最多约 15 秒看 lane 是否进入 `working`；仍 `ready` 且输入框里是刚发的文字 → `send-keys enter` 一次；再不动 → 返回 `ok:false` 与 pane 尾部，交给调度者。启动后先等 `pane_state == ready` 再发 goal。这一段对 codex 不启用（没观察到）。

### D7：doctor 与 setup

`doctor.sh --executor codex|pi`。共有：openspec、herdr、git、jq、python3、gh、glab、herdr pane、主 checkout、`openspec/`。pi 专有：`pi --version`、`node --version`（≥ 24）、`rg --version`、`<skill>/scripts/lane-guard/node_modules/@anthropic-ai/sandbox-runtime` 存在且版本匹配、`pi auth check --model <settings.json 的默认模型> --json --no-refresh`（不带 `--credentials`，不输出凭据）、平台（Linux 还要 `bwrap`、`socat`）、目标仓库已提交 `.pi/skills/openspec-apply-change/SKILL.md` 或 `.agents/skills/openspec-apply-change/SKILL.md`。`setup` 只为 sandbox 依赖多一个"征得同意后在 skill 目录 `npm install`"的步骤。

### D8：文案

确认页的姿态句、`verify.md` 的 `executor:` 行（pi 写 `pi <版本> + pi-codex-goal <版本>`）、评审请求出处行、"共享限流"提醒（pi：同一 provider 凭据）都从适配表取。

### D9：pi lane 逐个启动、逐个下达 goal，锁冲突只重启一次

P14 / P15 说明多个 pi 同时启动会在 pi 自己的配置锁上互相挤掉。做法：

- 派发流程里 pi lane 的 `launch` 串行，前一条到 `ready` 后再等 `launch_gap`（适配表里，初值 4 秒，取自 P15 的实地经验）才启动下一条；"全部启动完再下达 goal"保留，但 pi 的各条 goal 之间同样隔 `launch_gap`，避免首次请求模型时一起读 `auth.json`。codex 的 `launch_gap` 为 0，行为不变。
- 锁冲突在 lane 里**不表现为退出**（P16）：交互模式的 pi 带着 `unknown` 模型照常就绪，要到发 goal 时才报 `No API key found`。所以 pi 适配行在 `launch` 拿到 `ready` 后再检查"有没有模型"：底栏模型位是 `unknown`、或 pane 里出现 `No API key found` → 发 `/quit`，等回到 shell，隔 `launch_gap` 重启一次，结果带 `retried: "no_model"`；重启后仍无模型 → 记为启动失败、不再重试，goal 一条都不发。真缺凭据的情况 doctor 已先拦下（`pi_model_ready`），万一漏过也只是多一次重启。
- 间隔只能管住本次派发；同一时刻用户在别处启动的 pi（如另一会话的评测）仍可能撞锁，靠上面这一次重试兜住。

替代方案：给 pi 换一个独立的 `PI_CODING_AGENT_DIR` 彻底避开共享锁——需要把凭据复制出去，违反"不处理凭据"；不采用。

## Risks / Trade-offs

- [两份引擎副本漂移] → `sync-engine.sh --check` + CLAUDE.md 规范；任务里把它列为验收步骤。
- [pi-codex-goal 是第三方包，pi 每次启动从 npm 拉] → 钉死版本；拉取失败按启动失败处理（spec 已写）；known-behaviors 记下版本与来源。
- [sandbox-runtime 是 research preview（0.0.x）] → 钉死版本；fail closed；升级需重跑 P10 那组探针。
- [lane 能写用户共享的包缓存（P18 后的取舍）] → 只放行缓存目录本身；npm 缓存按内容寻址有完整性校验，pip 缓存没有，被写坏的风险由用户接受。
- [网络白名单过窄导致 lane 装不了依赖] → 自动并入用户已配的包源；被拒时模型拿到 403，lane 会报阻塞，按现有"上报"路径交给人。
- [pi 的 confirm 弹层样式未实测，`--strict` 下可能被识别为 `unknown`] → `unknown` 本就不发任何输入；任务里安排一次实测并据此补规则。
- [pi 进程本身与其他扩展在沙箱外] → 文档如实写明；lane 里关 MCP；确认页的姿态句不夸大。
- [并发启动在 pi 配置锁上冲突（P14 / P15）] → D9 的串行 + 间隔 + 一次重试；4 秒是经验值，若仍冲突再调 `launch_gap`，known-behaviors 记下实测值。代价是 N 条 pi lane 的派发至少多花约 4(N−1)×2 秒。
- [没有审查模型，越界只有"拦"或"问人"] → 有意为之：codex 审查放行的那类操作正是 lane 被禁止的。

## Migration Plan

- 已有 codex lane：零迁移（D2）。引擎改动后先用一次 codex 派发冒烟，确认 verdict 与今天一致。
- 回滚：`dispatch/pi/` 整个删掉、marketplace 去掉一行，codex 的引擎回退到上一个提交即可；bookkeeping 多出的 `executor` 字段对旧引擎无害（未知键不读）。

## Open Questions

- pi 1.4.0 的 `--offline` 能否在扩展已缓存时省掉启动期的网络请求、又不妨碍首次拉取：实现时试，不影响方案。
