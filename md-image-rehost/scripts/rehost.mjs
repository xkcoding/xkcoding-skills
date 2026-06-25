#!/usr/bin/env node
// Extract images from Markdown, compress them, upload to Aliyun OSS, and rewrite
// the links in place. Self-contained — needs `sharp` and `ali-oss` (run via
// `npx --yes --package=sharp --package=ali-oss node rehost.mjs ...`).
//
// Usage:
//   node rehost.mjs <file.md | dir> [--max-width N] [--quality Q]
//                   [--format webp|jpeg|png] [--animated] [--dry-run]
//
// OSS config comes from env (never CLI), so secrets stay out of shell history:
//   OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET   (required)
//   OSS_BUCKET                                  (required)
//   OSS_REGION (e.g. oss-cn-hangzhou) OR OSS_ENDPOINT   (one required)
//   OSS_CDN_BASE_URL    (optional, e.g. https://cdn.example.com; else OSS URL)
//   OSS_KEY_PREFIX      (optional, default "md-images")
//   OSS_PROCESS_STYLE   (optional, appended as ?x-oss-process=style/<name>)

import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { join, extname, relative, resolve, dirname, basename, isAbsolute } from 'node:path'
import { createHash } from 'node:crypto'
import { execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

// ---------- args ----------
const argv = process.argv.slice(2)
const opts = { input: '', maxWidth: undefined, quality: 80, format: 'webp', animated: false, dryRun: false, skipLocal: false }
for (let i = 0; i < argv.length; i++) {
  const a = argv[i]
  if (a === '--max-width') opts.maxWidth = Number(argv[++i])
  else if (a === '--quality') opts.quality = Number(argv[++i])
  else if (a === '--format') opts.format = argv[++i]
  else if (a === '--animated') opts.animated = true
  else if (a === '--dry-run') opts.dryRun = true
  else if (a === '--skip-local') opts.skipLocal = true
  else if (!a.startsWith('-') && !opts.input) opts.input = a
}
if (!opts.input) {
  console.error('Usage: node rehost.mjs <file.md | dir> [--max-width N] [--quality Q] [--format webp|jpeg|png] [--animated] [--skip-local] [--dry-run]')
  process.exit(1)
}

// ---------- env ----------
// Load OSS config from a conventional file if present, WITHOUT overriding vars
// already set in the environment. Configure once and the skill works anywhere.
// Precedence: real env > $MD_IMAGE_REHOST_ENV > ~/.config/md-image-rehost.env > <skill-dir>/.env
function loadEnvFile() {
  const candidates = [
    process.env.MD_IMAGE_REHOST_ENV,
    process.env.HOME ? join(process.env.HOME, '.config', 'md-image-rehost.env') : null,
    fileURLToPath(new URL('../.env', import.meta.url)),
  ].filter(Boolean)
  for (const f of candidates) {
    if (!existsSync(f)) continue
    for (const line of readFileSync(f, 'utf8').split('\n')) {
      const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/)
      if (!m || process.env[m[1]] !== undefined) continue
      let v = m[2]
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1)
      process.env[m[1]] = v
    }
    console.log(`[config] loaded OSS settings from ${f}`)
    break // first file found wins
  }
}
loadEnvFile()

const env = (k) => {
  const v = process.env[k]
  return v && v.trim() ? v.trim() : undefined
}
const cfg = {
  accessKeyId: env('OSS_ACCESS_KEY_ID'),
  accessKeySecret: env('OSS_ACCESS_KEY_SECRET'),
  bucket: env('OSS_BUCKET'),
  region: env('OSS_REGION'),
  endpoint: env('OSS_ENDPOINT'),
  cdnBaseUrl: env('OSS_CDN_BASE_URL')?.replace(/\/+$/, ''),
  // Empty = derive the namespace from the project (git repo / input dir) name.
  keyPrefix: (env('OSS_KEY_PREFIX') ?? '').replace(/^\/+|\/+$/g, ''),
  processStyle: env('OSS_PROCESS_STYLE'),
}
if (!opts.dryRun && (!cfg.accessKeyId || !cfg.accessKeySecret || !cfg.bucket || (!cfg.region && !cfg.endpoint))) {
  console.error('Missing OSS env: need OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET, and OSS_REGION or OSS_ENDPOINT.')
  process.exit(1)
}

let sharp, OSS
try {
  sharp = (await import('sharp')).default
  OSS = opts.dryRun ? null : (await import('ali-oss')).default
} catch (e) {
  console.error(`Missing dependency (${e.message}).\nRun: npm install --prefix ${new URL('..', import.meta.url).pathname}`)
  process.exit(1)
}
const client = OSS
  ? new OSS({ region: cfg.region, endpoint: cfg.endpoint, accessKeyId: cfg.accessKeyId, accessKeySecret: cfg.accessKeySecret, bucket: cfg.bucket, secure: true })
  : null

const FORMAT_META = {
  webp: { ext: 'webp', contentType: 'image/webp' },
  jpeg: { ext: 'jpg', contentType: 'image/jpeg' },
  png: { ext: 'png', contentType: 'image/png' },
}
const FETCH_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
const MD_IMAGE = /!\[([^\]]*)\]\((\S+?)(\s+"[^"]*"|\s+'[^']*')?\)/g
const HTML_IMAGE = /<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["'][^>]*>/gi

const skipHosts = new Set()
if (cfg.cdnBaseUrl) { try { skipHosts.add(new URL(cfg.cdnBaseUrl).hostname) } catch { /* ignore */ } }

function collectUrls(md) {
  const urls = new Set()
  for (const m of md.matchAll(MD_IMAGE)) urls.add(m[2])
  for (const m of md.matchAll(HTML_IMAGE)) urls.add(m[1])
  return [...urls]
}
// Classify a reference into how we should load it. Both remote and local images
// are rehosted by default; pass --skip-local to leave on-disk images untouched.
function classify(ref) {
  if (/^data:/i.test(ref)) return 'skip' // inline data URIs — nothing to rehost
  let u = null
  try { u = new URL(ref) } catch { /* not an absolute URL → treat as local path */ }
  if (u && (u.protocol === 'http:' || u.protocol === 'https:')) {
    return skipHosts.has(u.hostname) ? 'skip' : 'remote'
  }
  if (u && u.protocol === 'file:') return opts.skipLocal ? 'skip' : 'local'
  if (u && u.protocol) return 'skip' // mailto:, ftp:, etc — not a local image
  return opts.skipLocal ? 'skip' : 'local' // bare/relative path
}
function resolveLocal(ref, mdDir) {
  let p = ref.startsWith('file:') ? fileURLToPath(ref) : ref.split('#')[0].split('?')[0]
  let abs = isAbsolute(p) ? p : resolve(mdDir, p)
  if (!existsSync(abs)) {
    try {
      const dec = decodeURIComponent(p)
      abs = isAbsolute(dec) ? dec : resolve(mdDir, dec)
    } catch { /* keep abs */ }
  }
  return abs
}
async function fetchImage(url) {
  const res = await fetch(url, { headers: { 'User-Agent': FETCH_UA } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return Buffer.from(await res.arrayBuffer())
}
async function loadImage(ref, mdDir) {
  if (classify(ref) === 'remote') return fetchImage(ref)
  const abs = resolveLocal(ref, mdDir)
  if (!existsSync(abs)) throw new Error(`local file not found: ${abs}`)
  return readFileSync(abs)
}
async function compress(buf) {
  // First frame only by default: many CDNs (e.g. Aliyun OSS image styles) reject
  // animated WebP and flatten animation anyway. Pass --animated to keep frames.
  let pipeline = opts.animated ? sharp(buf, { animated: true }) : sharp(buf)
  if (opts.maxWidth) {
    const meta = await pipeline.metadata()
    if (meta.width && meta.width > opts.maxWidth) pipeline = pipeline.resize({ width: opts.maxWidth, withoutEnlargement: true })
  }
  if (opts.format === 'jpeg') pipeline = pipeline.jpeg({ quality: opts.quality })
  else if (opts.format === 'png') pipeline = pipeline.png({ quality: opts.quality })
  else pipeline = pipeline.webp({ quality: opts.quality })
  const out = await pipeline.toBuffer()
  const meta = FORMAT_META[opts.format] ?? FORMAT_META.webp
  return { data: out, ext: meta.ext, contentType: meta.contentType }
}
function publicUrl(key, objectUrl) {
  // encodeURI keeps "/" and ":" but escapes spaces / unicode so paths mirroring
  // the source file name (which may contain spaces or 中文) yield valid URLs.
  const base = cfg.cdnBaseUrl ? encodeURI(`${cfg.cdnBaseUrl}/${key}`) : objectUrl
  return cfg.processStyle ? `${base}?x-oss-process=style/${cfg.processStyle}` : base
}
async function uploadDedup(key, data, contentType) {
  if (opts.dryRun) return publicUrl(key, `oss://${cfg.bucket}/${key}`)
  let exists = false
  try { await client.head(key); exists = true } catch (e) { if (e.status !== 404) throw e }
  if (!exists) await client.put(key, data, { mime: contentType })
  return publicUrl(key, client.generateObjectUrl(key))
}

// Mirror the source location in the object key: <namespace>/<md path under root>/<hash>.<ext>.
// namespace = OSS_KEY_PREFIX when set, else the project (git repo / input dir) name.
function keyDirFor(path) {
  const relStem = relative(ROOT, resolve(path)).replace(/\.md$/i, '')
  const base = cfg.keyPrefix || PROJECT
  return `${base}/${relStem}`.replace(/\/+/g, '/').replace(/^\/+|\/+$/g, '')
}

async function rehostFile(path) {
  const md = readFileSync(path, 'utf8')
  const mdDir = dirname(resolve(path))
  const urls = collectUrls(md).filter((u) => classify(u) !== 'skip')
  const keyDir = keyDirFor(path)
  if (opts.dryRun) console.log(`  key dir: ${keyDir}/`)
  const map = new Map()
  let ok = 0, failed = 0
  for (const url of urls) {
    try {
      const raw = await loadImage(url, mdDir)
      const c = await compress(raw)
      const key = `${keyDir}/${createHash('sha256').update(c.data).digest('hex').slice(0, 16)}.${c.ext}`
      map.set(url, await uploadDedup(key, c.data, c.contentType))
      ok++
    } catch (e) {
      failed++
      console.warn(`  ! keep original (${url}): ${e.message}`)
    }
  }
  let out = md
  if (map.size) {
    out = md
      .replace(MD_IMAGE, (full, alt, u, title) => (map.has(u) ? `![${alt}](${map.get(u)}${title ?? ''})` : full))
      .replace(HTML_IMAGE, (full, src) => (map.has(src) ? full.replace(src, map.get(src)) : full))
    if (!opts.dryRun) writeFileSync(path, out, 'utf8')
  }
  console.log(`${path}: ${ok} rehosted, ${failed} failed, ${urls.length} eligible${opts.dryRun ? ' [dry-run]' : ''}`)
  return { ok, failed }
}

function mdFiles(input) {
  const st = statSync(input)
  if (st.isFile()) return input.endsWith('.md') ? [input] : []
  const out = []
  for (const e of readdirSync(input, { withFileTypes: true })) {
    const p = join(input, e.name)
    if (e.isDirectory()) out.push(...mdFiles(p))
    else if (e.isFile() && extname(e.name).toLowerCase() === '.md') out.push(p)
  }
  return out
}

// Project root = the md's git repo top-level, else the input dir (or the file's dir).
function resolveRoot(input) {
  const abs = resolve(input)
  const baseDir = statSync(abs).isDirectory() ? abs : dirname(abs)
  try {
    return execSync('git rev-parse --show-toplevel', { cwd: baseDir, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return baseDir
  }
}
const ROOT = resolveRoot(opts.input)
const PROJECT = basename(ROOT)

const files = mdFiles(opts.input)
if (!files.length) { console.error(`No .md files at ${opts.input}`); process.exit(1) }
let tOk = 0, tFail = 0
for (const f of files) { const r = await rehostFile(f); tOk += r.ok; tFail += r.failed }
console.log(`\nDone: ${files.length} file(s), ${tOk} images rehosted, ${tFail} failed.`)
