## 1. 目录结构搭建

- [x] 1.1 创建 `session-insights/` 目录和 `session-insights/scripts/` 子目录
- [x] 1.2 将 `~/.claude/commands/scripts/session-insights.py` 复制到 `session-insights/scripts/session-insights.py`，修改输出路径为带时间戳格式 `./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`

## 2. SKILL.md 转换

- [x] 2.1 基于 `~/.claude/commands/session-insights.md` 创建 `session-insights/SKILL.md`：精简 frontmatter 为 name + description（英文），添加 "Script Directory" 段落（`${SKILL_DIR}` 模式），将所有脚本路径引用替换为 `${SKILL_DIR}/scripts/session-insights.py`
- [x] 2.2 更新 SKILL.md 中的输出路径说明，从 `./docs/session-insights-{project-name}.md` 改为 `./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`

## 3. README 编写

- [x] 3.1 创建 `session-insights/README.md`：包含功能简介、安装方式（全局/项目级/符号链接）、使用方式、输出示例、依赖说明（Python 3 标准库）

## 4. 仓库注册与更新

- [x] 4.1 在 `.claude-plugin/marketplace.json` 的 `skills` 数组中添加 `"./session-insights"`
- [x] 4.2 更新仓库 `README.md`：Skills 表格添加 session-insights 行，目录结构添加 `session-insights/` 条目，路线图添加相关条目
