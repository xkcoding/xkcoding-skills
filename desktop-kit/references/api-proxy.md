# Go 反向代理模式

> 当 Web App 需要访问后端 API 时，Wails 桌面应用通过 Go 层的反向代理转发请求，绕过 WKWebView 的限制。

## 为什么需要 API 代理

1. **WKWebView 60s 超时限制** — macOS WKWebView 默认 60 秒请求超时，无法修改。Go 代理层设置 300 秒超时，适合长时间运行的 API（大模型推理、数据导出等）
2. **跨域问题** — 嵌入的前端通过 `wails://` 协议加载，直接请求外部 API 会触发 CORS。代理层在同源下转发，无 CORS 问题
3. **环境灵活性** — 后端 URL 通过 `ldflags` 注入，同一份代码可构建开发/测试/生产不同版本

## 代理实现模式

```go
var backendURL = "http://localhost:8080" // ldflags -X 'main.backendURL=...' 覆盖
const proxyTimeout = 300 * time.Second

func (a *App) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // 1. 仅代理匹配前缀的请求
    if !strings.HasPrefix(r.URL.Path, "/api/") {
        http.NotFound(w, r)
        return
    }
    // 2. 构造目标请求
    targetURL := backendURL + r.URL.RequestURI()
    proxyReq, _ := http.NewRequestWithContext(r.Context(), r.Method, targetURL, r.Body)
    // 3. 转发所有请求头
    for key, values := range r.Header {
        for _, v := range values {
            proxyReq.Header.Add(key, v)
        }
    }
    // 4. 发送请求
    resp, err := a.client.Do(proxyReq)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    // 5. 回写响应头和 body
    for key, values := range resp.Header {
        for _, v := range values {
            w.Header().Add(key, v)
        }
    }
    w.WriteHeader(resp.StatusCode)
    io.Copy(w, resp.Body)
}
```

## ldflags 注入方式

构建时通过 ldflags 覆盖 backendURL：

```bash
wails build -clean -ldflags "-X 'main.backendURL=https://api.example.com'"
```

从 `.env.production` 读取：

```bash
source .env.production
wails build -clean -ldflags "-X 'main.backendURL=$VITE_API_BASE'"
```

## API 前缀适配

不同项目的 API 前缀可能不同：

| 模式 | ServeHTTP 中的前缀检查 |
|------|----------------------|
| `/api/` | `strings.HasPrefix(r.URL.Path, "/api/")` |
| `/v1/` | `strings.HasPrefix(r.URL.Path, "/v1/")` |
| 多前缀 | 用 `||` 组合多个 HasPrefix 检查 |

Agent 应根据 detect-project.sh 的 `apiPrefix` 结果来设置前缀。

## 注意事项

- `http.Client` 必须设置 `Timeout`，否则默认无超时，连接泄漏风险
- 代理层不做认证，API 认证由前端 header 携带 token 透传
- 大文件上传/下载场景需考虑流式传输，当前 `io.Copy` 已支持流式
