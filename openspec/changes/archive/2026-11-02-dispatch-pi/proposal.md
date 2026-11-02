# Proposal

## Why

dispatch 目前只能把 change 派给 codex。pi 能用第三方模型（本机默认 glm-5.3），派给它可以分担 codex 账号的共享限流，也能让同一个仓库里的 change 按需要选执行者。2026-10-29 已在 herdr 里实测：pi + `pi-codex-goal` 能无人值守跑完一条 OpenSpec apply；sandbox-runtime 能把 pi 的 bash 关在 lane 里且不妨碍提交；pi 自带的 `write` / `edit` 不受该沙箱约束，需要一个路径守卫补上。

## What Changes

- 新增入口 `/dispatch:pi`，子命令与 flag 与 `/dispatch:codex` 一致（`<change…>`、`status`、`setup`；`--strict`、`--ready`、`--no-pr`、`--no-loop`）。
- 执行者成为每条 lane 的属性：从入口命令决定，派发时记下，巡检时按每条 lane 自己的执行者判断。任一入口的 `status` 都覆盖仓库里的全部 lane（两种执行者共用 `<repo>.lanes/` 与 `change/` 前缀，各管各的会互相误判）。
- 引擎（`lane.py`、`doctor.sh`）改为执行者无关 + 一张执行者适配表；`dispatch/codex/` 与 `dispatch/pi/` 各带一份**逐字节相同**的副本，由仓库内的同步脚本检查，保持两个 skill 目录各自自包含。
- pi lane 的姿态：bash 走 OS 级沙箱（sandbox-runtime：只可写 lane worktree、主仓库 `.git`（`.git/hooks` 与 `.git/config` 除外）与包管理器缓存目录；网络按白名单）；`write` / `edit` 走同一组可写根的路径守卫；沙箱起不来时 bash 拒绝执行而不是裸跑；关闭 MCP。默认越界即拦截并把原因交给模型；`--strict` 下越界改为弹给人批准。没有 yolo。
- pi lane 的 goal 用固定版本的 `pi-codex-goal`，启动时 `-e npm:pi-codex-goal@<版本>` 加载，不 `pi install`、不写用户的 pi 配置；goal 状态从 herdr 报告的 session 文件里读。
- pi 的一次性项目信任用 `--approve`（只对本次运行生效，不写 `trust.json`）。
- 发送 prompt 后确认它真的提交了：文字留在输入框而 lane 没开始工作时补一次回车（实测出现过）。
- `setup` / 前置检查按执行者检测：pi、Node ≥ 24、ripgrep、skill 目录里的 sandbox-runtime 依赖、pi 的模型凭据就绪、目标仓库已提交 `.pi/skills/` 或 `.agents/skills/` 里的 `openspec-apply-change`。sandbox-runtime 只在征得同意后 `npm install` 到 skill 目录。
- 文案按执行者：确认页、`verify.md` 的 executor 行、评审请求里的出处、"共享限流"提醒。

## Capabilities

### New Capabilities

- `dispatch-executors`：执行者的选择与记录、跨执行者的巡检、两个入口共用的引擎副本，以及 pi 执行者特有的约定（沙箱与守卫、goal 扩展、项目信任、prompt 提交确认）。

### Modified Capabilities

- `dispatch-lane-launch`：lane 的 agent 由入口决定的执行者担任；姿态要求按执行者表述（codex 维持原样，pi 为沙箱 + 守卫）；启动弹层与 goal 下达不再写死 codex；不带 change 名的场景改指任一入口。
- `dispatch-preflight`：依赖检测与仓库初始化引导按执行者区分；派发时的门槛场景不再写死 codex。
- `dispatch-supervision`：可丢弃的 bookkeeping 允许记执行者；goal 状态的恢复规则从"codex 报告"改为"该 lane 执行者的 goal 状态"。
- `dispatch-publish`：评审请求正文写明的是该 lane 的执行者，而不是固定的 codex。

## Impact

- 新目录：`dispatch/pi/`（`SKILL.md`、`scripts/lane.py`、`scripts/doctor.sh`、`scripts/lane-guard/` 扩展与其 `package.json`、`references/setup.md`、`references/known-behaviors.md`）。
- 改动：`dispatch/codex/scripts/lane.py` 与 `doctor.sh`（执行者适配表；codex 行为不变）、`dispatch/codex/SKILL.md`（巡检覆盖全部 lane 的说明）、`dispatch/README.md`、`.claude-plugin/marketplace.json`（`dispatch` 插件加入 `./dispatch/pi`）、仓库 `CLAUDE.md`、`CHANGELOG.md`。新增 `dispatch/sync-engine.sh`。
- 依赖（仅 pi 执行者）：pi ≥ 1.3.0（实测 1.3.0 / 1.4.0）、Node ≥ 24（`pi-codex-goal` 要求）、ripgrep、`@anthropic-ai/sandbox-runtime` 0.0.26（装在 skill 目录，`node_modules/` 已 gitignore）、首次启动从 npm 拉 `pi-codex-goal`。平台：macOS（Seatbelt）与 Linux（bubblewrap，另需 bwrap、socat）；Windows 不支持。
- 目标仓库仍然零安装物；沙箱策略文件写在 `~/.claude/dispatch/<repo-id>/` 下。
- 已有 codex lane 不受影响：执行者缺省按 herdr 报告的 agent 类型推出，旧 bookkeeping 没有执行者字段时视为 codex。
