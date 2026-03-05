# Agent Teams 使用指南

## 概述

Agent Teams 让你协调多个 Claude Code 实例协同工作。一个会话作为 Team Lead 协调工作、分配任务、综合结果；Teammate 各自独立工作，拥有独立上下文窗口，可以直接互相通信。

与 Subagent 不同，Agent Teams 中的 teammate 可以互相发消息、共享任务列表、自主认领工作。

## 核心概念

### 架构组成

| 组件 | 角色 |
|------|------|
| **Team Lead** | 主会话，创建团队、产生 teammate、协调工作 |
| **Teammate** | 独立 Claude Code 实例，各自处理分配的任务 |
| **Task List** | 共享任务列表，teammate 认领和完成任务 |
| **Mailbox** | Agent 之间的消息系统 |

### 显示模式

| 模式 | 说明 | 要求 |
|------|------|------|
| **in-process** | 所有 teammate 在主终端运行 | 无额外依赖 |
| **tmux** | 每个 teammate 独立分屏面板 | tmux 或 iTerm2 + it2 CLI |
| **auto**（默认） | tmux 会话内自动分屏，否则 in-process | 无 |

### 操作快捷键（in-process 模式）

| 操作 | 快捷键 |
|------|--------|
| 切换到下一个 teammate | `Shift+Down` |
| 查看 teammate 会话 | `Enter` |
| 中断 teammate 当前回合 | `Escape` |
| 切换任务列表 | `Ctrl+T` |

## 最佳用例

### 1. 并行代码审查

将审查标准拆分为独立维度，每个 teammate 负责一个：

```
Create an agent team to review PR #142. Spawn three reviewers:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
```

### 2. 竞争假设调试

当根因不明确时，让多个 teammate 并行验证不同假设：

```
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses. Have them talk to
each other to try to disprove each other's theories, like a scientific debate.
```

### 3. 新模块/功能开发

各 teammate 负责独立模块，互不干扰：

```
Create a team with 4 teammates to build these modules in parallel:
- Authentication service
- User profile API
- Notification system
- Admin dashboard
Each teammate owns their module entirely.
```

### 4. 跨层协调

前端、后端、测试各由不同 teammate 负责：

```
Create a team to implement the new payment flow:
- Frontend teammate: checkout UI components
- Backend teammate: payment API endpoints
- Test teammate: E2E test suite
Have them coordinate on the API contract.
```

## 高级用法

### 要求计划审批

让 teammate 在实施前先提交计划，由 lead 审核：

```
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
```

Lead 可以批准或驳回计划，驳回时附带反馈，teammate 修改后重新提交。

### 指定模型

```
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

### 质量门控（Hooks）

通过 hooks 在 teammate 完成时执行检查：

- `TeammateIdle`: teammate 即将空闲时触发，exit code 2 = 发送反馈让 teammate 继续工作
- `TaskCompleted`: 任务标记完成时触发，exit code 2 = 阻止完成并发送反馈

## 关键注意事项

### 成本控制

- 每个 teammate 有独立上下文窗口，token 用量随团队规模线性增长
- 推荐 3-5 个 teammate，过多会导致协调开销大于收益
- 每个 teammate 分配 5-6 个 task 是较优比例
- 常规任务用单会话或 subagent 更经济

### 文件冲突

- 避免多个 teammate 编辑同一文件
- 按文件所有权拆分任务，每个 teammate 负责独立的文件集

### 生命周期

- 一个 lead 同时只能管理一个 team
- Teammate 不能产生自己的 team（不支持嵌套）
- Lead 角色固定，不能转移
- 完成后让 **lead** 执行 cleanup，不要让 teammate 执行
- 关闭 teammate: 让 lead 发送 shutdown 请求

### 已知限制

- `/resume` 和 `/rewind` 不会恢复 in-process teammate
- 任务状态可能延迟更新（teammate 忘记标记完成）
- Teammate 关闭前会完成当前请求，可能需要等待
- 分屏模式不支持 VS Code 集成终端、Windows Terminal、Ghostty

### 数据存储

- Team 配置: `~/.claude/teams/{team-name}/config.json`
- Task 列表: `~/.claude/tasks/{team-name}/`
- 孤立 tmux 会话清理: `tmux ls` + `tmux kill-session -t <name>`
