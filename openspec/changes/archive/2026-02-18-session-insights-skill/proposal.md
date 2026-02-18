## Why

当前 `session-insights` 以个人 slash command 形式存在于 `~/.claude/commands/`，无法通过仓库分享给其他人。需要将其转换为标准 Skill 格式（`SKILL.md` + `scripts/` + `README.md`），纳入 xkcoding-skills 仓库，使其他 Claude Code 用户可以一键安装使用。

## What Changes

- 新增 `session-insights/` 目录，包含完整 Skill 结构
- 将 `~/.claude/commands/session-insights.md` 转换为 `session-insights/SKILL.md`，采用 baoyu-skills 的 `${SKILL_DIR}` 脚本引用模式
- 将 `~/.claude/commands/scripts/session-insights.py` 迁移为 `session-insights/scripts/session-insights.py`
- Frontmatter 从 commands 格式（category/complexity/mcp-servers/personas）精简为 Skills 标准格式（name + description）
- 输出路径从 `./docs/session-insights-{project-name}.md` 调整为 `./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`（加时间戳，保留历史快照）
- 新增 `session-insights/README.md` 面向用户文档
- 在 `.claude-plugin/marketplace.json` 中注册新 Skill
- 更新仓库 `README.md` 的 Skills 表格

## Capabilities

### New Capabilities
- `skill-packaging`: Skill 目录结构、SKILL.md 入口、脚本引用模式、marketplace 注册
- `session-analysis`: 会话数据提取、活跃时间计算、交互模式识别、Mermaid 报告生成

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- 新增文件：`session-insights/SKILL.md`、`session-insights/scripts/session-insights.py`、`session-insights/README.md`
- 修改文件：`.claude-plugin/marketplace.json`（注册新 Skill）、`README.md`（更新 Skills 表格）
- 依赖：Python 3 标准库（无外部依赖）
- 用户影响：安装后可通过 `/session-insights` 触发会话洞察分析
