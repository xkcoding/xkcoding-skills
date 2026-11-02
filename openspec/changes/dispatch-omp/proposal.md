# Proposal

## Why

`/dispatch:pi` 为了让 pi 能无人值守，在外面补了一圈：外挂第三方 goal 扩展、逐条错开启动以躲开 pi 的配置锁、"无模型就重启"、发完 prompt 再核对有没有提交。oh-my-pi（omp）把其中大部分做成了内置：启动参数 `--goal` 直接下达目标、goal 状态写进 session、凭据在 SQLite 里不抢文件锁、自带花费 / 时长上限。2026-11-02 在 herdr 里实测：omp 18.15.0 + lane-guard（经 omp 的 pi 兼容层）跑完一条 2 task 的 OpenSpec apply，4 个 omp 并发启动并发请求全部正常。用户决定用 omp 取代 pi。

## What Changes

- 新增入口 `/dispatch:omp`（`dispatch/omp/` 自包含 skill），子命令与 flag 与 `/dispatch:codex` 一致。
- **BREAKING** 删除 `/dispatch:pi` 与引擎里的 pi 执行者。已有的 pi lane 在新版里显示为 `unknown_executor`，不再被巡检操纵，需用户手动收尾（2026-11-02 本机有 1 条在跑）。
- omp lane 的启动：`--goal "<goal 文本>"` 在启动时下达（不再发 goal prompt），强制工具白名单 `--tools read,bash,edit,write,goal`，加 `--no-pty --no-lsp`，模型用用户在 omp 里设的默认模型；不加白名单时 `eval`、`glob`、`task`、`web_search`、`xd://ast_edit` 等会绕过 lane 的边界（实测）。
- lane-guard 随 skill 迁到 `dispatch/omp/scripts/lane-guard/`，并补一个实测到的漏洞：omp 的 `read` 能读 `http(s)://`、`www.` 和二十来种内部 URI，在沙箱外执行（实测 `read https://example.com` 取回网页而 bash 的 curl 被拒）。守卫对 `read` 只放行普通路径与 `skill://`，其余一律拦下。
- 引擎的 omp 执行者：从 session 的 `mode_change`（`data.goal.status`）与 `goal-completed` 读 goal 状态；`idle` 即空闲；omp 并发启动无锁冲突，启动间隔为 0，不需要"无模型重启"。omp 自己的界面识别与"提交确认"按实测校准。
- `setup` / 前置检查按 omp：`omp`、`rg`、`node` / `npm`（只为 `npm ci` 装沙箱依赖）、skill 目录里的 sandbox-runtime、omp 默认模型及其可用性、目标仓库已提交 `.omp/skills/`、`.agents/skills/` 或 `.claude/skills/` 里的 `openspec-apply-change`。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `dispatch-executors`：执行者从 codex + pi 改为 codex + omp；pi 专属的要求（沙箱、文件工具、MCP、配置、goal 扩展、错开启动、提交确认）移除，换成 omp 的版本；新增"lane 的工具被限定在白名单内"与"`read` 不能经 URL / 内部 URI 出沙箱"。
- `dispatch-lane-launch`：姿态、启动期提示、goal 下达里的 pi 改为 omp；omp 的 goal 在启动时下达。
- `dispatch-preflight`：依赖检测、凭据与仓库初始化引导里的 pi 改为 omp。
- `dispatch-supervision`：goal 状态的场景从 pi 改为 omp。
- `dispatch-publish`：评审请求出处的场景从 pi 改为 omp。

## Impact

- 新目录 `dispatch/omp/`（`SKILL.md`、`scripts/{lane.py,doctor.sh}`、`scripts/lane-guard/`、`references/{setup.md,known-behaviors.md}`）；删除 `dispatch/pi/`。
- 改动：`dispatch/codex/scripts/lane.py` 与 `doctor.sh`（pi 行换成 omp 行）、`dispatch/codex/SKILL.md`、`dispatch/sync-engine.sh`（目标从 `pi` 改为 `omp`）、`dispatch/README.md`、`.claude-plugin/marketplace.json`（`./dispatch/pi` 换成 `./dispatch/omp`）、仓库 `CLAUDE.md`、`CHANGELOG.md`。
- 依赖：omp ≥ 18.15.0（bun 全局安装）及其 herdr 集成；ripgrep；npm 仅用于安装 lane-guard 的 `@anthropic-ai/sandbox-runtime` 0.0.26。不再需要 pi、`pi-codex-goal`、Node ≥ 24。
- 用户侧：需要在 omp 里登录并设默认模型；升级插件后重新对 `dispatch/omp` 的 lane-guard 跑一次 `npm ci`（`/dispatch:omp setup` 会引导）；本机进行中的 pi lane 要在升级前收尾，或升级后手动处理。
