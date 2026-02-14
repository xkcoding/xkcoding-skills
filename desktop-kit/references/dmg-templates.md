# DMG 背景 SVG 模板

> Agent 选择模板后，替换颜色和文字参数生成最终 DMG 背景。Drop zone 坐标不可修改。

## Template A: 简约箭头

适合所有类型的应用。渐变背景 + 中间箭头 + 安装说明。

**参数：**
- `{{BG_COLOR_1}}` — 背景渐变起始色
- `{{BG_COLOR_2}}` — 背景渐变结束色
- `{{APP_NAME}}` — 应用名称
- `{{ACCENT_COLOR}}` — 箭头和装饰线条颜色

```xml
<svg width="600" height="400" viewBox="0 0 600 400" fill="none"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="600" y2="400"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{{BG_COLOR_1}}"/>
      <stop offset="100%" stop-color="{{BG_COLOR_2}}"/>
    </linearGradient>
  </defs>

  <!-- 背景 -->
  <rect width="600" height="400" fill="url(#bg)"/>

  <!-- 顶部应用名 -->
  <text x="300" y="60" text-anchor="middle"
        font-family="PingFang SC, -apple-system, sans-serif"
        font-size="22" font-weight="600" fill="white" opacity="0.95">
    {{APP_NAME}}
  </text>

  <!-- 中间箭头 (从 App 指向 Applications) -->
  <line x1="210" y1="185" x2="380" y2="185"
        stroke="{{ACCENT_COLOR}}" stroke-width="3" stroke-linecap="round"
        opacity="0.6"/>
  <polygon points="390,185 375,175 375,195"
           fill="{{ACCENT_COLOR}}" opacity="0.6"/>

  <!-- Drop zone 标签 -->
  <text x="150" y="240" text-anchor="middle"
        font-family="PingFang SC, -apple-system, sans-serif"
        font-size="11" fill="white" opacity="0.5">
    拖到这里
  </text>
  <text x="450" y="240" text-anchor="middle"
        font-family="PingFang SC, -apple-system, sans-serif"
        font-size="11" fill="white" opacity="0.5">
    Applications
  </text>

  <!-- 分隔线 -->
  <line x1="60" y1="320" x2="540" y2="320"
        stroke="white" stroke-width="0.5" opacity="0.2"/>

  <!-- 底部安装说明 -->
  <text x="300" y="350" text-anchor="middle"
        font-family="PingFang SC, -apple-system, sans-serif"
        font-size="10" fill="white" opacity="0.45">
    首次打开：右键点击 {{APP_NAME}} → 选择「打开」→ 弹窗点「打开」
  </text>
  <text x="300" y="370" text-anchor="middle"
        font-family="PingFang SC, -apple-system, sans-serif"
        font-size="10" fill="white" opacity="0.35">
    仅第一次需要，之后正常双击即可
  </text>
</svg>
```

**推荐配色：**

| 风格 | BG_COLOR_1 | BG_COLOR_2 | ACCENT_COLOR |
|------|-----------|-----------|-------------|
| 淡雅蓝紫（Argus 风格） | `#EEF0FF` | `#F5EEFF` | `#6366F1` |
| 深色科技 | `#0F172A` | `#1E293B` | `#38BDF8` |
| 暖色柔和 | `#FFF7ED` | `#FEF3F2` | `#F97316` |
| 翡翠清新 | `#ECFDF5` | `#F0FDF4` | `#10B981` |

## Agent 使用指引

1. 选择模板和配色方案
2. 替换参数（APP_NAME、颜色）
3. 将 SVG 写入 `build/dmg/background.svg`
4. 生成 HTML 包装写入 `build/dmg/background.html`（参考 dmg-background-spec.md 的模板）
5. 告知用户使用浏览器截图或 rsvg-convert 生成 PNG

**关键提醒：不要修改 drop zone 相关的任何坐标。**
