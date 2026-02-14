# desktop-kit

将任意 Web App（React / Vue / Svelte / 静态页面）打包为 macOS 桌面客户端。

基于 [Wails v2](https://wails.io)，一条 `/desktop-kit` 命令让 Claude Code Agent 自动完成项目检测、壳代码生成、图标设计、DMG 制作、构建脚本生成的全流程。

## 快速开始

```bash
# 1. 安装 Skill（见项目 README 的安装说明）
mkdir -p ~/.claude/skills
cp -r desktop-kit ~/.claude/skills/desktop-kit

# 2. 进入你的 Web 项目，启动 Claude Code
cd /path/to/my-web-app
claude

# 3. 运行完整向导
/desktop-kit
```

Agent 会自动执行四个阶段：**检测 → 确认 → 生成 → 指引**。

## 命令

| 命令 | 说明 |
|------|------|
| `/desktop-kit` | 完整向导（推荐） |
| `/desktop-kit init` | 仅生成 Wails 壳代码（main.go, app.go, wails.json） |
| `/desktop-kit icon` | 仅生成应用图标 SVG |
| `/desktop-kit dmg-bg` | 仅生成 DMG 安装背景 |
| `/desktop-kit doctor` | 检测环境依赖，报告缺失项 |

## 工作流程

### Phase 1: 项目检测

运行 `scripts/detect-project.sh` 自动识别：

- 前端框架（React / Vue / Svelte / 静态 HTML）
- 构建工具（Vite / Webpack）
- API 调用模式（.env 环境变量 / 源码中的 fetch/axios）
- 应用名称和版本（从 package.json）

### Phase 2: 交互确认

Agent 通过问答确认关键配置：

1. **应用名称** — 用于窗口标题、DMG 卷名、文件名
2. **API 代理** — 是否需要 Go 层反向代理（仅检测到 API 调用时询问）
3. **图标风格** — 渐变 + 字母 / 纯色 + 几何
4. **品牌色** — 可自定义或使用推荐配色
5. **DMG 背景风格** — 简约箭头（MVP 模板）

### Phase 3: 代码生成

根据配置生成以下文件：

```
your-web-project/
├── main.go                     # Wails 入口（embed dist, 窗口配置）
├── app.go                      # App 生命周期（+ 可选 API 代理）
├── wails.json                  # Wails 项目配置
├── build/
│   ├── appicon.svg             # 应用图标 SVG
│   ├── darwin/
│   │   └── Info.plist          # macOS 应用配置
│   └── dmg/
│       ├── background.svg      # DMG 背景 SVG
│       └── background.html     # HTML 包装（用于 PNG 渲染）
└── scripts/
    └── build-dmg.sh            # 构建脚本（版本同步 → 构建 → 签名 → DMG）
```

### Phase 4: 后续指引

输出环境依赖清单、图标/DMG 转换命令、构建命令和首次构建注意事项。

## 环境依赖

| 工具 | 用途 | 安装 | 何时需要 |
|------|------|------|---------|
| Python 3 | 脚本 JSON 解析 | macOS 内置 | 始终 |
| iconutil | ICNS 生成 | macOS 内置 | 图标转换 |
| rsvg-convert | SVG → PNG 渲染 | `brew install librsvg` | 图标/DMG 转换（推荐） |
| Go 1.21+ | Wails 构建 | https://go.dev/dl/ | 构建时 |
| Wails CLI v2 | 桌面应用框架 | `go install github.com/wailsapp/wails/v2/cmd/wails@latest` | 构建时 |
| create-dmg | DMG 制作 | `brew install create-dmg` | 构建时 |

> desktop-kit 负责**生成文件**。Go、Wails、create-dmg 只在执行 `wails build` / `build-dmg.sh` 时才需要。

## 核心特性

### API 代理

当项目需要访问后端 API 时，自动生成 Go 反向代理层：

- 绕过 WKWebView 60s 请求超时限制（代理层 300s）
- 后端 URL 通过 `ldflags` 注入，支持多环境构建
- 仅代理匹配 API 前缀的请求

### 应用图标

遵循 macOS 图标规范（1024x1024 canvas / 800x800 safe area / rx=179 圆角），提供两种模板：

| 模板 | 风格 | 适合 |
|------|------|------|
| A. 渐变 + 字母 | 对角渐变背景 + 白色首字母 | 开发工具、技术产品 |
| B. 纯色 + 几何 | 品牌色背景 + 白色几何图形 | 管理后台、数据工具 |

附带 `scripts/svg-to-icns.sh` 脚本，一键从 SVG 生成 macOS ICNS（10 个尺寸）。

### DMG 背景

精确对齐 create-dmg 坐标系（最容易踩坑的隐性知识）：

```
Canvas 600×400  |  App icon @(150,185)  |  Applications @(450,185)
```

Drop zone 坐标在模板中锁定，Agent 只修改装饰元素，保证坐标永远正确。包含 ad-hoc 签名的首次打开引导文字。

### 构建脚本

生成的 `build-dmg.sh` 覆盖完整构建流程：

```
前置检查 → 版本同步(package.json) → ldflags 注入 → wails build → ad-hoc 签名 → create-dmg
```

## 文件结构

```
desktop-kit/
├── SKILL.md                           # Skill 入口（四阶段 Agent 工作流）
├── DESIGN.md                          # 设计文档（架构决策、知识来源）
├── TESTING.md                         # 测试流程
├── README.md                          # ← 你在这里
│
├── scripts/
│   ├── detect-project.sh              # 项目检测 → JSON 输出
│   └── svg-to-icns.sh                 # SVG → ICNS 转换
│
└── references/                        # Agent 按需加载的知识文档
    ├── wails-scaffold.md              # main.go / app.go / wails.json 生成模式
    ├── api-proxy.md                   # Go 反向代理（ServeHTTP, 300s timeout, ldflags）
    ├── external-links.md              # 外部链接拦截（React / Vue / JS 三版）
    ├── icon-spec.md                   # macOS 图标 canvas 规范
    ├── icon-templates.md              # 2 种图标 SVG 模板 + 推荐配色
    ├── dmg-background-spec.md         # DMG 坐标系 + create-dmg 参数 + HTML 包装
    ├── dmg-templates.md               # DMG 背景 SVG 模板
    ├── build-scripts.md               # build-dmg.sh 生成知识
    └── info-plist.md                  # Info.plist 配置（多语言、ATS、Bundle ID）
```

## 测试

详见 [TESTING.md](TESTING.md)，包含：

1. **脚本单元测试** — detect-project.sh 和 svg-to-icns.sh 的独立验证
2. **端到端 Skill 测试** — 在 mock 项目上跑完整 `/desktop-kit` 流程
3. **生成文件验证** — 检查产出文件的正确性

快速脚本测试：

```bash
# 创建 mock 项目
mkdir -p /tmp/mock-web-app/src
cat > /tmp/mock-web-app/package.json << 'EOF'
{
  "name": "test-app",
  "version": "1.0.0",
  "dependencies": { "react": "^18.2.0" },
  "devDependencies": { "vite": "^5.0.0" }
}
EOF

# 测试项目检测
./scripts/detect-project.sh /tmp/mock-web-app
# → {"appName":"test-app","framework":"react","buildTool":"vite",...}

# 清理
rm -rf /tmp/mock-web-app
```

## 知识来源

所有工程知识提炼自 Argus 项目（AIMI Multi-Agent 可视化调试平台 v0.3.1），一个从 Web SPA 到 macOS 桌面客户端的生产级应用。详见 [DESIGN.md](DESIGN.md)。

## 路线图

- [x] **MVP** — Wails 壳、图标（2 模板）、DMG（1 模板）、构建脚本
- [ ] **P1** — Sparkle 自动更新、发布脚本、故障排查文档、更多模板
- [ ] **P2** — CHANGELOG → appcast 转换、更多前端框架检测
