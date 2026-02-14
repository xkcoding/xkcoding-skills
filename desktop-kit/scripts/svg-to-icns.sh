#!/usr/bin/env bash
# svg-to-icns.sh — SVG → 多尺寸 PNG iconset → macOS ICNS
# 用法: svg-to-icns.sh <input.svg> [output-dir]
# 依赖: rsvg-convert (推荐) 或 sips (macOS 内置 fallback)

set -euo pipefail

# ── 参数检查 ──────────────────────────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
  echo "用法: svg-to-icns.sh <input.svg> [output-dir]"
  echo "示例: svg-to-icns.sh build/appicon.svg build/"
  exit 1
fi

INPUT_SVG="$1"
OUTPUT_DIR="${2:-.}"

if [[ ! -f "$INPUT_SVG" ]]; then
  echo "错误: 文件不存在: $INPUT_SVG"
  exit 1
fi

# ── 工具检测 ──────────────────────────────────────────────────────────────────

RENDER_TOOL=""

if command -v rsvg-convert &>/dev/null; then
  RENDER_TOOL="rsvg-convert"
elif command -v sips &>/dev/null; then
  RENDER_TOOL="sips"
  echo "⚠️  使用 sips fallback，SVG 渲染质量可能不如 rsvg-convert"
  echo "   推荐安装: brew install librsvg"
else
  echo "错误: 需要 rsvg-convert 或 sips"
  echo "  安装 rsvg-convert: brew install librsvg"
  echo "  sips 是 macOS 内置工具，应该可用"
  exit 1
fi

if ! command -v iconutil &>/dev/null; then
  echo "错误: iconutil 不可用（需要 macOS 系统）"
  exit 1
fi

# ── 创建 iconset 目录 ─────────────────────────────────────────────────────────

ICONSET_DIR="$OUTPUT_DIR/AppIcon.iconset"
mkdir -p "$ICONSET_DIR"

# iconset 尺寸配置: "文件名 宽度"
SIZES=(
  "icon_16x16.png 16"
  "icon_16x16@2x.png 32"
  "icon_32x32.png 32"
  "icon_32x32@2x.png 64"
  "icon_128x128.png 128"
  "icon_128x128@2x.png 256"
  "icon_256x256.png 256"
  "icon_256x256@2x.png 512"
  "icon_512x512.png 512"
  "icon_512x512@2x.png 1024"
)

# ── SVG → PNG 转换 ───────────────────────────────────────────────────────────

svg_to_png() {
  local input="$1" output="$2" size="$3"

  if [[ "$RENDER_TOOL" == "rsvg-convert" ]]; then
    rsvg-convert -w "$size" -h "$size" "$input" -o "$output"
  else
    # sips: 先复制 SVG 内容到临时 PNG（需要先转为 1024 PNG，再缩放）
    local tmp_png
    tmp_png=$(mktemp /tmp/icon_XXXXX.png)

    # sips 不能直接转 SVG，用 qlmanage 生成预览图
    if command -v qlmanage &>/dev/null; then
      qlmanage -t -s 1024 -o /tmp "$input" &>/dev/null
      local ql_output="/tmp/$(basename "$input").png"
      if [[ -f "$ql_output" ]]; then
        sips -z "$size" "$size" "$ql_output" --out "$output" &>/dev/null
        rm -f "$ql_output"
      fi
    fi

    rm -f "$tmp_png"
  fi
}

echo "🔄 正在生成 iconset..."

for entry in "${SIZES[@]}"; do
  filename="${entry% *}"
  size="${entry#* }"
  echo "  ${filename} (${size}x${size})"
  svg_to_png "$INPUT_SVG" "$ICONSET_DIR/$filename" "$size"
done

# ── PNG iconset → ICNS ────────────────────────────────────────────────────────

ICNS_OUTPUT="$OUTPUT_DIR/appicon.icns"
echo "🔄 正在生成 ICNS..."
iconutil --convert icns "$ICONSET_DIR" -o "$ICNS_OUTPUT"

echo "✅ 完成: $ICNS_OUTPUT"
echo ""
echo "📁 产出文件:"
echo "   $ICONSET_DIR/  (多尺寸 PNG)"
echo "   $ICNS_OUTPUT   (macOS 图标)"
