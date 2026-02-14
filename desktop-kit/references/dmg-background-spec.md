# DMG 背景设计规范

> DMG 背景的坐标系必须与 create-dmg 参数精确对齐，这是最容易出错的地方。

## 核心坐标系

```
Canvas:        600 × 400 px (--window-size 600 400)
Icon size:     72px (--icon-size 72)

App icon:      center (150, 185)  →  --icon "AppName.app" 150 185
Apps folder:   center (450, 185)  →  --app-drop-link 450 185
```

### SVG 中的 Drop Zone 留白区域

```
Left drop zone (App 图标):
  rect x=110 y=149 width=80 height=72

Right drop zone (Applications):
  rect x=410 y=149 width=80 height=72
```

**这些坐标是不可修改的。** Agent 只能修改装饰元素（颜色、文字、图形），不能改变 drop zone 位置。

## create-dmg 完整命令

```bash
create-dmg \
  --volname "{{APP_NAME}}" \
  --background "build/dmg/background.png" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 72 \
  --icon "{{APP_NAME}}.app" 150 185 \
  --app-drop-link 450 185 \
  "build/bin/{{APP_NAME}}-{{VERSION}}-macOS.dmg" \
  "build/bin/{{APP_NAME}}.app"
```

## SVG → PNG 渲染管线

```
background.svg   ← Agent 生成，所有视觉元素
      │
      ▼
background.html  ← HTML 包装，确保字体渲染正确
      │
      ▼
background.png   ← 浏览器截图 (2x 分辨率: 1200×800)
```

### HTML 包装模板

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;width:600px;height:400px;overflow:hidden}
body{font-family:"PingFang SC",-apple-system,"Helvetica Neue",sans-serif;
     -webkit-font-smoothing:antialiased}
</style></head><body>
<!-- 将 SVG 内容粘贴到这里 -->
</body></html>
```

### PNG 转换方式

**方式 A: 浏览器截图（推荐，字体渲染最好）**

用 Chrome/Chromium headless 截图：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --screenshot="build/dmg/background.png" \
  --window-size=1200,800 \
  --default-background-color=0 \
  "build/dmg/background.html"
```

**方式 B: rsvg-convert**

```bash
rsvg-convert -w 1200 -h 800 build/dmg/background.svg -o build/dmg/background.png
```

注意：rsvg-convert 不支持自定义字体，中文字体可能 fallback。

## 输出文件位置

```
build/dmg/
├── background.svg     # SVG 源文件
├── background.html    # HTML 包装（用于浏览器截图）
└── background.png     # 最终 PNG（2x 分辨率 1200×800）
```

## 安装引导文字（必需）

ad-hoc 签名的应用必须包含以下引导文字：

```
首次打开：右键点击 {{APP_NAME}} → 选择「打开」→ 弹窗点「打开」
仅第一次需要，之后正常双击即可
```

这段文字应放置在 DMG 背景的底部区域（y > 330）。
