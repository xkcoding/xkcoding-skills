## Why

desktop-kit 是一个 Claude Code Skill，用于将任意 Web App（React/Vue/静态页面）一条命令打包成 macOS 桌面客户端。当前所有 Web → Desktop 的工程知识（Wails 壳代码、API 代理、图标规范、DMG 坐标系、构建签名）都散落在 Argus 项目中，没有被结构化编码。需要将这些隐性知识提炼为 Skill，让 Agent 具备自动完成整个桌面化流程的能力。

## What Changes

- 新增 `desktop-kit/SKILL.md` 作为 Skill 主入口，包含完整 Agent 工作流和决策树
- 新增 `desktop-kit/references/` 目录，包含 Wails 壳代码、API 代理、图标规范、DMG 背景规范、构建脚本等知识文档
- 新增 `desktop-kit/scripts/` 目录，包含项目检测脚本和图标转换脚本
- 注册 Skill 到 `.claude-plugin/marketplace.json`

## Capabilities

### New Capabilities

- `project-detection`: 自动检测目标 Web 项目的前端框架（React/Vue/Svelte/静态）、构建工具（Vite/Webpack）、API 调用模式，为后续代码生成提供上下文
- `wails-scaffold`: Wails v2 工程壳代码生成，包括 main.go、app.go、wails.json，以及可选的 Go 反向代理层（绕过 WKWebView 60s 超时限制）和前端外部链接拦截
- `app-icon-gen`: macOS 应用图标生成，遵循 1024x1024 canvas / 800x800 safe area / rx=179 圆角规范，提供多种 SVG 模板（渐变字母、纯色几何、深色发光、柔和扁平），支持 SVG → 多尺寸 PNG → ICNS 转换
- `dmg-background-gen`: DMG 安装背景图生成，精确对齐 create-dmg 坐标系（App icon @150,185 / Apps folder @450,185），提供多种 SVG 模板，包含安装引导文字
- `build-pipeline`: macOS 构建管线，包括版本同步（package.json 为单一来源）、环境变量注入（ldflags）、构建脚本生成（wails build + codesign + create-dmg）、Info.plist 生成

### Modified Capabilities

（无已有 capabilities，本项目为全新创建）

## Impact

- **新增文件**: ~15 个文件（1 SKILL.md + ~10 references + 2-3 scripts + marketplace 注册）
- **依赖工具**: Go 1.21+, Wails CLI v2, create-dmg, iconutil（macOS 内置）
- **可选依赖**: Sparkle 2.x（自动更新，P1 阶段）, rsvg-convert（SVG 渲染备选）
- **影响范围**: 仅新增 desktop-kit/ 目录，不修改仓库已有内容
- **目标用户**: 需要将内部 Web 工具打包为 macOS 桌面客户端的开发者
