# Wails 壳代码生成知识

> Agent 根据本文档中的模式和项目检测结果，现场生成 Wails v2 壳代码。

## main.go 生成模式

### 基础结构

```go
package main

import (
    "embed"
    "github.com/wailsapp/wails/v2"
    "github.com/wailsapp/wails/v2/pkg/options"
    "github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:dist
var assets embed.FS

func main() {
    app := NewApp()
    err := wails.Run(&options.App{
        Title:     "{{APP_NAME}}",
        Width:     1440,
        Height:    900,
        MinWidth:  1024,
        MinHeight: 768,
        AssetServer: &assetserver.Options{
            Assets: assets,
            // 如果需要 API 代理，添加: Handler: app,
        },
        OnStartup: app.startup,
        Bind:      []interface{}{app},
    })
    if err != nil {
        println("Error:", err.Error())
    }
}
```

### 关键要点

- `//go:embed all:dist` — 嵌入前端构建产物，目录名根据构建工具而定（Vite 通常是 `dist`，CRA 是 `build`）
- `AssetServer.Handler` — 仅当项目需要 API 代理时添加，指向 App 的 `ServeHTTP` 方法
- 窗口尺寸 — 默认 1440x900（适合大部分管理后台），最小 1024x768

## app.go 生成模式

### 无 API 代理版本

```go
package main

import "context"

type App struct {
    ctx context.Context
}

func NewApp() *App {
    return &App{}
}

func (a *App) startup(ctx context.Context) {
    a.ctx = ctx
}
```

### 有 API 代理版本

```go
package main

import (
    "context"
    "io"
    "net/http"
    "strings"
    "time"
)

var backendURL = "http://localhost:8080" // ldflags 覆盖

const proxyTimeout = 300 * time.Second

type App struct {
    ctx    context.Context
    client *http.Client
}

func NewApp() *App {
    return &App{
        client: &http.Client{Timeout: proxyTimeout},
    }
}

func (a *App) startup(ctx context.Context) {
    a.ctx = ctx
}

func (a *App) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if !strings.HasPrefix(r.URL.Path, "{{API_PREFIX}}") {
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

### 代理层要点

- `backendURL` 通过 `ldflags -X 'main.backendURL=...'` 注入，支持构建时指定不同环境
- 300 秒超时 — 绕过 WKWebView 默认 60 秒限制，适合长时间运行的 API 请求
- 仅代理匹配 API 前缀的请求，其他返回 404 由 Wails 静态资源处理

## wails.json 生成模式

### Vite 项目

```json
{
  "$schema": "https://wails.io/schemas/config.v2.json",
  "name": "{{APP_NAME}}",
  "version": "{{APP_VERSION}}",
  "outputfilename": "{{APP_NAME}}",
  "frontend:install": "npm install",
  "frontend:build": "npm run build",
  "frontend:dev:watcher": "npm run dev",
  "frontend:dev:serverUrl": "auto",
  "author": {
    "name": "{{AUTHOR_NAME}}"
  }
}
```

### Webpack 项目

```json
{
  "$schema": "https://wails.io/schemas/config.v2.json",
  "name": "{{APP_NAME}}",
  "version": "{{APP_VERSION}}",
  "outputfilename": "{{APP_NAME}}",
  "frontend:install": "npm install",
  "frontend:build": "npm run build",
  "author": {
    "name": "{{AUTHOR_NAME}}"
  }
}
```

### 要点

- `version` 字段由构建脚本从 `package.json` 同步，不手动维护
- `outputfilename` 即最终 `.app` 内二进制文件名
- Vite 项目额外配置 `frontend:dev:watcher` 和 `frontend:dev:serverUrl` 支持热更新开发

## 参数替换清单

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{{APP_NAME}}` | detect-project.sh → appName | `"my-tool"` |
| `{{APP_VERSION}}` | detect-project.sh → appVersion | `"1.0.0"` |
| `{{API_PREFIX}}` | detect-project.sh → apiPrefix | `"/api/"` |
| `{{AUTHOR_NAME}}` | 用户交互确认 | `"Yangkai Shen"` |
