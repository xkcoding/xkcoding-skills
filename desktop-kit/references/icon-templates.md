# 图标 SVG 模板

> Agent 选择模板后，替换颜色和内容参数生成最终图标。

## Template A: 渐变 + 字母

适合：开发工具、技术产品。从应用名取首字母，白色粗线条，对角线性渐变背景。

**参数：**
- `{{COLOR_1}}` — 渐变起始色（左上）
- `{{COLOR_2}}` — 渐变结束色（右下）
- `{{LETTER}}` — 应用名首字母（大写）

```xml
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="112" y1="112" x2="912" y2="912"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{{COLOR_1}}"/>
      <stop offset="100%" stop-color="{{COLOR_2}}"/>
    </linearGradient>
  </defs>
  <!-- 圆角矩形背景 -->
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179"
        fill="url(#bg)"/>
  <!-- 首字母 -->
  <text x="512" y="560" text-anchor="middle" dominant-baseline="central"
        font-family="-apple-system, 'SF Pro Display', 'Helvetica Neue', sans-serif"
        font-size="420" font-weight="700" fill="white"
        letter-spacing="-10">
    {{LETTER}}
  </text>
</svg>
```

**推荐配色：**

| 风格 | COLOR_1 | COLOR_2 |
|------|---------|---------|
| 石板青（Argus 风格） | `#334155` | `#0D9488` |
| 靛蓝紫 | `#4F46E5` | `#7C3AED` |
| 深蓝 | `#1E3A5F` | `#3B82F6` |
| 翡翠绿 | `#065F46` | `#10B981` |
| 暗红橙 | `#7F1D1D` | `#F97316` |

## Template B: 纯色 + 几何符号

适合：管理后台、数据工具。单色背景，居中白色几何图形。

**参数：**
- `{{BG_COLOR}}` — 背景色（品牌主色）
- `{{SHAPE}}` — 几何图形类型：`hexagon` | `circle` | `diamond`

### 六边形变体

```xml
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <!-- 纯色圆角矩形背景 -->
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179"
        fill="{{BG_COLOR}}"/>
  <!-- 六边形 -->
  <polygon
    points="512,280 680,376 680,568 512,664 344,568 344,376"
    stroke="white" stroke-width="28" fill="none"
    stroke-linejoin="round"/>
  <!-- 中心圆点 -->
  <circle cx="512" cy="472" r="40" fill="white"/>
</svg>
```

### 圆环变体

```xml
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179"
        fill="{{BG_COLOR}}"/>
  <!-- 外圆环 -->
  <circle cx="512" cy="472" r="200" stroke="white" stroke-width="28" fill="none"/>
  <!-- 内圆点 -->
  <circle cx="512" cy="472" r="50" fill="white"/>
</svg>
```

### 菱形变体

```xml
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <rect x="112" y="112" width="800" height="800" rx="179" ry="179"
        fill="{{BG_COLOR}}"/>
  <!-- 菱形 -->
  <rect x="362" y="322" width="300" height="300"
        transform="rotate(45 512 472)"
        stroke="white" stroke-width="28" fill="none"
        rx="20"/>
</svg>
```

**推荐纯色：**

| 风格 | BG_COLOR |
|------|----------|
| 蓝色 | `#2563EB` |
| 紫色 | `#7C3AED` |
| 青色 | `#0891B2` |
| 绿色 | `#059669` |
| 橙色 | `#EA580C` |
| 红色 | `#DC2626` |

## Agent 使用指引

1. 根据用户选择的风格确定模板（A 或 B）
2. 替换颜色参数（用户指定或从 Tailwind 提取或推荐配色）
3. Template A: 替换 `{{LETTER}}` 为应用名首字母
4. Template B: 选择几何变体
5. 将生成的 SVG 写入 `build/appicon.svg`
6. 提示用户运行 `scripts/svg-to-icns.sh build/appicon.svg` 生成 ICNS
