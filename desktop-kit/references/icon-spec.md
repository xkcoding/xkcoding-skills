# macOS 图标设计规范

> 所有应用图标必须遵循 macOS Human Interface Guidelines 的尺寸和圆角规范。

## Canvas 规格

```
Canvas:           1024 × 1024 px
Safe area:        112px padding (each side)
Background rect:  x=112 y=112 width=800 height=800
Corner radius:    rx=179 ry=179 (≈ 22% of 800)
Icon content:     居中在 800×800 safe area 内
```

## SVG 基础结构

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
  <!-- 图标内容，居中在 safe area -->
  <!-- ... -->
</svg>
```

## 多尺寸 iconset 输出

macOS `.icns` 需要以下尺寸（放入 `AppIcon.iconset/` 目录）：

| 文件名 | 尺寸 |
|--------|------|
| `icon_16x16.png` | 16×16 |
| `icon_16x16@2x.png` | 32×32 |
| `icon_32x32.png` | 32×32 |
| `icon_32x32@2x.png` | 64×64 |
| `icon_128x128.png` | 128×128 |
| `icon_128x128@2x.png` | 256×256 |
| `icon_256x256.png` | 256×256 |
| `icon_256x256@2x.png` | 512×512 |
| `icon_512x512.png` | 512×512 |
| `icon_512x512@2x.png` | 1024×1024 |

转换命令：

```bash
iconutil --convert icns AppIcon.iconset
# 输出 AppIcon.icns
```

## 输出文件位置

```
build/
├── appicon.svg          # 源文件
├── AppIcon.iconset/     # 多尺寸 PNG（中间产物）
│   ├── icon_16x16.png
│   ├── icon_16x16@2x.png
│   └── ...
└── appicon.icns         # 最终产物
```

## 设计原则

- 背景使用渐变或纯色，避免复杂纹理（缩小后不清晰）
- 图标内容用白色或浅色线条/填充，确保在暗色 Dock 上可辨认
- 线条粗细至少 2px（在 1024 尺度下），避免缩小后消失
- 保持图标简洁，16x16 尺寸下仍可识别
