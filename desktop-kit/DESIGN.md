# Desktop Kit — 完整设计文档

> 本文档沉淀了 desktop-kit Skill 的完整设计思路、知识来源、架构决策和实现规划。
> 源自 Argus 项目（AIMI Multi-Agent 可视化调试平台）从 Web SPA 到 macOS 桌面客户端的全部工程经验。
> 用于后续通过 OpenSpec 进行实现时恢复上下文。

---

## 1. Skill 定位

**一句话**：一条命令，把任意 Web App 打包成 macOS 桌面客户端。

**核心价值**：将"Web → Desktop"过程中的所有隐性工程知识（Wails 壳代码、API 代理、图标设计规范、DMG 背景坐标系、构建签名脚本、Sparkle 自动更新）编码成 Claude Code Agent Skill，让 Agent 具备自动完成这一切的能力。

**目标用户**：需要将内部 Web 工具（管理后台、调试工具、数据看板）打包为桌面客户端的开发者。

**触发关键词**：`/desktop-kit`、"打包成桌面应用"、"生成 app icon"、"做 DMG 背景"。

---

## 2. 知识来源：Argus 项目

所有知识提炼自 Argus（`/Users/yangkai.shen/code/xiaohongshu/argus`），一个 v0.3.1 的生产级桌面应用。

### 2.1 Argus 的桌面化做了哪些事

| 类别 | Argus 文件 | 做了什么 |
|------|-----------|---------|
| Wails 入口 | `main.go` | embed dist, Wails options, App binding |
| App 生命周期 | `app.go` | startup, ServeHTTP (反向代理), CheckForUpdates |
| Wails 配置 | `wails.json` | 项目名、版本同步、前端构建命令 |
| API 代理 | `app.go:ServeHTTP` | Go http.Client 300s timeout，绕过 WKWebView 60s 限制 |
| URL 注入 | `build-dmg.sh` + ldflags | `.env.production` → ldflags `-X main.backendURL=...` |
| 外部链接 | `App.tsx` | 拦截 `<a href>` 点击，调用 `window.runtime.BrowserOpenURL()` |
| 应用图标 | `build/appicon.svg` → `.png` → `.icns` | 1024×1024 SVG，macOS 圆角矩形规范 |
| DMG 背景 | `build/dmg/background.svg` → `.html` → `.png` | 600×400，精确 drop zone 坐标 |
| 构建脚本 | `scripts/build-dmg.sh` | 版本同步 + wails build + Sparkle 嵌入 + codesign + DMG |
| 发布脚本 | `scripts/publish-update.sh` | EdDSA 签名 + appcast.xml + ossutil 上传 CDN |
| Info.plist | `build/darwin/Info.plist` | 多语言、Sparkle keys、NSAppTransportSecurity |
| 自动更新 | Sparkle 2.x + go-sparkle | EdDSA 签名，appcast.xml feed，每小时检查 |

### 2.2 关键代码参考

#### main.go 模式

```go
package main

import (
    "embed"
    _ "github.com/abemedia/go-sparkle" // 可选：自动更新
    "github.com/wailsapp/wails/v2"
    "github.com/wailsapp/wails/v2/pkg/options"
    "github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:dist
var assets embed.FS

func main() {
    app := NewApp()
    err := wails.Run(&options.App{
        Title:     "AppName - Description",
        Width:     1440,
        Height:    900,
        MinWidth:  1024,
        MinHeight: 768,
        AssetServer: &assetserver.Options{
            Assets:  assets,
            Handler: app, // 可选：API 代理
        },
        OnStartup: app.startup,
        Bind: []interface{}{app},
    })
    if err != nil {
        println("Error:", err.Error())
    }
}
```

#### API 代理模式 (app.go)

```go
var backendURL = "http://default-backend.com" // ldflags 覆盖
const proxyTimeout = 300 * time.Second

type App struct {
    ctx    context.Context
    client *http.Client
}

func NewApp() *App {
    return &App{client: &http.Client{Timeout: proxyTimeout}}
}

func (a *App) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if !strings.HasPrefix(r.URL.Path, "/api/") {
        http.NotFound(w, r)
        return
    }
    targetURL := backendURL + r.URL.RequestURI()
    proxyReq, _ := http.NewRequestWithContext(r.Context(), r.Method, targetURL, r.Body)
    for key, values := range r.Header {
        for _, v := range values {
            proxyReq.Header.Add(key, v)
        }
    }
    resp, err := a.client.Do(proxyReq)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    for key, values := range resp.Header {
        for _, v := range values {
            w.Header().Add(key, v)
        }
    }
    w.WriteHeader(resp.StatusCode)
    io.Copy(w, resp.Body)
}
```

#### 外部链接拦截 (前端 JS)

```typescript
useEffect(() => {
    function handleClick(e: MouseEvent) {
        const anchor = (e.target as HTMLElement).closest('a')
        if (!anchor) return
        const href = anchor.getAttribute('href')
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) return
        if (href.startsWith('http://') || href.startsWith('https://')) {
            e.preventDefault()
            window.runtime?.BrowserOpenURL(href)
        }
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
}, [])
```

---

## 3. 三层架构

```
Layer 1: 工程壳 (Wails scaffold)
  ├─ main.go / app.go / wails.json
  ├─ API 代理层 (可选)
  ├─ 外部链接拦截
  └─ 环境变量注入 (ldflags)

Layer 2: 品牌设计 (icon + DMG background)
  ├─ App Icon 生成 (SVG → PNG → ICNS)
  │   └─ macOS icon 规范 + 多种风格模板
  ├─ DMG 背景生成 (SVG → HTML → PNG)
  │   └─ drop zone 坐标系 + 装饰模板 + 安装引导
  └─ 品牌配色提取 & 自动套用

Layer 3: 构建发布 (build + publish)
  ├─ build-dmg.sh (构建 + 签名 + DMG)
  ├─ publish-update.sh (Sparkle 签名 + CDN 上传)
  ├─ Info.plist 生成
  └─ CHANGELOG → appcast 转换
```

---

## 4. App Icon 设计规范

### 4.1 macOS Icon 规格

```
Canvas:           1024 × 1024
Safe area:        112px padding (each side)
Background rect:  x=112 y=112 width=800 height=800
Corner radius:    rx=179 ry=179 (≈ 22% of 800)
Icon content:     居中在 800×800 safe area 内
```

SVG 基础结构：

```xml
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="112" y1="112" x2="912" y2="912"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#COLOR1"/>
      <stop offset="100%" stop-color="#COLOR2"/>
    </linearGradient>
  </defs>
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179"
        fill="url(#bg)"/>
  <!-- icon content here, centered -->
</svg>
```

### 4.2 多尺寸输出

需要生成 .iconset 目录，包含以下尺寸：

```
icon_16x16.png      icon_16x16@2x.png
icon_32x32.png      icon_32x32@2x.png
icon_128x128.png    icon_128x128@2x.png
icon_256x256.png    icon_256x256@2x.png
icon_512x512.png    icon_512x512@2x.png
```

转换命令：`iconutil --convert icns AppIcon.iconset`

### 4.3 图标模板（预置 4 种）

**模板 A: 渐变 + 字母（Argus 风格）**
- 双色对角线性渐变背景
- 从应用名取首字母，白色粗线条
- 可在字母中嵌入装饰元素（如 Argus 的"眼睛"）
- 适合：开发工具、技术产品

**模板 B: 纯色 + 几何符号**
- 单色背景（品牌主色）
- 居中几何图形（圆环、三角、六边形、方块组合）
- 白色描边，无填充
- 适合：管理后台、数据工具

**模板 C: 深色 + 发光线条**
- 深灰到深蓝渐变背景
- 细线条图形 + 发光效果（用 filter: glow）
- 科技感强
- 适合：监控工具、调试器

**模板 D: 柔和渐变 + 扁平图标**
- 柔和双色渐变（粉蓝、橙黄等）
- 扁平化简单图形，填充白色
- 圆润友好
- 适合：日常工具、内部平台

### 4.4 Argus 图标实例

```xml
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="112" y1="112" x2="912" y2="912"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#334155"/>
      <stop offset="100%" stop-color="#0D9488"/>
    </linearGradient>
  </defs>
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179"
        fill="url(#bg)"/>
  <g transform="translate(512, 538) scale(19.5)" stroke="white" fill="none">
    <path d="M-10 8 L0 -14 L10 8" stroke-width="2.4"
          stroke-linecap="round" stroke-linejoin="round"/>
    <ellipse cx="0" cy="2" rx="5" ry="2.5" stroke-width="1.6"/>
    <circle cx="0" cy="2" r="1.5" fill="white" stroke="none"/>
  </g>
</svg>
```

---

## 5. DMG 背景设计规范

### 5.1 核心坐标系（最关键的隐性知识）

```
Canvas:        600 × 400 (--window-size 600 400)
Icon size:     72px (--icon-size 72)

App icon:      center (150, 185)  →  --icon "MyApp.app" 150 185
Apps folder:   center (450, 185)  →  --app-drop-link 450 185

SVG drop zone (留白区域，用于放置图标):
  Left:   rect x=110 y=149 width=80 height=72  (App 图标)
  Right:  rect x=410 y=149 width=80 height=72  (Applications)
```

create-dmg 完整命令：

```bash
create-dmg \
  --volname "AppName" \
  --background "build/dmg/background.png" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 72 \
  --icon "AppName.app" 150 185 \
  --app-drop-link 450 185 \
  "build/bin/AppName-VERSION-macOS.dmg" \
  "build/bin/AppName.app"
```

### 5.2 SVG → PNG 渲染管线

```
background.svg   纯 SVG，所有视觉元素
      │
      ▼
background.html  HTML 包装，加 <style> 确保字体渲染
      │
      ▼
background.png   浏览器截图或 rsvg-convert 转换 (2x @1200×800)
```

HTML 包装模板：

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;width:600px;height:400px;overflow:hidden}
body{font-family:"PingFang SC",-apple-system,sans-serif;
     -webkit-font-smoothing:antialiased}
</style></head><body>
  <!-- SVG content here -->
</body></html>
```

### 5.3 DMG 背景模板（预置 3 种）

**模板 A: 品牌展示（Argus 风格）**
- 顶部：品牌 tagline（PingFang SC 20px bold）
- 中心：可选吉祥物 / 产品 logo
- 两侧：装饰性元素（彩色节点、连接线等）
- 底部分割线 + 安装说明文字
- 整体淡雅渐变背景 (#EEF0FF → #F5EEFF)

**模板 B: 简约箭头**
- 纯色或渐变背景
- 左侧 App 图标 drop zone
- 中间大箭头 (→)
- 右侧 Applications drop zone
- 底部一行安装说明

**模板 C: 极简**
- 浅灰白背景
- 仅 drop zone 标记 + 应用名
- 底部安装说明
- 无装饰

### 5.4 底部安装引导文字

ad-hoc 签名的应用必须加这段引导：

```
首次打开：右键点击 [AppName] → 选择「打开」→ 弹窗点「打开」
仅第一次需要，之后正常双击即可
```

### 5.5 Argus DMG 背景实例

见 Argus 仓库 `build/dmg/background.svg`，包含：
- 渐变背景 (#EEF0FF → #F5EEFF)
- 中心可爱机器人 SVG 插画
- 两侧 DAG 节点装饰（蓝/绿/紫/粉色小药丸）
- 连接线箭头
- drop zone 预留白色圆角矩形
- 品牌 tagline "看见 Agent 每一步推理"
- 底部安装说明

---

## 6. 构建脚本知识

### 6.1 build-dmg.sh 核心流程

```
1. 从 package.json 读取版本号 (单一来源)
2. 同步版本到 wails.json
3. 从 .env.production 读取 VITE_API_BASE
4. CGO_LDFLAGS 设置 rpath (Sparkle.framework 查找路径)
5. wails build -clean -ldflags "-X 'main.backendURL=...'"
6. 复制 Sparkle.framework 到 .app/Contents/Frameworks/
7. 逐组件 codesign (XPC services → Autoupdate → Updater.app → framework → .app)
8. create-dmg 制作 DMG
9. ditto -c -k 制作 ZIP (Sparkle 更新用)
```

签名顺序（极其重要，顺序错会失败）：

```
XPC services (逐个) → Autoupdate binary → Updater.app →
Sparkle.framework 本体 → 整个 .app bundle (--deep)
```

### 6.2 publish-update.sh 核心流程

```
1. 验证前置条件 (ZIP 存在、sign_update 可用、ossutil 配置)
2. EdDSA 签名 ZIP → 获取 signature + length
3. 从 CHANGELOG.md 提取当前版本条目 → 转 HTML <li>
4. 生成/更新 appcast.xml (新 item 插入 </channel> 前)
5. ossutil 上传: ZIP → releases/, appcast.xml → 根, DMG → releases/
```

### 6.3 Info.plist 关键配置

```xml
<!-- 多语言 -->
<key>CFBundleDevelopmentRegion</key>
<string>zh_CN</string>
<key>CFBundleLocalizations</key>
<array><string>zh_CN</string><string>zh-Hans</string><string>en</string></array>

<!-- 允许 HTTP (内网 API) -->
<key>NSAppTransportSecurity</key>
<dict><key>NSAllowsArbitraryLoads</key><true/></dict>

<!-- Sparkle 自动更新 (可选) -->
<key>SUFeedURL</key>
<string>https://cdn.example.com/appcast.xml</string>
<key>SUPublicEDKey</key>
<string>YOUR_PUBLIC_KEY</string>
<key>SUEnableAutomaticChecks</key>
<true/>
<key>SUScheduledCheckInterval</key>
<integer>3600</integer>
```

---

## 7. SKILL.md 设计规划

### 7.1 调用方式

```
/desktop-kit              → 完整向导（推荐）
/desktop-kit init         → 仅生成 Wails 壳代码
/desktop-kit icon         → 仅生成应用图标
/desktop-kit dmg-bg       → 仅生成 DMG 背景
/desktop-kit update       → 添加 Sparkle 自动更新支持
/desktop-kit doctor       → 环境检测 + 问题诊断
```

### 7.2 Agent 工作流

```
Phase 1: 项目检测
  1. 运行 scripts/detect-project.sh
  2. 识别前端框架 (React/Vue/Svelte/静态)
  3. 识别构建工具 (Vite/Webpack/None)
  4. 扫描 API 调用模式 (fetch/axios baseURL)
  5. 读取 package.json (名称、版本)

Phase 2: 交互确认
  询问用户：
  - 应用名称（默认从 package.json.name）
  - 是否需要 API 代理（检测到 API 调用时推荐）
  - API 路径前缀（默认从检测结果）
  - 是否需要 Sparkle 自动更新
  - 图标风格偏好（渐变字母 / 纯色几何 / 深色发光 / 柔和扁平）
  - DMG 背景风格（品牌展示 / 简约箭头 / 极简）
  - 品牌主色调（可从项目 CSS/tailwind.config 提取）

Phase 3: 代码生成
  读取 references/ 中的知识文档，生成：
  a. Wails 壳: main.go + app.go + wails.json
  b. 前端补丁: 外部链接拦截代码片段
  c. 图标: build/appicon.svg → build/appicon.png
  d. DMG 背景: build/dmg/background.svg + background.html
  e. 构建脚本: scripts/build-dmg.sh
  f. plist: build/darwin/Info.plist
  g. (可选) 发布脚本: scripts/publish-update.sh
  h. (可选) go.mod + go.sum

Phase 4: 后续指引
  输出：
  - 环境依赖清单 (Go, Wails CLI, create-dmg, Sparkle.framework)
  - 构建命令
  - SVG → PNG → ICNS 转换命令
  - 首次构建注意事项
```

### 7.3 Agent 能做 vs 不能做

| 能做 | 不能做 |
|------|--------|
| 扫描项目结构，识别框架 | 安装 Go / Wails CLI |
| 生成 main.go / app.go / wails.json | 下载 Sparkle.framework |
| 生成构建脚本 / 发布脚本 | 配置 CDN / OSS 凭证 |
| 生成应用图标 SVG + PNG | Apple Developer 证书签名 |
| 生成 DMG 背景 SVG + HTML | 执行 wails build（可生成命令） |
| 检测 API 调用模式 | 实际网络请求测试 |
| 诊断构建错误 | — |

---

## 8. 仓库文件结构规划

```
xkcoding-skills/
├── .claude-plugin/
│   └── marketplace.json
├── .gitignore
├── README.md
├── LICENSE
│
└── desktop-kit/
    ├── SKILL.md                         # 主入口 + 工作流 + 决策树
    ├── DESIGN.md                        # 本文档（设计参考，不随 Skill 分发）
    │
    ├── scripts/
    │   ├── detect-project.sh            # 项目检测：框架、构建工具、API 模式
    │   ├── svg-to-icns.sh               # SVG → 多尺寸 PNG → .icns
    │   └── svg-to-png.sh               # SVG → PNG (sips/rsvg-convert)
    │
    └── references/
        ├── wails-scaffold.md            # Wails 壳代码生成知识
        ├── api-proxy.md                 # Go 反向代理模式 + 超时配置
        ├── external-links.md            # 外部链接拦截代码片段
        ├── info-plist.md                # Info.plist 配置知识
        ├── icon-spec.md                 # macOS 图标设计规范（尺寸、圆角、safe area）
        ├── icon-templates.md            # 4 种图标 SVG 模板（含完整代码）
        ├── dmg-background-spec.md       # DMG 背景规范（坐标系、drop zone、create-dmg 参数）
        ├── dmg-templates.md             # 3 种 DMG 背景 SVG 模板（含完整代码）
        ├── build-scripts.md             # 构建脚本知识（版本同步、codesign 顺序、DMG 制作）
        ├── publish-scripts.md           # 发布脚本知识（EdDSA 签名、appcast、CDN 上传）
        ├── sparkle-update.md            # Sparkle 集成指南（go-sparkle、Info.plist keys）
        ├── changelog-pattern.md         # CHANGELOG.md → appcast.xml description 转换
        ├── prerequisites.md             # 环境依赖清单（Go、Wails、create-dmg、Sparkle）
        └── troubleshooting.md           # 常见问题排查
```

---

## 9. 设计决策记录

### 9.1 知识驱动 vs 模板驱动

**决策**：混合模式。

- **图标 + DMG 背景**：预置 SVG 模板，Agent 参数化替换（颜色、文字、图形）。模板确保坐标系正确，Agent 负责创意部分。
- **Wails 壳代码**：知识驱动。references/ 里写清楚模式和注意事项，Agent 根据项目上下文现场生成代码。因为壳代码需要适配不同项目（API 前缀不同、是否需要代理、是否需要更新）。
- **构建脚本**：知识驱动。脚本需要根据项目具体配置定制化生成。

### 9.2 为什么选 Wails 而不是 Tauri/Electron

Skill 初版绑定 Wails v2，原因：
- Argus 实战验证过，所有坑都踩过
- Go 技术栈在小红书内部更通用
- 二进制体积小 (~15MB vs Electron ~100MB+)
- 未来可扩展支持 Tauri（加一组 references）

### 9.3 图标生成方式

**决策**：Agent 直接生成 SVG 代码（模板 + 创意）。

理由：
- Argus 的 appicon.svg 就是手写 SVG，证明 SVG 质量足够
- 零外部依赖
- 模板保证 macOS 规范正确，Agent 在模板内发挥创意
- 未来可以对接 baoyu-image-gen 等 AI 图像生成 Skill 提供高级选项

### 9.4 DMG 背景坐标对齐

这是最容易踩坑的地方。SVG 中 drop zone 的坐标必须和 create-dmg 的参数精确对齐：

```
create-dmg --icon "App.app" 150 185  →  SVG 中 left drop zone center = (150, 185)
create-dmg --app-drop-link 450 185   →  SVG 中 right drop zone center = (450, 185)
```

模板中硬编码这些坐标，Agent 不应修改 drop zone 位置，只修改装饰元素。

---

## 10. 实现优先级

```
P0 (MVP - 最小可用):
  ├─ SKILL.md (完整工作流)
  ├─ references/wails-scaffold.md
  ├─ references/api-proxy.md
  ├─ references/icon-spec.md
  ├─ references/icon-templates.md (至少 2 种)
  ├─ references/dmg-background-spec.md
  ├─ references/dmg-templates.md (至少 1 种)
  ├─ references/build-scripts.md
  ├─ scripts/detect-project.sh
  └─ scripts/svg-to-icns.sh

P1 (完善):
  ├─ references/sparkle-update.md
  ├─ references/publish-scripts.md
  ├─ references/external-links.md
  ├─ references/info-plist.md
  ├─ references/troubleshooting.md
  ├─ references/prerequisites.md
  └─ 更多图标/DMG 模板

P2 (增强):
  ├─ references/changelog-pattern.md
  ├─ scripts/svg-to-png.sh
  └─ 支持更多前端框架检测
```

---

## 11. 相关项目参考

- **Argus 仓库**：`/Users/yangkai.shen/code/xiaohongshu/argus` — 所有知识的实战来源
- **baoyu-skills**：`github.com/jimliu/baoyu-skills` — Skill 结构和 marketplace.json 参考
- **tchen-skills**：`github.com/tyrchen/claude-skills` — 另一种 Skill 组织方式参考
- **Wails v2 文档**：https://wails.io/docs/introduction
- **Sparkle 文档**：https://sparkle-project.org/documentation/
- **create-dmg**：https://github.com/create-dmg/create-dmg
