---
name: md-image-rehost
description: >-
  Use this whenever someone points at a Markdown file (or a folder of .md files)
  and wants the images it references pulled onto their OWN Aliyun OSS / object
  storage / CDN, with every Markdown image link rewritten to the new address.
  Images can be remote (知乎、微信、imgur、别人服务器、旧博客、过期外链) or
  local/relative on disk — both are uploaded by default, downloaded, compressed,
  and converted to WebP on the way. Handles both ![](…) and <img src> inside .md.
  This is THE skill for 备份/转存/持久化/搬迁 a note, 周报, 剪藏, Obsidian 库,
  README, or 一批要迁移/发布的文章; for saving images that 会失效/裂开/过期/被墙/
  打不开 because they live on someone else's host; and for "下载并压缩后传到阿里云
  OSS 再替换 markdown 链接为 cdn 地址". If the request couples Markdown + images +
  your-own-OSS/CDN, use it. Do NOT use for generating or designing new images;
  for compressing a single loose image with no Markdown; for uploading to
  non-Aliyun hosts (S3↔S3, sm.ms, 通用图床); or for non-Markdown files.
---

# Markdown Image Rehost → Aliyun OSS/CDN

Downloads each remote image in Markdown, compresses it (default WebP q80),
uploads to **Aliyun OSS**, and rewrites `![](url)` / `<img src>` links to your
CDN — turning fragile third-party image links into permanent self-hosted ones.

A single image that fails (404, decode error, OSS hiccup) keeps its **original**
URL and is logged — one bad image never aborts the whole file.

## When to reach for this

The user has Markdown whose images live on someone else's host and wants them on
their own OSS/CDN: expiring daily-report images, Obsidian clippings, scraped
articles, migrated blog posts. Phrases: "图片会失效 / 转存到我的 CDN / rehost
images / back up the images in this note".

## Prerequisites

- `node` (v18+, for global `fetch`).
- `sharp` + `ali-oss`, installed **inside this skill's directory** (they're
  listed in its `package.json`). If `node_modules` is missing, install once:
  ```bash
  npm install --prefix <skill-dir>
  ```
  The script lives in `scripts/` and resolves these from the skill dir, so no
  per-project install is needed. (ESM bare imports don't resolve through
  `npx --package`, which is why deps live here rather than being fetched ad hoc.)
- An Aliyun OSS bucket; ideally a RAM sub-account scoped to the key prefix.

## OSS config — via environment, never CLI args

Keep credentials out of shell history. Set these before running:

| Var | Required | Notes |
|---|---|---|
| `OSS_ACCESS_KEY_ID` | ✅ | RAM key id |
| `OSS_ACCESS_KEY_SECRET` | ✅ | RAM key secret |
| `OSS_BUCKET` | ✅ | bucket name |
| `OSS_REGION` | one of region/endpoint | e.g. `oss-cn-hangzhou` |
| `OSS_ENDPOINT` | one of region/endpoint | overrides region if both set |
| `OSS_CDN_BASE_URL` | optional | public base, e.g. `https://cdn.example.com`; else the raw OSS URL is used |
| `OSS_KEY_PREFIX` | optional | top-level namespace override; unset = derive from project name (see keys below) |
| `OSS_PROCESS_STYLE` | optional | appended as `?x-oss-process=style/<name>` |

### Where config lives — configure once

The script **auto-loads** a config file if present, so the user sets credentials
once instead of exporting every session. Lookup order (first found wins; real
environment variables always take precedence over the file):

1. `$MD_IMAGE_REHOST_ENV` (explicit path)
2. `~/.config/md-image-rehost.env`
3. `<skill-dir>/.env`

Copy `oss.env.example` (in the skill dir) to `~/.config/md-image-rehost.env` and
fill it in. The skill prints `[config] loaded OSS settings from <path>` when it
uses one. Keep that file private — it holds credentials — and never commit it.

If none exists and `OSS_*` aren't in the environment, ask the user for the
bucket/region/CDN and where their RAM key lives, then offer to write
`~/.config/md-image-rehost.env`. A project-local `.env.local` also works if they
source it first: `set -a; . ./.env.local; set +a`.

## How to run

```bash
node <skill-dir>/scripts/rehost.mjs <file.md | dir> [options]
```

(If it errors that `sharp`/`ali-oss` are missing, run `npm install --prefix <skill-dir>` first.)

Options:

| Option | Default | Meaning |
|---|---|---|
| `<path>` | — | a `.md` file, or a directory (recurses all `.md`) |
| `--max-width N` | off | downscale images wider than N px |
| `--quality Q` | `80` | encoder quality 0–100 |
| `--format webp\|jpeg\|png` | `webp` | output format |
| `--animated` | off | keep GIF animation (animated WebP) — see caveat |
| `--skip-local` | off | leave on-disk/relative-path images untouched (by default they're uploaded too) |
| `--dry-run` | off | report what would change, upload nothing, don't rewrite |

**Both remote URLs and local images are rehosted by default.** Local references
(relative like `./img/a.png`, absolute, or `file://`) are resolved against the
Markdown file's own directory, then uploaded just like remote ones — so a note
moved to a new machine or published online keeps all its images. Pass
`--skip-local` only when the user explicitly wants on-disk images left as-is.
`data:` URIs and links already on the configured CDN host are always skipped.

**Always offer `--dry-run` first** on unfamiliar input so the user sees how many
images would be touched before anything is uploaded or the file is rewritten.

## Object keys & dedup

Keys **mirror the source file's location** so the bucket stays browsable:

```
<namespace>/<md-path-relative-to-project-root-without-.md>/<sha256[:16]>.<ext>
```

- `<namespace>` = `OSS_KEY_PREFIX` when set, otherwise the **project name** — the
  git repo top-level directory the md lives in, or (outside git) the input
  directory name.
- The md's path *under that root* is preserved, so a note at
  `second-brain/00_Inbox/foo.md` uploads to `second-brain/00_Inbox/foo/<hash>.webp`.

The filename is content-addressed, so images dedup within a document and re-runs
skip the upload (existing object detected via `HEAD`). Re-running is safe and cheap.
Paths with spaces or 中文 are URL-encoded automatically.

If your RAM sub-account is scoped to a fixed prefix (e.g. `acs:oss:*:*:bucket/myapp/*`),
set `OSS_KEY_PREFIX=myapp` so keys stay inside the authorized path.

## GIF / animation caveat (important)

By default GIFs are flattened to their **first frame**. This is deliberate:
Aliyun OSS image styles (the `?x-oss-process=style/...` delivery path, often
mandatory when a bucket has 原图保护 / "access only via style") **reject animated
WebP** (`BadWebPImage`) and flatten animation anyway. A static first frame keeps
the URL working instead of returning 400.

Only pass `--animated` if the target CDN serves the object **without** a
flattening style (no 原图保护, or a style that preserves frames). If unsure,
leave it off — a working static image beats a broken animated one.

## Verifying

After a real run, spot-check a rewritten URL actually resolves:

```bash
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' '<one rewritten URL>'
```

If a bucket uses 原图保护, the raw object 403s and only the
`?x-oss-process=style/...` URL returns 200 — which is exactly the URL written
into the file when `OSS_PROCESS_STYLE` is set. A `400 BadWebPImage` means an
animated WebP slipped through; re-run without `--animated`.
