# md-image-rehost

抽取 Markdown 文件（或整个目录的 `.md`）里引用的图片，**压缩后转存到你自己的阿里云 OSS/CDN**，并就地把链接替换为新地址。让笔记 / 周报 / 剪藏 / Obsidian 库里那些挂在别人服务器上、随时会失效的图片，变成永久自托管。

- **远程 + 本地图都默认上传**（`--skip-local` 可只处理远程外链）
- sharp 压缩，默认 WebP q80，可 `--max-width` 缩放
- GIF 取首帧静态图（适配阿里云 OSS「原图保护 + 仅样式访问」的样式投递）
- 对象键镜像源文件位置：`<项目名>/<md 相对路径>/<内容哈希>.webp`，同图去重、`HEAD` 跳过重传
- 单张图失败保留原链，不阻断整篇

## 前置

- Node.js ≥ 18
- 首次使用前在本目录安装依赖：

  ```bash
  npm install --prefix <本 skill 目录>
  ```

## 配置（一次即可）

凭证不进 skill，只走环境变量 / 配置文件。复制 `oss.env.example` 到
`~/.config/md-image-rehost.env` 并填写，脚本会自动加载：

```
OSS_ACCESS_KEY_ID=...
OSS_ACCESS_KEY_SECRET=...
OSS_BUCKET=...
OSS_REGION=oss-cn-hangzhou
OSS_CDN_BASE_URL=https://cdn.example.com
# OSS_KEY_PREFIX=        # 可选；不设则按项目名派生目录
# OSS_PROCESS_STYLE=...   # 可选；追加 ?x-oss-process=style/<name>
```

RAM 子账号最小权限示例（限定到某前缀）：

```json
{
  "Version": "1",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["oss:PutObject", "oss:GetObject"],
    "Resource": ["acs:oss:*:*:your-bucket/your-prefix/*"]
  }]
}
```

## 用法

直接对 Claude Code 说「把这个 md 里的图片转存到我的阿里云 CDN」即可，或手动：

```bash
node md-image-rehost/scripts/rehost.mjs <file.md | dir> \
  [--max-width 1600] [--quality 80] [--format webp|jpeg|png] \
  [--skip-local] [--animated] [--dry-run]
```

先用 `--dry-run` 预览会处理几张图、不上传不改写。

完整说明见 [`SKILL.md`](SKILL.md)。
