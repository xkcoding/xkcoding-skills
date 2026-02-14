---
name: desktop-kit
description: 将任意 Web App（React/Vue/静态页面）打包为 macOS 桌面客户端（基于 Wails v2）
---

# Desktop Kit

一条命令，把任意 Web App 打包成 macOS 桌面客户端。

## 触发方式

- `/desktop-kit` — 完整向导（推荐）
- `/desktop-kit init` — 仅生成 Wails 壳代码
- `/desktop-kit icon` — 仅生成应用图标
- `/desktop-kit dmg-bg` — 仅生成 DMG 背景
- `/desktop-kit doctor` — 环境检测 + 问题诊断

---

## 子命令路由

根据用户输入的子命令，跳转到对应阶段：

| 子命令 | 执行阶段 |
|--------|---------|
| `/desktop-kit`（无参数） | Phase 1 → 2 → 3 → 4 完整流程 |
| `/desktop-kit init` | Phase 1 → 2（仅 Wails 相关问题）→ 生成 Wails 壳代码 → Phase 4 |
| `/desktop-kit icon` | Phase 2（仅图标相关问题）→ 生成图标 SVG → Phase 4（图标转换指引） |
| `/desktop-kit dmg-bg` | Phase 2（仅 DMG 相关问题）→ 生成 DMG 背景 → Phase 4（PNG 转换指引） |
| `/desktop-kit doctor` | 检测环境依赖（Go、Wails、create-dmg、rsvg-convert），报告缺失项和安装方式 |

---

## Phase 1: 项目检测

运行项目检测脚本，获取目标项目的技术栈信息。

### 步骤

1. 确定目标项目目录（默认为当前工作目录）
2. 执行 `scripts/detect-project.sh <project-dir>`
3. 解析 JSON 输出结果
4. 向用户展示检测摘要：

```
检测结果:
  项目名称:   {{appName}}
  版本:       {{appVersion}}
  前端框架:   {{framework}} (置信度: {{frameworkConfidence}})
  构建工具:   {{buildTool}}
  API 代理:   {{apiProxy}} {{apiPrefix}}
```

### 异常处理

- 检测脚本返回 error → 提示用户确认项目目录是否正确，是否包含 package.json
- framework 为 unknown → 询问用户手动指定框架类型
- frameworkConfidence 为 low/medium → 展示检测依据，请用户确认

---

## Phase 2: 交互确认

通过 AskUserQuestion 工具向用户确认关键决策。

### 问题清单

**Q1: 应用名称**
- 默认值：来自检测结果的 `appName`
- 示例："my-tool"
- 用于：窗口标题、DMG 卷名、输出文件名

**Q2: 是否需要 API 代理**
- 仅当检测到 `apiProxy: true` 时询问
- 选项：是（推荐）/ 否
- 如果选「是」，确认 API 路径前缀（默认从检测结果）

**Q3: 图标风格**
- 选项：
  - A. 渐变 + 字母 — 适合开发工具、技术产品
  - B. 纯色 + 几何 — 适合管理后台、数据工具
- 读取 `references/icon-templates.md` 了解各模板详情

**Q4: 品牌色**
- 如果项目有 tailwind.config，尝试提取主色并建议
- 否则提供推荐配色表（从 icon-templates.md 中获取）
- 用户可自定义输入十六进制色值

**Q5: DMG 背景风格**
- 选项：A. 简约箭头（当前 MVP 仅此模板）
- 读取 `references/dmg-templates.md` 了解模板详情

---

## Phase 3: 代码生成

根据检测结果和用户确认，读取 references 并生成所有文件。

### 生成顺序

```
Step 1: Wails 壳代码
  读取: references/wails-scaffold.md
  生成: main.go, app.go, wails.json

Step 2: API 代理（如果需要）
  读取: references/api-proxy.md
  修改: app.go (添加 ServeHTTP), main.go (添加 Handler)

Step 3: 外部链接拦截
  读取: references/external-links.md
  生成: 根据框架类型选择代码片段，提示用户添加到入口组件

Step 4: 应用图标
  读取: references/icon-spec.md, references/icon-templates.md
  生成: build/appicon.svg

Step 5: DMG 背景
  读取: references/dmg-background-spec.md, references/dmg-templates.md
  生成: build/dmg/background.svg, build/dmg/background.html

Step 6: 构建脚本
  读取: references/build-scripts.md
  生成: scripts/build-dmg.sh (chmod +x)

Step 7: Info.plist
  读取: references/info-plist.md
  生成: build/darwin/Info.plist
```

### Reference 加载决策树

```
生成 Wails 壳?
├─ 是 → 读取 wails-scaffold.md
│   └─ 需要 API 代理?
│       ├─ 是 → 额外读取 api-proxy.md
│       └─ 否 → 跳过
└─ 否 (子命令 icon/dmg-bg) → 跳过

生成图标?
├─ 是 → 读取 icon-spec.md + icon-templates.md
└─ 否 → 跳过

生成 DMG 背景?
├─ 是 → 读取 dmg-background-spec.md + dmg-templates.md
└─ 否 → 跳过

生成构建脚本?
├─ 是 → 读取 build-scripts.md + info-plist.md
└─ 否 → 跳过
```

### 参数替换

所有模板中的 `{{占位符}}` 使用以下来源替换：

| 占位符 | 来源 |
|--------|------|
| `{{APP_NAME}}` | Q1 确认的应用名 |
| `{{APP_VERSION}}` | detect-project.sh → appVersion |
| `{{API_PREFIX}}` | Q2 确认的 API 前缀 |
| `{{COLOR_1}}` / `{{COLOR_2}}` | Q4 确认的品牌色 |
| `{{BG_COLOR}}` | Q4 品牌主色 |
| `{{LETTER}}` | 应用名首字母（大写） |
| `{{ACCENT_COLOR}}` | Q4 品牌色（或推荐色） |
| `{{BUNDLE_ID}}` | 从应用名推导 com.{org}.{appname} |

---

## Phase 4: 后续指引

代码生成完成后，输出以下指引信息。

### 环境依赖

```
请确保已安装以下工具:

  ✅/❌ Go 1.21+          → https://go.dev/dl/
  ✅/❌ Wails CLI v2      → go install github.com/wailsapp/wails/v2/cmd/wails@latest
  ✅/❌ create-dmg        → brew install create-dmg
  ✅/❌ rsvg-convert (可选) → brew install librsvg

运行 `/desktop-kit doctor` 检测环境。
```

（用 `command -v` 检测每个工具是否已安装，显示 ✅ 或 ❌）

### 图标转换

```
将 SVG 图标转为 macOS ICNS:

  ./desktop-kit/scripts/svg-to-icns.sh build/appicon.svg build/

产出:
  build/AppIcon.iconset/  (多尺寸 PNG)
  build/appicon.icns      (macOS 图标文件)
```

### DMG 背景转换

```
将 SVG 背景转为 PNG (二选一):

方式 A - Chrome 截图 (推荐):
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless --screenshot="build/dmg/background.png" \
    --window-size=1200,800 \
    "build/dmg/background.html"

方式 B - rsvg-convert:
  rsvg-convert -w 1200 -h 800 build/dmg/background.svg -o build/dmg/background.png
```

### 构建命令

```
构建 .app + .dmg:

  chmod +x scripts/build-dmg.sh
  ./scripts/build-dmg.sh

产出:
  build/bin/{{APP_NAME}}.app              (macOS 应用)
  build/bin/{{APP_NAME}}-{{VERSION}}-macOS.dmg  (安装包)
```

### 首次构建注意事项

```
1. 首次构建前确保前端能正常 `npm run build`
2. Go module 初始化: go mod init {{BUNDLE_ID}} && go mod tidy
3. Wails 开发模式: wails dev (热更新调试)
4. ad-hoc 签名的应用首次打开: 右键 → 打开
```

---

## Agent 能力边界

| 能做 | 不能做 |
|------|--------|
| 扫描项目结构，识别框架 | 安装 Go / Wails CLI |
| 生成 main.go / app.go / wails.json | 下载 Sparkle.framework |
| 生成构建脚本 | 配置 CDN / OSS 凭证 |
| 生成应用图标 SVG | Apple Developer 证书签名 |
| 生成 DMG 背景 SVG + HTML | 执行 wails build |
| 检测 API 调用模式 | 实际网络请求测试 |
| 诊断环境依赖 | — |
