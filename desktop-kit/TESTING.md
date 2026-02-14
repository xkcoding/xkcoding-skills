# Desktop Kit 测试流程

## 前置条件

### 环境依赖

| 工具 | 用途 | 安装方式 | 必需？ |
|------|------|---------|--------|
| Claude Code | Skill 运行环境 | `npm install -g @anthropic-ai/claude-code` | 是 |
| Python 3 | detect-project.sh JSON 解析 | macOS 自带 | 是 |
| rsvg-convert | SVG → PNG 渲染（推荐） | `brew install librsvg` | 推荐 |
| iconutil | PNG → ICNS 转换 | macOS 自带 | 是 |
| Go 1.21+ | Wails 构建（端到端测试需要） | https://go.dev/dl/ | 可选 |
| Wails CLI v2 | 桌面应用构建 | `go install github.com/wailsapp/wails/v2/cmd/wails@latest` | 可选 |
| create-dmg | DMG 制作 | `brew install create-dmg` | 可选 |

### 快速检测

```bash
# 运行 desktop-kit doctor 一键检测（安装 Skill 后可用）
# 或手动检测：
command -v python3 && echo "✅ python3" || echo "❌ python3"
command -v rsvg-convert && echo "✅ rsvg-convert" || echo "❌ rsvg-convert"
command -v iconutil && echo "✅ iconutil" || echo "❌ iconutil"
command -v go && echo "✅ go" || echo "❌ go"
command -v wails && echo "✅ wails" || echo "❌ wails"
command -v create-dmg && echo "✅ create-dmg" || echo "❌ create-dmg"
```

---

## 第一步：安装 Skill

### 方式 A：全局安装（推荐，所有项目可用）

```bash
# 克隆仓库
git clone https://github.com/xkcoding/xkcoding-skills.git ~/xkcoding-skills

# 复制 desktop-kit 到 Claude Code 全局 skills 目录
mkdir -p ~/.claude/skills
cp -r ~/xkcoding-skills/desktop-kit ~/.claude/skills/desktop-kit
```

### 方式 B：项目级安装（仅当前项目可用）

```bash
# 在你的 Web 项目根目录下
cd /path/to/your-web-project

# 复制 desktop-kit 到项目的 .claude/skills/
mkdir -p .claude/skills
cp -r /path/to/xkcoding-skills/desktop-kit .claude/skills/desktop-kit
```

### 方式 C：本地开发（直接在 skills 仓库内测试）

```bash
# 如果你就是 xkcoding-skills 的开发者，可以创建符号链接
ln -s /Users/yangkai.shen/code/xkcoding/xkcoding-skills/desktop-kit ~/.claude/skills/desktop-kit
```

### 验证安装

```bash
# 启动新的 Claude Code 会话
claude

# 在对话中输入，看 /desktop-kit 是否出现在可用 skills 列表中
/desktop-kit doctor
```

如果 `/desktop-kit` 出现在自动补全列表中，说明安装成功。

---

## 第二步：脚本单元测试

脚本测试不需要安装 Skill，直接运行即可。

### 2.1 创建 Mock 项目

```bash
# 创建一个最小的 React + Vite 项目骨架
mkdir -p /tmp/mock-web-app/src

# package.json
cat > /tmp/mock-web-app/package.json << 'EOF'
{
  "name": "mock-admin-panel",
  "version": "0.1.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "vite": "^5.0.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  }
}
EOF

# 模拟 API 调用的源码
cat > /tmp/mock-web-app/src/api.ts << 'EOF'
export async function fetchData() {
  const res = await fetch("/api/v1/data")
  return res.json()
}
EOF

# 模拟 .env.production
echo 'VITE_API_BASE=https://api.example.com' > /tmp/mock-web-app/.env.production

# vite 配置
cat > /tmp/mock-web-app/vite.config.ts << 'EOF'
import { defineConfig } from 'vite'
export default defineConfig({})
EOF
```

### 2.2 测试 detect-project.sh

```bash
DETECT="./desktop-kit/scripts/detect-project.sh"

# ✅ 测试 1: 正常检测 React + Vite + API 代理
$DETECT /tmp/mock-web-app
# 期望输出:
# {
#   "appName": "mock-admin-panel",
#   "appVersion": "0.1.0",
#   "framework": "react",
#   "frameworkConfidence": "high",
#   "buildTool": "vite",
#   "apiProxy": true,
#   "apiEnvVar": "VITE_API_BASE",
#   "apiEnvValue": "https://api.example.com"
# }

# ✅ 测试 2: 无 package.json 的错误处理
$DETECT /tmp
echo "Exit code: $?"
# 期望: JSON error + exit code 1

# ✅ 测试 3: 源码 API 模式检测（移除 .env 后从源码扫描）
mv /tmp/mock-web-app/.env.production /tmp/mock-web-app/.env.production.bak
$DETECT /tmp/mock-web-app
# 期望: apiProxy=true, apiPrefix="/api/"
mv /tmp/mock-web-app/.env.production.bak /tmp/mock-web-app/.env.production

# ✅ 测试 4: Vue 项目检测
cat > /tmp/mock-web-app/package.json << 'EOF'
{"name":"vue-app","version":"1.0.0","dependencies":{"vue":"^3.3.0"},"devDependencies":{"vite":"^5.0.0"}}
EOF
$DETECT /tmp/mock-web-app
# 期望: framework="vue"
```

### 2.3 测试 svg-to-icns.sh

```bash
ICNS="./desktop-kit/scripts/svg-to-icns.sh"

# 生成测试 SVG
cat > /tmp/test-icon.svg << 'EOF'
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179" fill="#334155"/>
  <text x="512" y="560" text-anchor="middle" dominant-baseline="central"
        font-family="-apple-system" font-size="420" font-weight="700" fill="white">T</text>
</svg>
EOF

# ✅ 测试 5: SVG → ICNS 完整流程
$ICNS /tmp/test-icon.svg /tmp/
# 期望: 生成 /tmp/AppIcon.iconset/ (10 个 PNG) + /tmp/appicon.icns

# 验证产出
ls -la /tmp/appicon.icns          # 应该存在且大小 > 0
ls /tmp/AppIcon.iconset/ | wc -l  # 应该是 10 个文件

# ✅ 测试 6: 缺少输入文件的错误处理
$ICNS /tmp/nonexistent.svg /tmp/
echo "Exit code: $?"
# 期望: 错误信息 + exit code 1
```

---

## 第三步：端到端 Skill 测试

这一步测试完整的 `/desktop-kit` Agent 工作流。需要先完成 Skill 安装（第一步）。

### 3.1 准备测试项目

使用第二步创建的 mock 项目，或任意真实 Web 项目。

```bash
# 恢复为 React 项目（如果之前改成了 Vue 测试）
cat > /tmp/mock-web-app/package.json << 'EOF'
{
  "name": "mock-admin-panel",
  "version": "0.1.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "vite": "^5.0.0"
  }
}
EOF
```

### 3.2 完整向导测试

```bash
# 在 mock 项目目录下启动 Claude Code
cd /tmp/mock-web-app
claude

# 在对话中输入：
/desktop-kit
```

**验证 Phase 1（项目检测）：**
- [ ] Agent 是否运行了 detect-project.sh
- [ ] 是否正确展示了检测摘要（React, Vite, API 代理）

**验证 Phase 2（交互确认）：**
- [ ] 是否询问了应用名称
- [ ] 是否询问了 API 代理配置
- [ ] 是否询问了图标风格（渐变字母 / 纯色几何）
- [ ] 是否询问了品牌色
- [ ] 是否询问了 DMG 背景风格

**验证 Phase 3（代码生成）：**
- [ ] 是否生成了 `main.go`（包含 embed dist、Wails options）
- [ ] 是否生成了 `app.go`（包含 ServeHTTP 代理）
- [ ] 是否生成了 `wails.json`（Vite 构建命令）
- [ ] 是否提示了外部链接拦截代码片段
- [ ] 是否生成了 `build/appicon.svg`
- [ ] 是否生成了 `build/dmg/background.svg` + `background.html`
- [ ] 是否生成了 `scripts/build-dmg.sh`
- [ ] 是否生成了 `build/darwin/Info.plist`

**验证 Phase 4（后续指引）：**
- [ ] 是否列出了环境依赖清单
- [ ] 是否给出了图标转换命令
- [ ] 是否给出了 DMG 背景转换命令
- [ ] 是否给出了构建命令
- [ ] 是否给出了首次构建注意事项

### 3.3 子命令测试

```bash
# 仅生成图标
/desktop-kit icon
# 验证: 只询问图标相关问题，只生成 build/appicon.svg

# 仅生成 DMG 背景
/desktop-kit dmg-bg
# 验证: 只询问 DMG 相关问题，只生成 build/dmg/ 下的文件

# 仅生成 Wails 壳代码
/desktop-kit init
# 验证: 运行检测 → 询问 Wails 相关问题 → 只生成 Go 文件

# 环境诊断
/desktop-kit doctor
# 验证: 检测所有依赖工具并报告状态
```

---

## 第四步：生成文件验证

如果跑了完整向导（3.2），验证生成的文件内容。

### 4.1 检查文件结构

```bash
# 在 mock 项目目录下
find . -name "*.go" -o -name "wails.json" -o -name "*.svg" -o -name "*.sh" -o -name "Info.plist" | sort
# 期望:
# ./build/appicon.svg
# ./build/darwin/Info.plist
# ./build/dmg/background.html
# ./build/dmg/background.svg
# ./main.go
# ./app.go
# ./wails.json
# ./scripts/build-dmg.sh
```

### 4.2 检查生成内容

```bash
# main.go 应包含 embed 和 Wails 配置
grep -q "//go:embed all:dist" main.go && echo "✅ embed" || echo "❌ embed"
grep -q "AssetServer" main.go && echo "✅ AssetServer" || echo "❌ AssetServer"

# app.go 应包含代理（如果选了 API 代理）
grep -q "ServeHTTP" app.go && echo "✅ ServeHTTP proxy" || echo "❌ no proxy"
grep -q "300" app.go && echo "✅ 300s timeout" || echo "❌ timeout"

# wails.json 应包含正确的前端构建命令
grep -q "npm run build" wails.json && echo "✅ build cmd" || echo "❌ build cmd"

# SVG 图标应符合 macOS 规范
grep -q 'width="1024"' build/appicon.svg && echo "✅ icon 1024" || echo "❌ icon size"
grep -q 'rx="179"' build/appicon.svg && echo "✅ corner radius" || echo "❌ corner radius"

# DMG 背景坐标应正确
grep -q '600' build/dmg/background.svg && echo "✅ DMG 600px" || echo "❌ DMG width"

# Info.plist 应有多语言配置
grep -q "zh_CN" build/darwin/Info.plist && echo "✅ zh_CN" || echo "❌ locale"
grep -q "NSAllowsArbitraryLoads" build/darwin/Info.plist && echo "✅ ATS" || echo "❌ ATS"

# build-dmg.sh 应有前置检查
grep -q "check_tool" scripts/build-dmg.sh && echo "✅ prereq check" || echo "❌ prereq"
```

### 4.3 图标构建验证（可选，需要 rsvg-convert）

```bash
# 用 svg-to-icns.sh 将生成的图标转为 ICNS
~/.claude/skills/desktop-kit/scripts/svg-to-icns.sh build/appicon.svg build/
ls -la build/appicon.icns  # 应该存在且 > 100KB
```

---

## 第五步：清理

```bash
# 删除 mock 项目
rm -rf /tmp/mock-web-app

# 删除测试产出
rm -f /tmp/test-icon.svg /tmp/appicon.icns
rm -rf /tmp/AppIcon.iconset
```

---

## 测试 Checklist 速查表

### 脚本测试（5 分钟）

- [ ] detect-project.sh 正确检测 React 项目
- [ ] detect-project.sh 正确检测 Vite 构建工具
- [ ] detect-project.sh 从 .env 检测 API URL
- [ ] detect-project.sh 从源码检测 /api/ 模式
- [ ] detect-project.sh 无 package.json 时报错退出
- [ ] svg-to-icns.sh 生成完整 iconset（10 个 PNG）
- [ ] svg-to-icns.sh 生成有效 .icns 文件

### Skill 端到端测试（15 分钟）

- [ ] `/desktop-kit` 完整四阶段流程正常
- [ ] `/desktop-kit init` 仅生成 Wails 壳代码
- [ ] `/desktop-kit icon` 仅生成图标 SVG
- [ ] `/desktop-kit dmg-bg` 仅生成 DMG 背景
- [ ] `/desktop-kit doctor` 正确报告环境依赖

### 生成文件验证（5 分钟）

- [ ] main.go 包含 embed 和 Wails 配置
- [ ] app.go 包含 API 代理（如适用）
- [ ] wails.json 前端构建命令正确
- [ ] SVG 图标符合 1024x1024 / rx=179 规范
- [ ] DMG 背景 drop zone 坐标正确（150,185 / 450,185）
- [ ] Info.plist 多语言和 ATS 配置正确
- [ ] build-dmg.sh 包含前置检查和完整构建流程
