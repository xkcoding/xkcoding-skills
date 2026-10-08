# Proposal

## Why

用 OpenSpec 做规划的人，想把"执行"这一段外包给 codex：Claude 负责 propose、验收和发布，codex 在隔离的 worktree 里按 `tasks.md` 干活，多个 change 可以同时跑。现成的 [bestony/herdr-dispatch](https://github.com/bestony/herdr-dispatch) 证明了"herdr + worktree + 调度者巡检"这条路可行，但它自带一套私有状态协议（`.dispatch/TASK.md`、`progress.md`、`DONE`、`state.json`），和 OpenSpec 已有的 change / `tasks.md` / `all_done` 是两份真相。

本变更做一个只借鉴其思路、状态全部交给 OpenSpec 管的派发 skill。2026-09-18 的两轮 spike（herdr 0.9.0、openspec 1.13.1、codex 0.154.0 → 0.155.0）已经把最关键的假设验证过：`/goal` 能带着 `$openspec-apply-change` 跑通、`--approve-for-me` 下 lane 全程无人工审批、3 条 lane 并行向同一个 `.git` 提交零锁冲突、巡检可以完全不存状态文件。现在可以落地 MVP 并用真实 change 试运行。

## What Changes

- 新增插件 `dispatch`，含一个自包含的 skill `codex`（带子命令），入口位于 `/opsx:propose` 与 `/opsx:apply` 之间，**不改写、不覆盖任何 OpenSpec 命令**：
  - `/dispatch:codex <change…>`：把已 propose 的 change 派发给 codex。每个 change 一条 lane（一个 herdr worktree + 一个 codex agent），lane 内执行标准的 `$openspec-apply-change`。
  - `/dispatch:codex status`：对所有 lane 做一次巡检并给出总览；派发后由 `/loop` 定时调用。
  - `/dispatch:codex setup`：一次性依赖检测（openspec / herdr / codex / gh）、征得同意后协助安装、上手引导（含如何退出）。
- 确定性、易碎的操作（推导名字、建 worktree 与 propose commit、启动、下达 goal、总览、写验证记录、发布）收在一个随 skill 发布的脚本 `scripts/lane.py` 里，`SKILL.md` 只负责编排与需要判断的部分。
- 进度与状态只用 OpenSpec 原生信号：lane worktree 内的 `openspec instructions apply --json`（`progress`、`state`）。不引入 `.dispatch/`、`state.json` 之类的私有协议，**MVP 不带自定义 schema**。
- change 产物作为 lane 分支的第一个 commit（`docs(openspec): propose <change>`）；调度者永不 commit、永不 push base 分支。
- 默认审批姿态为 codex 的 `--approve-for-me`（guardian 自动审查 + workspace-write 沙箱），另提供严格模式；MVP 不提供 yolo。
- lane 声明完成（`all_done`）后，调度者独立重跑验收、把结果写成 change 目录下的普通文件 `verify.md`、再 push lane 分支并开评审请求（PR / MR）。自动段止于"评审请求已开"。
- 评审请求不绑定 GitHub：push 是纯 git；开评审请求按 `origin` 的 host 选工具——GitHub 用 `gh`、GitLab 用 `glab`、内部平台交给运行时里现有的 MR 工具或 skill（脚本交出与平台无关的交接包）。认不出的 host 只问用户一次，选择按 host 记住。
- `archive`、merge、worktree 清理一律不自动执行：命令打印给用户，由人来跑。
- 目标仓库零残留：不装 schema、不改 `openspec/config.yaml`、不装 git hook。卸载插件即完成退出，在途 change 仍是普通的 spec-driven change。

## Capabilities

### New Capabilities

- `dispatch-preflight`：依赖与环境检测。setup 时可征得同意后协助安装；每次派发前只检查不安装，缺失即停并说明。
- `dispatch-lane-launch`：把一个 change 变成一条 lane——准入判定、worktree 与 propose commit、按姿态启动 codex、处理启动期弹层、下达 goal 与 lane 边界。
- `dispatch-supervision`：无状态文件的巡检——从 herdr、git、openspec 反查 lane 总览，判定完成 / 停滞 / 阻塞，续跑或上报，定时循环的启停。
- `dispatch-publish`：验证与发布——独立重跑验收、写 `verify.md`、检测 lane 越界 push、push 分支并开 PR、各种降级，以及"永不 archive / merge / 删除"的边界。

### Modified Capabilities

（无。`openspec/specs/` 目前为空。）

## Impact

- **新增目录**：`dispatch/codex/`（`SKILL.md` + `scripts/{doctor.sh,lane.py}` + `references/`）与 `dispatch/README.md`。
- **修改文件**：`.claude-plugin/marketplace.json`（注册插件 `dispatch`）、`CLAUDE.md`、`README.md`、`CHANGELOG.md`（登记新 skill）、`.gitignore`（忽略 Python 字节码）。
- **运行时依赖**（用户机器）：herdr、codex CLI、openspec CLI、git；`gh` / `glab` 可选，且只在仓库托管于 GitHub / GitLab 时才用得上。目标仓库需已执行 `openspec init --tools codex`（其 `.agents/skills/` 需已提交）。
- **外部耦合**：herdr CLI、codex CLI（尤其 `--approve-for-me`、`/goal`、启动期弹层）与 OpenSpec 生成的 `openspec-apply-change` skill 的行为都会随版本漂移；driver 里的每条结论须标注验证所用版本。
- **不影响**：本仓库现有 skill；用户目标仓库的 OpenSpec 配置与既有 change。
