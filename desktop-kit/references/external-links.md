# 外部链接拦截

> 桌面应用内的外部链接（http/https）应在系统默认浏览器中打开，而非在 WKWebView 内导航。

## 拦截代码片段

### React / TypeScript

```typescript
useEffect(() => {
    function handleClick(e: MouseEvent) {
        const anchor = (e.target as HTMLElement).closest('a')
        if (!anchor) return
        const href = anchor.getAttribute('href')
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) return
        if (href.startsWith('http://') || href.startsWith('https://')) {
            e.preventDefault()
            window.runtime?.BrowserOpenURL(href)
        }
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
}, [])
```

### Vue 3 Composition API

```typescript
import { onMounted, onUnmounted } from 'vue'

onMounted(() => {
    document.addEventListener('click', handleExternalLink)
})
onUnmounted(() => {
    document.removeEventListener('click', handleExternalLink)
})

function handleExternalLink(e: MouseEvent) {
    const anchor = (e.target as HTMLElement).closest('a')
    if (!anchor) return
    const href = anchor.getAttribute('href')
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return
    if (href.startsWith('http://') || href.startsWith('https://')) {
        e.preventDefault()
        ;(window as any).runtime?.BrowserOpenURL(href)
    }
}
```

### 纯 JavaScript（静态页面）

```javascript
document.addEventListener('click', function(e) {
    var anchor = e.target.closest('a')
    if (!anchor) return
    var href = anchor.getAttribute('href')
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return
    if (href.startsWith('http://') || href.startsWith('https://')) {
        e.preventDefault()
        if (window.runtime && window.runtime.BrowserOpenURL) {
            window.runtime.BrowserOpenURL(href)
        }
    }
})
```

## 集成位置

| 框架 | 推荐位置 |
|------|---------|
| React | `App.tsx` 或根组件的 `useEffect` |
| Vue | `App.vue` 的 `onMounted` |
| Svelte | `+layout.svelte` 的 `onMount` |
| 静态 | `index.html` 底部 `<script>` |

## 工作原理

1. 在 `document` 上监听全局 `click` 事件（事件委托）
2. 通过 `closest('a')` 找到最近的锚元素
3. 过滤内部链接（`#` 锚点、`javascript:` 协议）
4. 对 `http://` 和 `https://` 链接调用 Wails 运行时的 `BrowserOpenURL`
5. `preventDefault()` 阻止 WKWebView 内导航

## 注意事项

- `window.runtime` 是 Wails 自动注入的全局对象，仅在桌面环境可用
- 代码中使用 `?.` 可选链确保在浏览器开发模式下不报错
- 事件监听器在组件卸载时必须清理，避免内存泄漏
