# Info.plist 生成知识

> macOS 应用的 Info.plist 配置核心信息，包括多语言、网络权限和应用元数据。

## 文件位置

```
build/darwin/Info.plist
```

Wails v2 构建时会自动使用此文件。

## 基础模板

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- 多语言支持 -->
    <key>CFBundleDevelopmentRegion</key>
    <string>zh_CN</string>
    <key>CFBundleLocalizations</key>
    <array>
        <string>zh_CN</string>
        <string>zh-Hans</string>
        <string>en</string>
    </array>

    <!-- 应用元数据 -->
    <key>CFBundleDisplayName</key>
    <string>{{APP_DISPLAY_NAME}}</string>
    <key>CFBundleIdentifier</key>
    <string>{{BUNDLE_ID}}</string>
    <key>CFBundleVersion</key>
    <string>{{APP_VERSION}}</string>
    <key>CFBundleShortVersionString</key>
    <string>{{APP_VERSION}}</string>

    <!-- 允许 HTTP 请求 (内网 API) -->
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>

    <!-- 高分屏支持 -->
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
```

## 配置项说明

### 多语言

| Key | 值 | 说明 |
|-----|---|------|
| `CFBundleDevelopmentRegion` | `zh_CN` | 默认开发语言 |
| `CFBundleLocalizations` | `[zh_CN, zh-Hans, en]` | 支持的语言列表 |

默认配置中文优先，英文作为 fallback。Agent 应根据用户偏好调整。

### 网络访问

`NSAppTransportSecurity` → `NSAllowsArbitraryLoads: true`

允许 HTTP 请求（非 HTTPS），因为：
- 内部 API 通常不使用 HTTPS
- 开发环境 localhost 是 HTTP
- Wails 代理层会转发到配置的后端 URL

### Bundle ID

格式建议：`com.{org}.{appname}`

示例：
- `com.xkcoding.mytool`
- `com.company.admin-panel`

## 参数替换清单

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{{APP_DISPLAY_NAME}}` | 用户输入的应用显示名 | `"我的工具"` |
| `{{BUNDLE_ID}}` | 用户输入或自动生成 | `"com.xkcoding.my-tool"` |
| `{{APP_VERSION}}` | package.json version | `"1.0.0"` |

## Agent 生成指引

1. 从用户确认的应用名生成 `CFBundleDisplayName`
2. 自动生成 `CFBundleIdentifier`（从应用名推导）
3. 版本号从 `package.json` 读取
4. 默认包含中文+英文多语言配置
5. 默认启用 `NSAllowsArbitraryLoads`（内网应用需要）
6. 将文件写入 `build/darwin/Info.plist`
