## Context

desktop-kit 是一个 Claude Code Skill，将"Web App → macOS 桌面客户端"的完整工程流程编码为 Agent 可执行的知识体系。所有技术方案源自 Argus 项目（v0.3.1 生产级桌面应用）的实战验证。

当前状态：工程知识散落在 Argus 代码库中，无法复用。目标是将其结构化为 Skill 三层架构——工程壳（Wails scaffold）、品牌设计（icon + DMG）、构建发布（build pipeline）。

关键约束：
- Skill 运行在 Claude Code Agent 环境中，只能生成文件和执行 shell 脚本，不能安装系统依赖
- macOS 图标和 DMG 背景有精确的坐标规范，必须严格遵循
- MVP 阶段只覆盖 P0 功能（见 proposal），Sparkle 自动更新等为 P1

## Goals / Non-Goals

**Goals:**

- 用户执行 `/desktop-kit` 即可将任意 Web App 打包为 macOS .app + .dmg
- Agent 能自动检测项目框架（React/Vue/Svelte/静态）和 API 调用模式
- 生成的 Wails 壳代码、图标、DMG 背景、构建脚本均为生产可用质量
- 图标和 DMG 背景提供多种预置模板，用户可选择风格
- 所有知识文档自包含，Agent 无需外部文档即可完成任务

**Non-Goals:**

- 不支持 Windows/Linux 打包（仅 macOS）
- 不支持 Tauri/Electron 等其他桌面框架（MVP 仅 Wails v2）
- 不包含 Sparkle 自动更新集成（P1 阶段）
- 不包含发布脚本和 CDN 上传（P1 阶段）
- 不负责安装 Go、Wails CLI 等系统依赖（仅提供检测和指引）
- 不处理 Apple Developer 证书签名（仅支持 ad-hoc 签名）

## Decisions

### D1: 知识架构 — 混合模式（知识驱动 + 模板驱动）

**决策**: 图标和 DMG 背景使用 SVG 模板驱动，Wails 壳代码和构建脚本使用知识驱动。

**理由**: 图标和 DMG 背景有严格的坐标规范（macOS icon safe area、DMG drop zone 坐标），模板能保证规范正确性，Agent 在模板框架内做创意替换（颜色、文字、图形）。而壳代码和脚本需要根据项目上下文（API 前缀、框架类型、是否需要代理）动态生成，知识文档提供模式和注意事项，Agent 现场组装。

**备选方案**:
- 全模板驱动：灵活性不足，无法适配不同项目
- 全知识驱动：图标/DMG 坐标容易出错

### D2: Skill 文件组织 — SKILL.md + references/ + scripts/

**决策**: SKILL.md 作为单一入口包含工作流和决策树，references/ 存放按职责拆分的知识文档，scripts/ 存放可执行工具脚本。

**理由**: SKILL.md 控制 Agent 行为流程，references/ 按需加载避免 context 浪费（Agent 只在需要时读取对应文档），scripts/ 提供 Agent 无法直接完成的操作（如 SVG → ICNS 转换依赖 macOS 原生工具）。

**备选方案**:
- 单文件 SKILL.md 包含所有内容：context 膨胀，超出 token 限制
- 按功能模块拆分多个 Skill：增加用户认知负担

### D3: 项目检测 — Shell 脚本实现

**决策**: 用 `scripts/detect-project.sh` 实现项目检测，输出 JSON 格式结果。

**理由**: Shell 脚本可直接在用户机器执行，无额外依赖。检测逻辑（读 package.json、扫描目录结构、grep API 调用）用 shell 最自然。JSON 输出方便 Agent 解析决策。

**备选方案**:
- Agent 直接用 Read/Grep 工具检测：多轮工具调用，效率低
- Node.js 脚本：增加 Node 依赖假设

### D4: 图标转换 — macOS 原生工具链

**决策**: SVG → PNG 用 `rsvg-convert`（优先）或 `sips`（fallback），PNG → ICNS 用 macOS 内置 `iconutil`。

**理由**: `iconutil` 是 macOS 唯一官方的 ICNS 生成工具，必须使用。`rsvg-convert` 对 SVG 渲染质量最好，`sips` 作为 macOS 内置备选。脚本自动检测可用工具。

### D5: DMG 坐标系 — 硬编码 + 模板锁定

**决策**: DMG 背景 SVG 模板中硬编码 drop zone 坐标（App @150,185 / Applications @450,185），与 create-dmg 参数精确对齐。Agent 仅可修改装饰元素，不可修改 drop zone 位置。

**理由**: 这是 Argus 项目中踩过的最大坑。坐标偏差会导致 DMG 打开后图标位置与背景不对齐。通过模板锁定消除此类错误。

### D6: Agent 工作流 — 四阶段渐进式

**决策**: 检测 → 交互确认 → 代码生成 → 后续指引，四阶段顺序执行。

**理由**: 先检测提供上下文，交互确认让用户控制关键决策（应用名、风格选择），代码生成批量产出所有文件，最后指引用户完成 Agent 无法执行的步骤（安装依赖、执行构建）。

## Risks / Trade-offs

**[R1] SVG 渲染质量受工具限制** → 提供 `rsvg-convert` 和 `sips` 两种路径，脚本自动探测。文档中注明 `rsvg-convert` 为推荐方案。

**[R2] Wails v2 版本锁定** → MVP 绑定 Wails v2（Argus 验证过的版本）。架构上 references/ 按框架分组，未来可新增 wails-v3/ 或 tauri/ 目录扩展。

**[R3] 项目检测可能误判** → detect-project.sh 输出所有检测到的信号和置信度，Agent 在交互确认阶段让用户复核。不依赖单一信号做决策。

**[R4] ad-hoc 签名的 macOS Gatekeeper 拦截** → DMG 背景模板和 SKILL.md 指引中包含首次打开说明（右键 → 打开）。这是 ad-hoc 签名的固有限制，文档中明确告知。

**[R5] references/ 文档过时** → 每个 reference 文件头部标注来源版本（Argus v0.3.1）和适用的 Wails 版本。后续维护时可按版本更新。
