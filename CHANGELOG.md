# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-30

### Added

- **skill-audit**: 新增 Agent Skill/Prompt 质量审计 skill
  - 五项反模式检查：事实/推断混淆、行为锚定、过度详细、排他性分类、自由度匹配
  - 注册到 `productivity-skills` 插件组
- **dark-luxury-editorial**: 新增暗黑奢华杂志风网页生成 skill
  - 把旅行文本/路书/游记转成 React + Tailwind 编辑型网页
  - 8 个分主题 references（benchmark 视觉基线、brief→site 工作流、intent→行程规划、图片与音频管线、实现 recipes、editorial 文案、failure modes/QA、产品演进）
  - 经过 skill-audit 质量调优：non-negotiables 16 条 → 9 条 soul rules，决策矩阵从 4 层嵌套合并为优先级排序，关键约束词软化并补充 why
  - 注册到新增的 `design-skills` 插件组

## [0.2.0] - 2026-03-06

### Added

- **agent-team-setup**: 新增 Agent Teams 环境配置 skill
  - `SKILL.md`: 4 步向导（检测 → 配置 → 验证 → 指南）+ 子命令路由（doctor/enable/guide）
  - `scripts/doctor.sh`: 环境诊断脚本，检测 15 项依赖并输出 JSON 报告
  - `references/agent-teams-guide.md`: Agent Teams 使用指南和最佳实践
  - 注册到 `dev-skills` 插件组

## [0.1.0] - 2026-02-18

### Added

- **desktop-kit**: 将任意 Web App 打包为 macOS 桌面客户端（基于 Wails v2）
- **session-insights**: 分析 Claude Code 会话数据，生成带 Mermaid 图表的 Markdown 洞察报告
- 初始化 marketplace.json，拆分为 `dev-skills` 和 `productivity-skills` 两个插件组
