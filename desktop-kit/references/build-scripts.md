# 构建脚本生成知识

> Agent 根据本文档生成 `scripts/build-dmg.sh`，覆盖从版本同步到 DMG 制作的完整流程。

## build-dmg.sh 核心流程

```
1. 前置检查 (go, wails, create-dmg)
2. 从 package.json 读取版本号 (单一来源)
3. 同步版本到 wails.json
4. (可选) 从 .env.production 读取后端 URL
5. wails build -clean [-ldflags "-X 'main.backendURL=...'"]
6. ad-hoc codesign
7. create-dmg 制作 DMG
```

## 脚本模板

```bash
#!/usr/bin/env bash
# build-dmg.sh — 构建 macOS 桌面应用 + DMG
set -euo pipefail

APP_NAME="{{APP_NAME}}"

# ── 前置检查 ──────────────────────────────────────────────────────────────────

check_tool() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌ 缺少依赖: $1"
    echo "   安装方式: $2"
    exit 1
  fi
}

check_tool "go" "https://go.dev/dl/"
check_tool "wails" "go install github.com/wailsapp/wails/v2/cmd/wails@latest"
check_tool "create-dmg" "brew install create-dmg"

# ── 版本同步 ──────────────────────────────────────────────────────────────────

VERSION=$(python3 -c "import json; print(json.load(open('package.json'))['version'])")
echo "📦 版本: $VERSION"

# 同步到 wails.json
python3 -c "
import json
with open('wails.json', 'r+') as f:
    cfg = json.load(f)
    cfg['version'] = '$VERSION'
    f.seek(0)
    json.dump(cfg, f, indent=2)
    f.truncate()
"

# ── 构建 ──────────────────────────────────────────────────────────────────────

LDFLAGS=""

# 读取后端 URL (如果存在)
if [[ -f .env.production ]]; then
  BACKEND_URL=$(grep -E '^(VITE_API_BASE|REACT_APP_API_URL|BACKEND_URL)=' .env.production | head -1 | cut -d'=' -f2- || true)
  if [[ -n "$BACKEND_URL" ]]; then
    LDFLAGS="-X 'main.backendURL=$BACKEND_URL'"
    echo "🔗 后端 URL: $BACKEND_URL"
  fi
fi

echo "🔨 开始构建..."
if [[ -n "$LDFLAGS" ]]; then
  wails build -clean -ldflags "$LDFLAGS"
else
  wails build -clean
fi

# ── 签名 ──────────────────────────────────────────────────────────────────────

APP_PATH="build/bin/${APP_NAME}.app"
echo "🔐 Ad-hoc 签名..."
codesign --deep --force -s - "$APP_PATH"

# ── DMG ───────────────────────────────────────────────────────────────────────

DMG_OUTPUT="build/bin/${APP_NAME}-${VERSION}-macOS.dmg"
echo "💿 制作 DMG..."

# 删除已存在的 DMG (create-dmg 不会覆盖)
rm -f "$DMG_OUTPUT"

create-dmg \
  --volname "$APP_NAME" \
  --background "build/dmg/background.png" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 72 \
  --icon "${APP_NAME}.app" 150 185 \
  --app-drop-link 450 185 \
  "$DMG_OUTPUT" \
  "$APP_PATH"

echo ""
echo "✅ 构建完成!"
echo "   App: $APP_PATH"
echo "   DMG: $DMG_OUTPUT"
```

## 关键要点

### 版本同步
- `package.json` 是唯一的版本来源
- 构建脚本自动同步到 `wails.json`
- DMG 文件名包含版本号

### ldflags 注入
- 仅当项目使用 API 代理时需要
- 从 `.env.production` 读取环境变量
- 支持多种环境变量命名（VITE_API_BASE、REACT_APP_API_URL 等）

### ad-hoc 签名
- `codesign --deep --force -s -` 使用 ad-hoc 签名
- `--deep` 递归签名所有嵌套的框架和二进制
- ad-hoc 签名的应用首次打开需要右键 → 打开

### create-dmg 参数
- `--background` 指向 PNG 背景图（不是 SVG）
- `--icon` 和 `--app-drop-link` 坐标必须与 SVG 模板中的 drop zone 对齐
- 运行前必须删除已存在的 DMG 文件

## Agent 生成指引

1. 替换 `{{APP_NAME}}` 为实际应用名
2. 根据是否需要 API 代理决定 ldflags 部分
3. 如果用户没有 `.env.production`，移除后端 URL 读取部分
4. 确保 `build/dmg/background.png` 已生成再运行
5. 生成后设置可执行权限: `chmod +x scripts/build-dmg.sh`
