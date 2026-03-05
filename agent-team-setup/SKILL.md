---
name: agent-team-setup
description: One-command setup for Claude Code Agent Teams — enable experimental flag, configure display mode, install dependencies (tmux/iTerm2), and verify the environment.
---

# /agent-team-setup - Agent Team 环境配置

一条命令完成 Claude Code Agent Teams 的环境准备：开启实验特性、配置显示模式、安装依赖、验证环境。

## 触发方式

- `/agent-team-setup` — 完整向导（推荐）
- `/agent-team-setup doctor` — 仅环境检测，不做任何修改
- `/agent-team-setup enable` — 仅开启实验特性标志
- `/agent-team-setup guide` — 输出 Agent Teams 使用指南和最佳实践

---

## 子命令路由

| 子命令 | 执行阶段 |
|--------|---------|
| `/agent-team-setup`（无参数） | Step 0 → 1 → 2 → 3 → 4 完整流程 |
| `/agent-team-setup doctor` | 仅 Step 1（环境检测报告） |
| `/agent-team-setup enable` | Step 2（仅开启 flag + 验证） |
| `/agent-team-setup guide` | 仅 Step 4（输出使用指南） |

---

## Script Directory

**Important**: All scripts are located in the `scripts/` subdirectory of this skill.

**Agent Execution Instructions**:
1. Determine this SKILL.md file's directory path as `SKILL_DIR`
2. Script path = `${SKILL_DIR}/scripts/<script-name>.sh`
3. Replace all `${SKILL_DIR}` in this document with the actual path

**Script Reference**:
| Script | Purpose |
|--------|---------|
| `scripts/doctor.sh` | 检测 Agent Teams 所需的全部环境依赖，输出 JSON 诊断报告 |

---

## Step 0: 交互引导

调用 `AskUserQuestion` 工具，**精确使用以下参数**：

```json
{
  "questions": [
    {
      "question": "选择 Agent Team 的显示模式",
      "header": "Display Mode",
      "multiSelect": false,
      "options": [
        {"label": "auto (Recommended)", "description": "自动检测：tmux 会话内用分屏，否则用 in-process"},
        {"label": "in-process", "description": "所有 teammate 在主终端运行，Shift+Down 切换，无需额外依赖"},
        {"label": "tmux", "description": "每个 teammate 独立分屏面板，需要安装 tmux 或 iTerm2"}
      ]
    },
    {
      "question": "是否同时配置权限模式？",
      "header": "Permissions",
      "multiSelect": false,
      "options": [
        {"label": "保持默认 (Recommended)", "description": "teammate 继承 lead 的权限设置，逐条确认"},
        {"label": "预批准常用操作", "description": "在 permissions 中预批准 Read/Edit/Glob/Grep/Bash 等常用工具，减少中断"}
      ]
    }
  ]
}
```

如果用户在调用时已提供明确参数（如 `--mode tmux`），可跳过对应引导。

---

## Step 1: 环境检测

运行诊断脚本，获取当前环境状态：

```bash
bash ${SKILL_DIR}/scripts/doctor.sh
```

脚本输出 JSON 格式的诊断报告，包含以下字段：

| 字段 | 说明 |
|------|------|
| `claude_code_installed` | Claude Code CLI 是否可用 |
| `claude_code_version` | Claude Code 版本号 |
| `agent_teams_enabled` | 实验标志是否已开启 |
| `settings_json_path` | settings.json 文件路径 |
| `settings_json_exists` | settings.json 是否存在 |
| `current_teammate_mode` | 当前配置的 teammateMode |
| `tmux_installed` | tmux 是否已安装 |
| `tmux_version` | tmux 版本号 |
| `iterm2_running` | 是否在 iTerm2 中运行 |
| `it2_cli_installed` | it2 CLI 是否可用 |
| `terminal` | 当前终端类型 |
| `os` | 操作系统 |
| `shell` | 当前 shell |

**解析 JSON 输出并向用户展示检测摘要**：

```
Agent Teams 环境检测:
  Claude Code:     vX.X.X
  实验特性标志:     已开启 / 未开启
  显示模式:        auto / in-process / tmux
  tmux:           vX.X / 未安装
  iTerm2:         运行中 (it2 CLI: 可用) / 未检测到
  终端:           iTerm2 / Terminal.app / tmux / 其他
```

**子命令 `doctor`**：输出检测摘要后结束，不继续后续步骤。

---

## Step 2: 应用配置

根据 Step 0 的用户选择和 Step 1 的检测结果，执行配置操作。

### 2.1 开启实验特性标志

**检查**：如果 `agent_teams_enabled` 已为 true，跳过此步。

**操作**：读取 `~/.claude/settings.json`（如果不存在则创建），确保包含：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**注意**：保留 settings.json 中已有的其他配置项，仅添加/更新 `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`。

### 2.2 配置显示模式

**操作**：在 `~/.claude/settings.json` 中设置 `teammateMode`：

```json
{
  "teammateMode": "auto"
}
```

值来自 Step 0 问题 1 的选择：
- "auto (Recommended)" → `"auto"`
- "in-process" → `"in-process"`
- "tmux" → `"tmux"`

### 2.3 安装依赖（仅 tmux 模式需要）

如果用户选择了 `tmux` 模式且 `tmux_installed` 为 false：

**macOS**：
```bash
brew install tmux
```

**提示用户确认安装**，不要自动执行。

如果用户在 iTerm2 中且 `it2_cli_installed` 为 false，提示：
```
iTerm2 检测到，但 it2 CLI 未安装。
安装方式: brew install mkusaka/it2/it2
然后在 iTerm2 → Settings → General → Magic → 勾选 Enable Python API
```

### 2.4 预批准权限（可选）

如果用户选择了「预批准常用操作」，提示用户在项目 `.claude/settings.json` 或全局 `~/.claude/settings.json` 中添加权限配置。

**提示用户手动确认并添加**，Agent 不自动修改权限配置。输出建议配置示例供用户参考：

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "WebFetch"
    ]
  }
}
```

---

## Step 3: 验证配置

配置完成后，再次运行诊断脚本验证：

```bash
bash ${SKILL_DIR}/scripts/doctor.sh
```

对比 Step 1 和 Step 3 的结果，输出变更摘要：

```
配置完成! 变更摘要:
  [CHANGED] 实验特性标志:  未开启 → 已开启
  [CHANGED] 显示模式:      (未设置) → auto
  [OK]      tmux:          v3.4 (已安装)
  [OK]      Claude Code:   v1.x.x
```

如果有未通过的检查项，给出具体修复建议。

---

## Step 4: 使用指南

读取 `${SKILL_DIR}/references/agent-teams-guide.md`，向用户输出精简的使用指南。

输出内容包含：

### 4.1 快速启动

```
Agent Teams 已就绪! 以下是快速入门:

1. 启动 Claude Code:
   claude

2. 描述任务并请求创建团队:
   "Create an agent team to review PR #142. Spawn three reviewers:
    - One focused on security implications
    - One checking performance impact
    - One validating test coverage"

3. 操作 teammate:
   - Shift+Down: 切换到下一个 teammate
   - 直接输入: 给当前 teammate 发消息
   - Ctrl+T: 切换任务列表显示
```

### 4.2 推荐用例

从 references/agent-teams-guide.md 中提取 3-4 个最佳用例场景，简要描述。

### 4.3 注意事项

```
注意事项:
  - Agent Teams 是实验特性，不支持 /resume 恢复 in-process teammate
  - 每个 teammate 消耗独立 token，成本随团队规模线性增长
  - 建议 3-5 个 teammate，每人 5-6 个 task
  - 避免多个 teammate 编辑同一文件
  - 完成后让 lead 执行 cleanup，不要让 teammate 执行
```

---

## Agent 能力边界

| 能做 | 不能做 |
|------|--------|
| 检测环境依赖状态 | 安装 Homebrew |
| 配置 settings.json | 修改 Claude Code 内部设置 |
| 安装 tmux（需确认） | 配置 iTerm2 Python API |
| 输出使用指南和最佳实践 | 启动 Agent Team 实例 |
| 诊断配置问题 | 修复 Claude Code 本身的 bug |
