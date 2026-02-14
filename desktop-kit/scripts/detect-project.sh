#!/usr/bin/env bash
# detect-project.sh — 检测 Web 项目的框架、构建工具和 API 调用模式
# 用法: detect-project.sh [project-dir]
# 输出: JSON 到 stdout

set -euo pipefail

PROJECT_DIR="${1:-.}"

# ── 错误处理 ──────────────────────────────────────────────────────────────────

if [[ ! -f "$PROJECT_DIR/package.json" ]]; then
  echo '{"error":"no package.json found","path":"'"$PROJECT_DIR"'"}'
  exit 1
fi

# ── 读取 package.json ─────────────────────────────────────────────────────────

PKG="$PROJECT_DIR/package.json"

app_name=$(python3 -c "import json; print(json.load(open('$PKG')).get('name','unknown'))" 2>/dev/null || echo "unknown")
app_version=$(python3 -c "import json; print(json.load(open('$PKG')).get('version','0.0.0'))" 2>/dev/null || echo "0.0.0")

# 合并 dependencies + devDependencies 的 key 列表
all_deps=$(python3 -c "
import json
pkg = json.load(open('$PKG'))
deps = list(pkg.get('dependencies', {}).keys()) + list(pkg.get('devDependencies', {}).keys())
print('\n'.join(deps))
" 2>/dev/null || echo "")

# ── 1. 框架检测 ───────────────────────────────────────────────────────────────

framework="unknown"
framework_confidence="low"

if echo "$all_deps" | grep -qx "react\|react-dom"; then
  framework="react"
  framework_confidence="high"
elif echo "$all_deps" | grep -qx "vue"; then
  framework="vue"
  framework_confidence="high"
elif echo "$all_deps" | grep -qx "svelte"; then
  framework="svelte"
  framework_confidence="high"
elif [[ -f "$PROJECT_DIR/index.html" ]] || [[ -f "$PROJECT_DIR/public/index.html" ]]; then
  framework="static"
  framework_confidence="medium"
fi

# ── 2. 构建工具检测 ───────────────────────────────────────────────────────────

build_tool="none"

if echo "$all_deps" | grep -qx "vite"; then
  build_tool="vite"
elif ls "$PROJECT_DIR"/vite.config.* &>/dev/null; then
  build_tool="vite"
elif echo "$all_deps" | grep -qx "webpack"; then
  build_tool="webpack"
elif ls "$PROJECT_DIR"/webpack.config.* &>/dev/null; then
  build_tool="webpack"
fi

# ── 3. API 调用模式检测 ───────────────────────────────────────────────────────

api_proxy="false"
api_prefix=""
api_env_var=""
api_env_value=""

# 扫描 .env / .env.production 中的 API URL 环境变量
for env_file in "$PROJECT_DIR/.env" "$PROJECT_DIR/.env.production" "$PROJECT_DIR/.env.local"; do
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key value; do
      # 跳过注释和空行
      [[ "$key" =~ ^[[:space:]]*# ]] && continue
      [[ -z "$key" ]] && continue
      # 匹配 VITE_API_BASE, REACT_APP_API_URL 等模式
      if [[ "$key" =~ (API_BASE|API_URL|BACKEND_URL|API_HOST) ]]; then
        api_proxy="true"
        api_env_var="$key"
        api_env_value="$value"
        break 2
      fi
    done < "$env_file"
  fi
done

# 扫描源码中的 API 路径模式 (fetch/axios)
if [[ "$api_proxy" == "false" ]]; then
  src_dirs=("$PROJECT_DIR/src" "$PROJECT_DIR/app" "$PROJECT_DIR/pages" "$PROJECT_DIR/lib")
  for src_dir in "${src_dirs[@]}"; do
    if [[ -d "$src_dir" ]]; then
      # 检测 fetch("/api/ 或 baseURL: "/api/ 等模式
      if grep -rql '"/api/' "$src_dir" 2>/dev/null || \
         grep -rql "'/api/" "$src_dir" 2>/dev/null; then
        api_proxy="true"
        api_prefix="/api/"
        break
      fi
    fi
  done
fi

# ── 输出 JSON ─────────────────────────────────────────────────────────────────

cat <<EOF
{
  "appName": "$app_name",
  "appVersion": "$app_version",
  "framework": "$framework",
  "frameworkConfidence": "$framework_confidence",
  "buildTool": "$build_tool",
  "apiProxy": $api_proxy,
  "apiPrefix": "$api_prefix",
  "apiEnvVar": "$api_env_var",
  "apiEnvValue": "$api_env_value"
}
EOF
