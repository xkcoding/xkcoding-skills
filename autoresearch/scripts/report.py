#!/usr/bin/env python3
"""report.py - turn a ledger into the one page a person reads.

    report.py <ar-dir>        regenerate <ar-dir>/report/index.html from the checkpoints

ar.py calls write_report() at the start and end of every round, and `ar.py serve` renders
the same page on request plus a /data.json the page polls. This entry point exists so a
ledger can be rendered on its own, without the repository the research ran in.

The page states facts and draws no conclusions: where the subject stands (best, baseline,
how many remaining items), what each round did (one row, expandable to the agent's note,
the patch, the score breakdown against the previous best), and what it cost. Anything
that needs attention - a round in progress, a stop condition, a scorer edited after the
best - appears as an action line only when it is true. Labels are Chinese; keep /
discard / crash / error stay as they are in the ledger and in `status`.

One HTML file with the data and Apache ECharts (vendor/echarts.min.js) embedded: no
network, no assets, no build. Opened from disk it is a static snapshot; served by
`ar.py serve` it refreshes itself from /data.json. Visual system: two-layer tokens
(--ar-*), a floating panel, pill controls, quiet tables, colour only for meaning.

Standard library only; runs on Python 3.9.
"""

import datetime
import glob
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ECHARTS_PATH = os.path.join(SCRIPT_DIR, "vendor", "echarts.min.js")
PATCH_CAP = 20000  # bytes of a round's patch embedded in the page; the rest stays on disk

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>@@TITLE@@ · autoresearch</title>
<style>
/* ===== token 层：取值与 hiwork-eval-web 的 --hw-* 一致，只改前缀。样式里不出现颜色字面量。 ===== */
:root{
  --ar-bg:#f8faff; --ar-surface:#ffffff; --ar-surface-sunken:#f3f6fa; --ar-surface-quiet:#fbfdff;
  --ar-fg:#0d253d; --ar-fg-muted:#63738a; --ar-fg-faint:#8e9aa8; --ar-border:#e3e8ee; --ar-border-strong:#d1d7e2;
  --ar-solid:#0b0c0f; --ar-accent:#533afd; --ar-accent-softer:#f4f0ff; --ar-link:#615ced; --ar-link-hover:#4444c7;
  --ar-success:#16a34a; --ar-success-bg:#eefbf3; --ar-warning:#b45f06; --ar-warning-bg:#fff8e6; --ar-warning-border:#f5d28b;
  --ar-danger:#c81e1e; --ar-danger-bg:#fff1f1; --ar-danger-border:#f4b8b8; --ar-neutral-bg:#f0f3f7;
  --ar-b4-bg:oklch(0.94 0.05 150); --ar-b4-fg:oklch(0.40 0.11 150);
  --ar-pos:oklch(0.50 0.13 150); --ar-neg:oklch(0.52 0.20 27);
  /* 图表只认 hex：和上面的语义色同值 */
  --ar-chart-line:#0d253d; --ar-chart-keep:#16a34a; --ar-chart-discard:#8e9aa8; --ar-chart-crash:#c81e1e; --ar-chart-error:#b45f06;
  --ar-chart-grid:#e3e8ee; --ar-chart-band:#f3f6fa; --ar-chart-band-alt:#eef1ff; --ar-chart-metric:#b9c9e6;
  --ar-font:'Inter Variable','PingFang SC','Microsoft YaHei','Noto Sans CJK SC',system-ui,-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif;
  --ar-font-mono:'Geist Mono','SFMono-Regular',Consolas,ui-monospace,monospace;
  --ar-text-note:12px; --ar-text-ctrl:13px; --ar-text-body:14px; --ar-text-sub:16px; --ar-text-section:20px; --ar-text-page:28px; --ar-text-num:40px; --ar-tracking:.4px;
  --ar-r-pill:999px; --ar-r-panel:24px; --ar-r-card:16px; --ar-r-cell:10px; --ar-r-sm:8px;
  --ar-s2:8px; --ar-s4:16px; --ar-s5:20px; --ar-s6:24px; --ar-s8:32px;
  --ar-card-pad:28px; --ar-section-gap:40px; --ar-row-h:58px; --ar-row-hover:rgba(13,37,61,.03);
  --ar-shadow-panel:0 8px 24px rgba(0,55,112,.08); --ar-ring-accent:0 0 0 3px rgba(83,58,253,.22);
  --ar-topbar-h:68px; --ar-gutter:24px; --ar-ease:cubic-bezier(.2,0,0,1); --ar-dur-fast:.15s;
}
/* ===== 基础层 ===== */
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;background:var(--ar-bg)}
body{color:var(--ar-fg);font:400 var(--ar-text-body)/22px var(--ar-font);letter-spacing:var(--ar-tracking);-webkit-font-smoothing:antialiased}
h1,h2,h3,h4,p,ul,ol,dl,dd,pre{margin:0;padding:0}
ul,ol{list-style:none}
button{font:inherit;letter-spacing:inherit;color:inherit;cursor:pointer;background:none;border:0;padding:0}
a{color:var(--ar-link);text-decoration:none}a:hover{color:var(--ar-link-hover)}
table{border-collapse:collapse;width:100%}
.t-page{font-size:var(--ar-text-page);line-height:38px;font-weight:600;letter-spacing:0}
.t-section{font-size:var(--ar-text-section);line-height:28px;font-weight:600;letter-spacing:.2px}
.t-sub{font-size:var(--ar-text-sub);line-height:24px;font-weight:600}
.t-ctrl{font-size:var(--ar-text-ctrl)}
.t-note{font-size:var(--ar-text-note);line-height:18px;color:var(--ar-fg-muted)}
.t-muted{color:var(--ar-fg-muted)}.t-faint{color:var(--ar-fg-faint)}
.t-mono{font-family:var(--ar-font-mono);letter-spacing:0}
.num{font-variant-numeric:tabular-nums;font-feature-settings:'tnum' 1;letter-spacing:0}
.num-xl{font-size:var(--ar-text-num);line-height:44px;font-weight:600;letter-spacing:-.02em}
.pos{color:var(--ar-pos)}.neg{color:var(--ar-neg)}
.clip{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hint{border-bottom:1px dashed var(--ar-border-strong);cursor:help}
/* ===== 外壳：顶栏 + 浮起面板 ===== */
.topbar{height:var(--ar-topbar-h);display:flex;align-items:center;gap:var(--ar-s4);padding:0 var(--ar-gutter)}
.brand{display:flex;align-items:center;gap:12px}
.brand-word{font-size:22px;font-weight:800;letter-spacing:-.2px;color:var(--ar-solid)}
.brand-v{width:1px;height:18px;background:var(--ar-border-strong);margin:0 4px}
.brand-sub{font-size:14px;font-weight:500;color:var(--ar-fg-muted)}
.spacer{flex:1}
.live{display:flex;align-items:center;gap:8px;font-size:var(--ar-text-ctrl);color:var(--ar-fg-muted)}
.live.is-off{color:var(--ar-warning)}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:var(--ar-success);animation:pulse 1.6s var(--ar-ease) infinite;flex:none}
.is-off .pulse-dot{background:var(--ar-warning);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.main{padding:0 var(--ar-gutter) var(--ar-gutter)}
.surface{background:var(--ar-surface);border:1px solid var(--ar-border);border-radius:var(--ar-r-panel);box-shadow:var(--ar-shadow-panel);padding:36px 40px 56px}
.surface>*{max-width:1240px;margin-left:auto;margin-right:auto}
/* ===== 控件 ===== */
.tag{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border-radius:var(--ar-r-pill);font-size:var(--ar-text-note);background:var(--ar-neutral-bg);color:var(--ar-fg-muted);white-space:nowrap;letter-spacing:.2px}
.tag-ok{background:var(--ar-success-bg);color:var(--ar-success)}
.tag-warn{background:var(--ar-warning-bg);color:var(--ar-warning)}
.tag-danger{background:var(--ar-danger-bg);color:var(--ar-danger)}
.tag-line{background:none;border:1px solid var(--ar-border-strong)}
.code{display:inline-block;font-family:var(--ar-font-mono);letter-spacing:0;font-size:var(--ar-text-note);line-height:20px;padding:0 7px;border-radius:6px;background:var(--ar-surface-sunken);color:var(--ar-fg);margin:2px 6px 2px 0}
.link{color:var(--ar-link);font-weight:500;cursor:pointer;font-size:inherit}
.link:hover{color:var(--ar-link-hover);text-decoration:underline;text-underline-offset:3px}
/* ===== 页头 / 区块 ===== */
.crumb{display:flex;align-items:center;gap:6px;font-size:var(--ar-text-ctrl);color:var(--ar-fg-muted);margin-bottom:6px}
.page-head{display:flex;align-items:flex-start;gap:var(--ar-s6);margin-bottom:var(--ar-s8)}
.page-head .grow{flex:1;min-width:0}
.title-row{display:flex;align-items:center;gap:12px}
.page-meta{display:flex;flex-wrap:wrap;gap:4px 18px;margin-top:8px;font-size:var(--ar-text-ctrl);color:var(--ar-fg-muted)}
.page-meta b{color:var(--ar-fg);font-weight:500}
.tabs{display:flex;gap:28px;border-bottom:1px solid var(--ar-border);margin-bottom:var(--ar-s8)}
.tabs button{position:relative;height:44px;display:inline-flex;align-items:center;gap:8px;font-size:15px;color:var(--ar-fg-muted)}
.tabs button:hover{color:var(--ar-fg)}
.tabs button.on{color:var(--ar-fg);font-weight:600}
.tabs button.on::after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:2px;border-radius:2px;background:var(--ar-accent)}
.section{margin-top:var(--ar-section-gap)}
.section-head{display:flex;align-items:center;gap:var(--ar-s4);margin-bottom:var(--ar-s5)}
/* ===== 卡片 / 表格 ===== */
.card{border:1px solid var(--ar-border);border-radius:var(--ar-r-card);background:var(--ar-surface);padding:var(--ar-card-pad)}
.grid-2{display:grid;grid-template-columns:1.15fr 1fr;gap:var(--ar-s5)}
.table th{height:40px;padding:0 16px;text-align:left;font-size:12px;font-weight:400;color:var(--ar-fg-muted);background:var(--ar-surface-sunken);white-space:nowrap}
.table th:first-child{border-radius:var(--ar-r-sm) 0 0 var(--ar-r-sm);padding-left:20px}
.table th:last-child{border-radius:0 var(--ar-r-sm) var(--ar-r-sm) 0}
.table td{height:var(--ar-row-h);padding:10px 16px;border-bottom:1px solid var(--ar-border);vertical-align:middle}
.table td:first-child{padding-left:20px}
.table tbody tr.is-link{cursor:pointer;transition:background var(--ar-dur-fast) var(--ar-ease)}
.table tbody tr.is-link:hover{background:var(--ar-row-hover)}
.table tbody tr.is-open{background:var(--ar-row-hover)}
.table .r{text-align:right}
.table-nest th{height:28px;font-size:11px}
.table-nest td{height:34px;padding:4px 12px;font-size:var(--ar-text-ctrl)}
.table-nest td:first-child{padding-left:12px}
.table-nest td.r{padding-left:18px;white-space:nowrap}
.kv{display:grid;grid-template-columns:96px 1fr;gap:10px 16px;font-size:var(--ar-text-ctrl)}
.kv dt{color:var(--ar-fg-muted)}.kv dd{color:var(--ar-fg);min-width:0;overflow-wrap:anywhere}
/* ===== 结论行 / 指标条 ===== */
.conclusion{display:flex;align-items:flex-start;gap:var(--ar-s8);margin-bottom:var(--ar-s6)}
.conclusion .divider{width:1px;align-self:stretch;background:var(--ar-border)}
.c-label{display:flex;align-items:center;gap:8px;font-size:var(--ar-text-note);color:var(--ar-fg-muted);margin-bottom:6px}
.c-sub{font-size:var(--ar-text-ctrl);color:var(--ar-fg-muted);margin-top:4px}
.arrow{display:flex;align-items:center;gap:14px;height:44px}
.arrow .from{font-size:22px;font-weight:500;color:var(--ar-fg-faint)}
.arrow .to{font-size:22px;font-weight:600}
.arrow .glyph{color:var(--ar-fg-faint)}
.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:var(--ar-s5)}
.stat .c-label{margin-bottom:4px}
.stat .v{font-size:22px;line-height:28px;font-weight:600;letter-spacing:-.01em}
.stat .v small{font-size:var(--ar-text-ctrl);font-weight:400;color:var(--ar-fg-muted);margin-left:4px;letter-spacing:.4px}
.stat .s{font-size:var(--ar-text-note);color:var(--ar-fg-muted);margin-top:2px}
/* ===== 例外才出现的行动条 ===== */
.action{display:flex;align-items:center;gap:14px;border:1px solid var(--ar-border);border-radius:var(--ar-r-card);padding:14px 20px;margin-bottom:var(--ar-s6)}
.action .ico{color:var(--ar-warning);font-size:16px;line-height:1}
.action.is-run .ico{color:var(--ar-success)}
.action.is-bad{border-color:var(--ar-danger-border)}
.action.is-bad .ico{color:var(--ar-danger)}
.action .grow{flex:1;min-width:0}
.action .t-note{margin-top:2px}
.action .bar{width:160px;height:6px;border-radius:var(--ar-r-pill);background:var(--ar-surface-sunken);overflow:hidden}
.action .bar>i{display:block;height:100%;background:var(--ar-accent);border-radius:inherit}
/* ===== 结局矩阵（一轮一格） ===== */
.matrix{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.cell{width:18px;height:18px;border-radius:5px;display:block;cursor:pointer;border:1px solid transparent;transition:transform var(--ar-dur-fast) var(--ar-ease)}
.cell:hover{transform:scale(1.2)}
.cell.keep{background:var(--ar-b4-bg);border-color:var(--ar-b4-bg)}
.cell.discard{background:var(--ar-neutral-bg);border-color:var(--ar-border)}
.cell.crash{background:var(--ar-danger-bg);border-color:var(--ar-danger-border)}
.cell.error{background:var(--ar-warning-bg);border-color:var(--ar-warning-border)}
.cell.base{background:var(--ar-surface);border-color:var(--ar-border-strong)}
.cell.is-open{box-shadow:var(--ar-ring-accent);border-color:var(--ar-accent)}
.legend{display:flex;gap:18px;font-size:var(--ar-text-note);color:var(--ar-fg-muted);margin-top:10px;flex-wrap:wrap;align-items:center}
.legend i{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:6px;vertical-align:-1px;border:1px solid transparent}
/* ===== 图表 ===== */
.ec{height:440px}
/* ===== 说明 / remaining / diff ===== */
.prose{white-space:pre-wrap;line-height:22px;color:var(--ar-fg)}
.prose.clipped{max-height:132px;overflow:hidden}
.list-rem li{position:relative;padding-left:16px;margin:6px 0;line-height:20px}
.list-rem li::before{content:'';position:absolute;left:2px;top:8px;width:5px;height:5px;border-radius:50%;background:var(--ar-fg-faint)}
pre.diff{font-family:var(--ar-font-mono);letter-spacing:0;font-size:12px;line-height:18px;background:var(--ar-surface-sunken);border-radius:var(--ar-r-cell);padding:12px 14px;overflow:auto;max-height:420px;white-space:pre}
pre.diff .a{display:block;background:var(--ar-success-bg);color:var(--ar-b4-fg)}
pre.diff .r{display:block;background:var(--ar-danger-bg);color:var(--ar-danger)}
pre.diff .h{display:block;color:var(--ar-link)}
pre.diff .m{display:block;color:var(--ar-fg-faint)}
pre.diff .p{display:block}
.reason{font-family:var(--ar-font-mono);letter-spacing:0;font-size:12px;line-height:18px;white-space:pre-wrap;background:var(--ar-danger-bg);border:1px solid var(--ar-danger-border);border-radius:var(--ar-r-cell);padding:10px 14px}
/* ===== 轮次表 ===== */
.rounds td.n{color:var(--ar-fg-muted);width:64px}
.rounds td.st{width:96px}
.rounds td.sc{width:120px;font-weight:600}
.rounds td.d{width:96px}
.rounds td.tm,.rounds td.cost{width:104px;color:var(--ar-fg-muted)}
.rounds td.nt{color:var(--ar-fg-muted);max-width:0}
.rounds td.chev{width:44px;color:var(--ar-fg-faint);text-align:center;transition:transform var(--ar-dur-fast) var(--ar-ease)}
.rounds tr.is-open td.chev{transform:rotate(90deg)}
.rounds tr.detail-row td{padding:0;height:auto;border-bottom:1px solid var(--ar-border)}
.detail{background:var(--ar-surface-sunken);border-radius:var(--ar-r-card);margin:8px 0 12px;padding:24px 28px 28px;display:grid;grid-template-columns:1.15fr 1fr;gap:var(--ar-s6)}
.detail .blk+.blk{margin-top:var(--ar-s5)}
.detail .t-sub{margin-bottom:10px}
.detail .table-nest th{background:var(--ar-surface)}
.foot{margin-top:56px;font-size:var(--ar-text-note);color:var(--ar-fg-faint)}
</style>
<script>@@ECHARTS@@</script>
</head><body>
<div id="app"></div>
<script id="ar-data" type="application/json">@@DATA@@</script>
<script>
let D = JSON.parse(document.getElementById('ar-data').textContent);
const LIVE = /^https?:$/.test(location.protocol);
const NET = {ok: LIVE, at: Date.now()};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const CHART = {line: css('--ar-chart-line'), keep: css('--ar-chart-keep'), discard: css('--ar-chart-discard'), crash: css('--ar-chart-crash'), error: css('--ar-chart-error'), grid: css('--ar-chart-grid'), band: css('--ar-chart-band'), bandAlt: css('--ar-chart-band-alt'), metric: css('--ar-chart-metric'), muted: css('--ar-fg-faint'), fg: css('--ar-fg'), surface: css('--ar-surface')};
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const isNum = v => typeof v === 'number' && isFinite(v);
const F = {
  score: v => !isNum(v) ? '—' : Number.isInteger(v) ? v.toLocaleString('en-US') : v.toLocaleString('en-US', {maximumFractionDigits: 4}),
  money: v => isNum(v) ? '$' + v.toFixed(2) : '—',
  dur: ms => { if (!isNum(ms)) return '—'; const s = Math.round(ms / 1000); if (s < 60) return s + ' 秒'; const m = Math.floor(s / 60), h = Math.floor(m / 60); if (h) return `${h} 小时 ${m % 60} 分`; return `${m} 分 ${String(s % 60).padStart(2, '0')} 秒`; },
  when: iso => iso ? iso.replace('T', ' ').slice(5, 16) : '—',
  ago: iso => { if (!iso) return '—'; const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000); if (s < 60) return Math.round(s) + ' 秒前'; if (s < 3600) return Math.round(s / 60) + ' 分钟前'; if (s < 86400) return (s / 3600).toFixed(1) + ' 小时前'; return Math.round(s / 86400) + ' 天前'; },
  num: v => isNum(v) ? v.toLocaleString('en-US') : '—',
  k: v => !isNum(v) ? '—' : v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : String(v),
  sha: s => s ? s.slice(0, 7) : '—',
};
const median = xs => { const a = xs.filter(isNum).sort((p, q) => p - q); if (!a.length) return null; const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
const sum = xs => xs.filter(isNum).reduce((a, b) => a + b, 0);
const MIN = () => D.cfg.direction === 'min';
const STOP = {max_rounds: ['达到 max_rounds', 'max_rounds'], consecutive_discards: ['连续 discard 到上限', 'max_consecutive_discards'], consecutive_errors: ['连续 error 到上限', 'max_consecutive_errors'], target_score: ['达到 target_score', 'target_score'], 'budget.minutes': ['用完 budget.minutes', 'budget.minutes'], 'budget.tokens': ['用完 budget.tokens', 'budget.tokens']};
const TAG = {keep: 'tag-ok', discard: 'tag', crash: 'tag-danger', error: 'tag-warn'};

const UI_KEY = 'ar-report:' + D.cfg.name;
const UI = JSON.parse(localStorage.getItem(UI_KEY) || '{"tab":0,"open":[]}');
const save = () => localStorage.setItem(UI_KEY, JSON.stringify(UI));

const runOf = s => (D.run && D.run.running && D.run.subject === s.subject) ? D.run : {};
const delta = c => (isNum(c.score) && isNum(c.best_before)) ? c.score - c.best_before : null;
const better = d => MIN() ? d < 0 : d > 0;
const fmtDelta = d => d === null ? '—' : d === 0 ? '±0' : (d > 0 ? '+' : '−') + F.score(Math.abs(d));
const dcls = d => d === null || d === 0 ? 't-faint' : better(d) ? 'pos' : 'neg';
const prevBest = (s, c) => { let p = null; for (const x of s.checkpoints) { if (x.n >= c.n) break; if (x.status === 'keep' && x.version === c.version && isNum(x.score)) p = x; } return p; };
function flat(obj, pre, out) { out = out || {}; if (obj && typeof obj === 'object' && !Array.isArray(obj)) { for (const k of Object.keys(obj)) flat(obj[k], pre ? pre + '.' + k : k, out); } else if (isNum(obj)) out[pre] = obj; return out; }
const firstLine = (t, n) => { const l = String(t || '').split('\n').find(x => x.trim()) || ''; return l.length > n ? l.slice(0, n) + '…' : l; };
const tagOf = c => c.n === 0 ? '<span class="tag tag-line">基线</span>' : `<span class="tag ${TAG[c.status]}">${c.status}</span>`;

// ---------------------------------------------------------------- 外壳
function liveLabel() {
  if (!LIVE) return `<span class="live">静态 · 生成于 ${F.when(D.generated)}<span class="t-faint">· 用 ar serve 可实时查看</span></span>`;
  if (!NET.ok) return `<span class="live is-off"><span class="pulse-dot"></span>连接已断开<span class="t-faint">· 最近更新 <span id="live-ago">${F.ago(new Date(NET.at).toISOString())}</span></span></span>`;
  return `<span class="live"><span class="pulse-dot"></span>实时 · <span id="live-ago">${F.ago(new Date(NET.at).toISOString())}</span></span>`;
}
function topbar() {
  return `<div class="topbar"><div class="brand"><span class="brand-word">autoresearch</span><span class="brand-v"></span><span class="brand-sub">${esc(D.cfg.name)}</span></div><div class="spacer"></div><span id="live">${liveLabel()}</span></div>`;
}
function pageHead(s) {
  const idx = s.index, run = runOf(s);
  const state = run.running ? '<span class="tag tag-ok">运行中</span>' : idx.stopped_reason ? '<span class="tag tag-warn">已停止</span>' : '<span class="tag">空闲</span>';
  const t = idx.totals || {};
  return `<div class="page-head"><div class="grow"><div class="crumb">研究 ${esc(D.cfg.name)}</div>
    <div class="title-row"><h1 class="t-page">${esc(s.subject)}</h1>${state}${(s.depends_on || []).length ? `<span class="tag tag-line">依赖 ${s.depends_on.map(esc).join('、')}</span>` : ''}</div>
    ${D.cfg.description ? `<div class="page-meta"><span>${esc(D.cfg.description)}</span></div>` : ''}
    <div class="page-meta"><span>harness <b>${esc(s.harness || '—')}</b></span><span><b>${t.checkpoints || 0}</b> 轮</span><span>打分器 <b>v${esc(idx.version || '?')}</b></span><span>最近更新 <b>${F.ago(idx.updated_at)}</b></span><span class="t-faint">账本 ${esc(D.cfg.ar_dir)}</span></div></div></div>`;
}
function tabs() {
  if (D.states.length < 2) return '';
  return `<div class="tabs">${D.states.map((s, i) => { const run = runOf(s); const st = run.running ? '运行中' : s.index.stopped_reason ? '已停' : '空闲'; return `<button class="${i === UI.tab ? 'on' : ''}" data-tab="${i}">${esc(s.subject)}<span class="t-note">${st}${(s.depends_on || []).length ? ' · 依赖 ' + s.depends_on.map(esc).join('、') : ''}</span></button>`; }).join('')}</div>`;
}
// ---------------------------------------------------------------- 例外才出现的行动条
function action(s) {
  const idx = s.index, run = runOf(s), lim = s.limits || {};
  const cps = s.checkpoints, last = cps[cps.length - 1];
  const out = [];
  if (run.running && run.round_started) {
    const med = median(cps.filter(c => c.n > 0).map(c => c.timings_ms && c.timings_ms.agent));
    const age = Date.now() - Date.parse(run.round_started);
    const stale = !LIVE && age > ((s.timeout_sec || 1800) + 120) * 1000;
    if (stale) out.push(`<div class="action is-bad"><span class="ico">⚑</span><div class="grow"><div>第 #${run.round} 轮开始于 ${F.ago(run.round_started)}，超过了 timeout_sec，之后没有更新</div><div class="t-note">上次 run 可能没有正常结束；用 ar status 确认，或重新生成报告</div></div></div>`);
    else out.push(`<div class="action is-run"><span class="ico">●</span><div class="grow"><div>第 <b>#${run.round}</b> 轮进行中，已 <b class="num" id="elapsed" data-since="${esc(run.round_started)}" data-med="${med || 0}">${F.dur(age)}</b>${med >= 1000 ? ` <span class="t-muted">· 每轮中位 ${F.dur(med)}</span>` : ''}</div><div class="t-note">${last ? `上一轮 #${last.n} ${last.status}${isNum(last.score) ? '，' + F.score(last.score) : ''}，${F.ago(last.at)}` : '这是第一轮'}</div></div><div class="bar"><i id="elapsed-bar" style="width:${med ? Math.min(100, age / med * 100).toFixed(0) : 0}%"></i></div></div>`);
  } else if (run.running) {
    out.push(`<div class="action is-run"><span class="ico">●</span><div class="grow"><div>run 已启动，正在准备第一轮</div></div></div>`);
  } else if (idx.stopped_reason) {
    const [why, key] = STOP[idx.stopped_reason] || [idx.stopped_reason, null];
    const n = idx.stopped_reason === 'consecutive_discards' ? `${idx.consecutive_discards} / ${lim.max_consecutive_discards}` : idx.stopped_reason === 'consecutive_errors' ? `${idx.consecutive_errors} / ${lim.max_consecutive_errors}` : idx.stopped_reason === 'max_rounds' ? `${idx.totals.checkpoints} / ${lim.max_rounds}` : '';
    out.push(`<div class="action"><span class="ico">⚑</span><div class="grow"><div>已停止：${why}${n ? `（${n}）` : ''}</div><div class="t-note">${key ? `调高 research.json 里的 <span class="t-mono">${key}</span>，再次 run 即可继续` : ''}</div></div></div>`);
  }
  if (s.scorer_changed_since_best) out.push(`<div class="action"><span class="ico">⚑</span><div class="grow"><div>打分器在最佳轮次之后被修改过</div><div class="t-note">下次 run 会先在 HEAD 上重新测一次基线；已有的 checkpoint 不变</div></div></div>`);
  if ((s.unreadable || []).length) out.push(`<div class="action is-bad"><span class="ico">⚑</span><div class="grow"><div>账本里有 ${s.unreadable.length} 个 checkpoint 文件无法解析</div><div class="t-note t-mono">${s.unreadable.map(esc).join('<br>')}</div></div></div>`);
  return out.join('');
}
// ---------------------------------------------------------------- 结论行 + 指标条
function conclusion(s) {
  const idx = s.index;
  const cps = s.checkpoints, base = cps.find(c => c.n === 0 && isNum(c.score)), best = cps.find(c => c.id === idx.best_id);
  const keeps = cps.filter(c => c.status === 'keep' && c.n > 0), lastKeep = keeps[keeps.length - 1];
  const rel = base && best && base.score ? (best.score - base.score) / Math.abs(base.score) : null;
  const rounds = cps.filter(c => c.n > 0), t = idx.totals || {};
  const cost = sum(rounds.map(c => c.harness && c.harness.cost_usd)), time = sum(rounds.map(c => c.timings_ms && (c.timings_ms.agent || 0) + (c.timings_ms.gate || 0) + (c.timings_ms.score || 0)));
  const inTok = sum(rounds.map(c => c.usage && (c.usage.input || 0) + (c.usage.cache_read || 0) + (c.usage.cache_write || 0))), outTok = sum(rounds.map(c => c.usage && c.usage.output));
  const remaining = best ? (best.remaining || []).length : null;
  return `<div class="conclusion">
    <div><div class="c-label"><span class="hint" title="同一打分器版本内最好的一轮">最佳分数</span><span class="tag">${MIN() ? '越小越好' : '越大越好'}</span></div><div class="num num-xl">${F.score(idx.best)}</div><div class="c-sub">${best ? `来自 #${best.n}` : '尚无评分'}${lastKeep ? `，最近一次 keep 在 #${lastKeep.n}（<span class="${dcls(delta(lastKeep))}">${fmtDelta(delta(lastKeep))}</span>）` : best ? '，基线之后尚无 keep' : ''}</div></div>
    <div class="divider"></div>
    <div><div class="c-label"><span class="hint" title="基线 #0 是 run 开始前对 HEAD 直接评分的结果">基线 → 最佳</span></div><div class="arrow num"><span class="from">${base ? F.score(base.score) : '—'}</span><span class="glyph">→</span><span class="to">${F.score(idx.best)}</span></div><div class="c-sub">${rel === null ? '' : `较基线 <span class="${better(rel) ? 'pos' : 'neg'}">${rel < 0 ? '降' : '升'} ${(Math.abs(rel) * 100).toFixed(1)}%</span>`}</div></div>
    <div class="divider"></div>
    <div><div class="c-label"><span class="hint" title="打分器在最佳轮次输出的 remaining 列表：按当前评分标准尚未达成的事项">待改进项</span></div><div class="num num-xl">${remaining === null ? '—' : `<a class="link" data-scroll="rem-card" style="color:inherit">${remaining}</a>`}<span class="t-ctrl t-muted" style="margin-left:6px;font-weight:400;letter-spacing:.4px">项</span></div><div class="c-sub">${remaining === null ? '' : remaining === 0 ? '打分器没有列出待改进项' : `打分器在 #${best.n} 列出，点数字查看`}</div></div>
  </div>
  <div class="stats">
    <div class="stat"><div class="c-label"><span class="hint" title="含 #0 基线">轮次</span></div><div class="v num">${t.checkpoints || 0}</div><div class="s">${t.keep || 0} keep · ${t.discard || 0} discard${t.crash ? ' · ' + t.crash + ' crash' : ''}${t.error ? ' · ' + t.error + ' error' : ''}</div></div>
    <div class="stat"><div class="c-label"><span class="hint" title="连续几轮没有超过最佳；到 max_consecutive_discards 就停">连续 discard</span></div><div class="v num">${idx.consecutive_discards || 0}<small>/ ${(s.limits || {}).max_consecutive_discards || '∞'}</small></div><div class="s">${idx.consecutive_errors ? `连续 error ${idx.consecutive_errors}` : '无 error'}</div></div>
    <div class="stat"><div class="c-label"><span class="hint" title="Claude Code 按 Anthropic 价格的估算，不是账单">费用</span></div><div class="v num">${F.money(cost)}</div><div class="s">中位 ${F.money(median(rounds.map(c => c.harness && c.harness.cost_usd)))} / 轮</div></div>
    <div class="stat"><div class="c-label"><span class="hint" title="agent + gate + score 之和">耗时</span></div><div class="v num">${F.dur(time)}</div><div class="s">agent 中位 ${F.dur(median(rounds.map(c => c.timings_ms && c.timings_ms.agent)))} / 轮</div></div>
    <div class="stat"><div class="c-label"><span class="hint" title="输入含缓存读写">Token</span></div><div class="v num">${F.k(outTok)}<small>输出</small></div><div class="s">输入 ${F.k(inTok)}</div></div>
  </div>`;
}
// ---------------------------------------------------------------- 结局矩阵
function matrix(s) {
  const cells = s.checkpoints.map(c => `<a class="cell ${c.n === 0 ? 'base' : c.status} ${UI.open.includes(c.id) ? 'is-open' : ''}" data-go="${esc(c.id)}" title="#${c.n} ${c.n === 0 ? '基线' : c.status}${isNum(c.score) ? ' · ' + F.score(c.score) : ''}${c.n > 0 && delta(c) !== null ? '（' + fmtDelta(delta(c)) + '）' : ''}"></a>`).join('');
  return `<div class="section"><div class="section-head"><h2 class="t-section">每轮结局</h2><span class="t-note">一格一轮，点击查看</span></div><div class="matrix">${cells}</div>
    <div class="legend"><span><i class="cell keep"></i>keep</span><span><i class="cell discard"></i>discard</span><span><i class="cell crash"></i>crash</span><span><i class="cell error"></i>error</span><span><i class="cell base"></i>基线</span></div></div>`;
}
// ---------------------------------------------------------------- 图表
function bands(cps) { const out = []; let cur = null; cps.forEach(c => { const v = c.version || (cur && cur.version); if (!cur || (c.version && c.version !== cur.version)) { cur = {version: v, from: c.n, to: c.n}; out.push(cur); } else cur.to = c.n; }); return out; }
function chartSection(s, si) {
  const canLog = s.checkpoints.every(c => !isNum(c.score) || c.score > 0);
  return `<div class="section"><div class="section-head"><h2 class="t-section">分数走势</h2><span class="t-note">${canLog ? '对数轴；' : ''}曲线连接 keep 的轮次，下方为每轮耗时与费用；悬停看摘要，点击定位到该轮</span></div><div class="ec" id="chart-${si}"></div></div>`;
}
let EC = null;
function mountChart(s, si) {
  const el = document.getElementById('chart-' + si); if (!el || !window.echarts) return;
  if (EC) { EC.dispose(); EC = null; }
  const cps = s.checkpoints, maxN = Math.max(1, ...cps.map(c => c.n));
  const scored = cps.filter(c => isNum(c.score)).map(c => c.score);
  if (!scored.length) { el.innerHTML = '<p class="t-muted">还没有评分。</p>'; return; }
  const useLog = scored.every(v => v > 0);
  const byId = Object.fromEntries(cps.map(c => [c.id, c]));
  const groups = []; let cur = null;
  cps.forEach(c => { if (c.status !== 'keep' || !isNum(c.score)) return; if (!cur || cur.version !== c.version) { cur = {version: c.version, pts: []}; groups.push(cur); } cur.pts.push([c.n, c.score, c.id]); });
  const areas = bands(cps).map((b, i) => [{xAxis: b.from - 0.5, name: b.version ? '打分器 v' + b.version : '', itemStyle: {color: i % 2 ? CHART.band : CHART.bandAlt, opacity: 0.9}}, {xAxis: b.to + 0.5}]);
  const noScore = cps.filter(c => !isNum(c.score)).map(c => ({xAxis: c.n, lineStyle: {color: c.status === 'crash' ? CHART.crash : CHART.error, type: 'dashed', width: 1.5}, label: {formatter: '#' + c.n + ' ' + c.status, color: c.status === 'crash' ? CHART.crash : CHART.error, position: 'insideEndTop', fontSize: 11}}));
  const series = groups.map((g, i) => ({name: 'keep', type: 'line', data: g.pts, smooth: 0.45, smoothMonotone: 'x', symbol: 'circle', symbolSize: 9, lineStyle: {color: CHART.line, width: 1.8}, itemStyle: {color: p => p.data[0] === 0 ? CHART.muted : CHART.keep, borderColor: CHART.surface, borderWidth: 1.5}, emphasis: {scale: 1.5}, z: 3,
    markArea: i === 0 ? {silent: true, label: {position: 'insideTopRight', color: CHART.muted, fontSize: 11, distance: 6}, data: areas} : undefined,
    markLine: i === 0 ? {silent: true, symbol: 'none', data: noScore} : undefined}));
  if (!groups.length) series.push({type: 'line', data: [], markArea: {silent: true, data: areas}, markLine: {silent: true, symbol: 'none', data: noScore}});
  series.push({name: 'discard', type: 'scatter', data: cps.filter(c => c.status === 'discard' && isNum(c.score)).map(c => [c.n, c.score, c.id]), symbol: 'circle', symbolSize: 9, itemStyle: {color: CHART.surface, borderColor: CHART.discard, borderWidth: 1.6}, emphasis: {scale: 1.5}, z: 4});
  const rounds = cps.filter(c => c.n > 0);
  const medLine = fmt => ({silent: true, symbol: 'none', lineStyle: {color: CHART.muted, type: 'dashed', width: 1}, label: {position: 'insideEndTop', fontSize: 11, color: CHART.muted, formatter: p => '中位 ' + fmt(p.value)}, data: [{type: 'median'}]});
  series.push({name: '耗时', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: rounds.map(c => [c.n, c.timings_ms && c.timings_ms.agent, c.id]), itemStyle: {color: CHART.metric, borderRadius: 2}, barMaxWidth: 12, markLine: medLine(F.dur)});
  series.push({name: '费用', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: rounds.map(c => [c.n, c.harness && c.harness.cost_usd, c.id]), itemStyle: {color: CHART.metric, borderRadius: 2}, barMaxWidth: 12, markLine: medLine(F.money)});
  const xAxis = (i, show) => ({type: 'value', min: -0.5, max: maxN + 0.5, minInterval: 1, gridIndex: i, axisLine: {show: false}, axisTick: {show: false}, splitLine: {show: false}, axisLabel: {show, color: CHART.muted, fontSize: 11, formatter: v => Number.isInteger(v) && v >= 0 && v <= maxN ? '#' + v : ''}});
  const tip = p => { const c = byId[p.data && p.data[2]]; if (!c) return ''; const d = delta(c);
    return `<b>#${c.n} ${c.n === 0 ? '基线' : c.status}</b>${isNum(c.score) ? ' · ' + F.score(c.score) : ''}${c.n > 0 && d !== null ? '（' + fmtDelta(d) + '）' : ''}<div style="opacity:.7">${F.dur(c.timings_ms && c.timings_ms.agent)} · ${F.money(c.harness && c.harness.cost_usd)}${(c.changed_files || []).length ? ' · 改了 ' + c.changed_files.length + ' 个文件' : ''}</div>${c.note ? '<div style="max-width:380px;white-space:normal;margin-top:4px">' + esc(firstLine(c.note, 160)) + '</div>' : ''}${c.reason ? '<div style="max-width:380px;white-space:normal;margin-top:4px">' + esc(firstLine(c.reason, 120)) + '</div>' : ''}`; };
  const lo = Math.min(...scored), hi = Math.max(...scored);
  EC = echarts.init(el, null, {renderer: 'svg'});
  EC.setOption({
    animation: false, textStyle: {fontFamily: 'inherit'},
    grid: [{top: 30, left: 76, right: 24, height: 250}, {top: 316, left: 76, right: 24, height: 44}, {top: 374, left: 76, right: 24, height: 44}],
    xAxis: [xAxis(0, false), xAxis(1, false), xAxis(2, true)],
    yAxis: [Object.assign({type: useLog ? 'log' : 'value', scale: true, gridIndex: 0, splitLine: {lineStyle: {color: CHART.grid}}, minorSplitLine: {show: useLog, lineStyle: {color: CHART.band}}, axisLabel: {color: CHART.muted, fontSize: 11, formatter: v => F.score(v)}}, useLog && lo < hi ? {logBase: 2, min: lo / 1.05, max: hi * 1.05} : {}),
            {type: 'value', gridIndex: 1, name: '耗时', nameLocation: 'middle', nameGap: 48, nameTextStyle: {color: CHART.muted, fontSize: 11}, splitLine: {show: false}, axisLabel: {show: false}, axisLine: {show: false}},
            {type: 'value', gridIndex: 2, name: '费用', nameLocation: 'middle', nameGap: 48, nameTextStyle: {color: CHART.muted, fontSize: 11}, splitLine: {show: false}, axisLabel: {show: false}, axisLine: {show: false}}],
    tooltip: {trigger: 'item', formatter: tip, backgroundColor: CHART.fg, borderWidth: 0, textStyle: {color: CHART.surface, fontSize: 12}, extraCssText: 'border-radius:12px;padding:10px 14px;box-shadow:0 2px 8px rgba(13,37,61,.1)'},
    series});
  EC.on('click', p => { if (p.data && p.data[2]) openRow(p.data[2]); });
}
window.addEventListener('resize', () => EC && EC.resize());
// ---------------------------------------------------------------- 最近一轮 / 待改进项 / 最佳构成
function kv(obj) {
  if (obj === null || obj === undefined) return '<span class="t-faint">—</span>';
  if (typeof obj !== 'object') return esc(isNum(obj) ? F.score(obj) : String(obj));
  if (Array.isArray(obj)) return esc(obj.map(v => typeof v === 'object' ? JSON.stringify(v) : v).join('、'));
  const keys = Object.keys(obj); if (!keys.length) return '<span class="t-faint">空</span>';
  const tabular = keys.length > 1 && keys.every(k => obj[k] && typeof obj[k] === 'object' && !Array.isArray(obj[k])) && (() => { const cols = Object.keys(obj[keys[0]]); return keys.every(k => Object.keys(obj[k]).join() === cols.join()); })();
  if (tabular) { const cols = Object.keys(obj[keys[0]]); return `<table class="table table-nest"><thead><tr><th></th>${cols.map(c => `<th class="r">${esc(c)}</th>`).join('')}</tr></thead><tbody>${keys.map(k => `<tr><td class="t-mono">${esc(k)}</td>${cols.map(c => `<td class="r num">${kv(obj[k][c])}</td>`).join('')}</tr>`).join('')}</tbody></table>`; }
  return `<table class="table table-nest"><tbody>${keys.map(k => `<tr><td class="t-muted">${esc(k)}</td><td class="${isNum(obj[k]) ? 'r num' : ''}">${kv(obj[k])}</td></tr>`).join('')}</tbody></table>`;
}
function nowAndRemaining(s) {
  const cps = s.checkpoints, last = [...cps].reverse().find(c => c.n > 0), best = cps.find(c => c.id === s.index.best_id);
  let left = '<p class="t-muted">尚未运行过 agent。</p>';
  if (last) {
    left = `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">${tagOf(last)}<span class="num" style="font-weight:600">${isNum(last.score) ? F.score(last.score) : '未评分'}</span>${isNum(last.score) ? `<span class="${dcls(delta(last))} num">${fmtDelta(delta(last))}</span>` : ''}<span class="t-note">${F.dur(last.timings_ms && last.timings_ms.agent)} · ${F.money(last.harness && last.harness.cost_usd)} · ${F.ago(last.at)}</span></div>
      <div style="margin-top:12px">${(last.changed_files || []).length ? last.changed_files.map(f => `<span class="code">${esc(f)}</span>`).join('') : '<span class="t-note">没有改动文件</span>'}</div>
      ${last.reason ? `<div class="reason" style="margin-top:12px">${esc(last.reason)}</div>` : ''}
      <div class="prose clipped" id="lastnote" style="margin-top:12px">${esc(last.note || 'agent 没有留下说明')}</div><button class="link t-ctrl" data-unclip="lastnote" style="margin-top:8px">展开全文</button>`;
  }
  const rem = (best && best.remaining) || [];
  const right = !best ? '<p class="t-muted">尚无最佳轮次。</p>' : !rem.length ? '<p class="t-muted">打分器没有列出待改进项。remaining 为空时，下一轮没有可执行的目标；可以调整评分标准，或结束这项研究。</p>' : `<ul class="list-rem">${rem.slice(0, 8).map(r => `<li>${esc(r)}</li>`).join('')}</ul>${rem.length > 8 ? `<button class="link t-ctrl" data-more="rem-all" style="margin-top:8px">展开全部 ${rem.length} 项</button><ul class="list-rem" id="rem-all" hidden>${rem.slice(8).map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}`;
  return `<div class="section grid-2"><div class="card"><h3 class="t-sub" style="margin-bottom:14px">最近一轮${last ? ` <span class="t-note" style="font-weight:400">#${last.n}</span>` : ''}</h3>${left}</div><div class="card" id="rem-card"><h3 class="t-sub" style="margin-bottom:14px">待改进项${best ? ` <span class="t-note" style="font-weight:400">打分器在 #${best.n} 输出的 remaining · ${rem.length} 项</span>` : ''}</h3>${right}</div></div>`;
}
function bestPanel(s) { const best = s.checkpoints.find(c => c.id === s.index.best_id); if (!best) return ''; return `<div class="section"><div class="section-head"><h2 class="t-section">最佳分数的构成</h2><span class="t-note">打分器在 #${best.n} 输出的 details</span></div>${kv(best.details)}</div>`; }
// ---------------------------------------------------------------- 轮次表
function diffHtml(txt) { return txt.replace(/\n$/, '').split('\n').map(l => { const e = esc(l) || ' '; const k = (l.startsWith('+++') || l.startsWith('---') || l.startsWith('diff ') || l.startsWith('index ')) ? 'm' : l.startsWith('@@') ? 'h' : l.startsWith('+') ? 'a' : l.startsWith('-') ? 'r' : 'p'; return `<span class="${k}">${e}</span>`; }).join(''); }
function detail(s, c) {
  const pb = prevBest(s, c), tm = c.timings_ms || {}, u = c.usage || {}, h = c.harness || {};
  let changes;
  if (c.n === 0) changes = '<p class="t-muted">基线：对 HEAD 直接评分，未运行 agent。</p>';
  else if (c.patch) changes = `<div style="margin-bottom:10px">${(c.changed_files || []).map(f => `<span class="code">${esc(f)}</span>`).join('')}</div><pre class="diff">${diffHtml(c.patch)}</pre>${c.patch_truncated ? `<p class="t-note" style="margin-top:6px">仅显示前 20 KB；完整 patch 在 ${esc(c.artifacts)}/changes.patch</p>` : ''}`;
  else changes = `<p class="t-muted">${(c.changed_files || []).length ? '改动了 ' + c.changed_files.map(esc).join('、') + '；这一轮没有保存 patch' : '没有改动文件'}</p>`;
  let comp;
  if (isNum(c.score)) {
    const a = flat(c.details), b = pb ? flat(pb.details) : {};
    const rows = Object.keys(a).filter(k => !pb || a[k] !== b[k]).map(k => `<tr><td class="t-mono">${esc(k)}</td><td class="r num t-faint">${pb ? F.score(b[k]) : ''}</td><td class="r num" style="font-weight:600">${F.score(a[k])}</td><td class="r num ${pb && isNum(b[k]) ? dcls(a[k] - b[k]) : ''}">${pb && isNum(b[k]) ? fmtDelta(a[k] - b[k]) : ''}</td></tr>`);
    comp = rows.length ? `<table class="table table-nest"><thead><tr><th></th><th class="r">${pb ? '上一个最佳 #' + pb.n : ''}</th><th class="r">本轮 #${c.n}</th><th class="r">Δ</th></tr></thead><tbody>${rows.join('')}</tbody></table>` : Object.keys(a).length ? '<p class="t-muted">与上一个最佳的 details 相同。</p>' : '<p class="t-muted">打分器没有输出数值型的 details。</p>';
  } else comp = `<div class="reason">${esc(c.reason || '未评分')}</div><p class="t-note" style="margin-top:8px">详情见 gate.out / score.err / harness.err，位于 ${esc(c.artifacts)}/</p>`;
  const sub = Object.keys(tm).filter(k => !['agent', 'gate', 'score'].includes(k)).map(k => `${esc(k)} ${F.dur(tm[k])}`).join(' · ');
  const proc = `<dl class="kv"><dt>阶段耗时</dt><dd>agent ${F.dur(tm.agent)} · gate ${F.dur(tm.gate)} · score ${F.dur(tm.score)}${sub ? '<br><span class="t-note">打分器子阶段 ' + sub + '</span>' : ''}</dd>
    <dt>token</dt><dd>输入 ${F.num(u.input)} · 输出 ${F.num(u.output)}<br><span class="t-note">缓存读 ${F.num(u.cache_read)} · 缓存写 ${F.num(u.cache_write)}</span></dd>
    <dt>harness</dt><dd>${esc(h.type || '—')}${h.model ? ' · ' + esc(h.model) : ''}${isNum(h.turns) ? ' · ' + h.turns + ' turn' : ''} · ${F.money(h.cost_usd)}${h.cut_off ? ' · 被 ' + esc(h.cut_off) + ' 截断' : ''}</dd>
    <dt>git</dt><dd><span class="t-mono">${F.sha(c.commit)}</span>${c.reverted_by ? ' · 已撤回 <span class="t-mono">' + F.sha(c.reverted_by) + '</span>' : ''} · 打分器 v${esc(c.version || '—')}</dd>
    <dt>产物目录</dt><dd><a href="file://${esc(c.artifacts)}/" class="t-mono" style="font-size:12px">${esc(c.artifacts)}/</a></dd></dl>`;
  return `<div class="detail"><div><div class="blk"><h4 class="t-sub">agent 说明</h4><div class="prose">${esc(c.note || 'agent 没有留下说明')}</div></div><div class="blk"><h4 class="t-sub">改动</h4>${changes}</div></div>
    <div><div class="blk"><h4 class="t-sub">分数构成${pb ? `<span class="t-note" style="font-weight:400;margin-left:8px">相对上一个最佳 #${pb.n}</span>` : ''}</h4>${comp}</div><div class="blk"><h4 class="t-sub">执行信息</h4>${proc}</div></div></div>`;
}
function rounds(s) {
  const rows = [...s.checkpoints].reverse().map(c => {
    const d = delta(c), open = UI.open.includes(c.id);
    return `<tr class="is-link ${open ? 'is-open' : ''}" id="row-${esc(c.id)}" data-id="${esc(c.id)}"><td class="n num">#${c.n}</td><td class="st">${tagOf(c)}</td><td class="sc r num">${F.score(c.score)}</td><td class="d r num ${dcls(d)}">${c.n === 0 ? '' : fmtDelta(d)}</td><td class="tm r num">${F.dur(c.timings_ms && c.timings_ms.agent)}</td><td class="cost r num">${F.money(c.harness && c.harness.cost_usd)}</td><td class="nt"><div class="clip">${esc(c.reason ? firstLine(c.reason, 160) : c.n === 0 ? '基线：对 HEAD 直接评分，未运行 agent' : firstLine(c.note, 160))}</div></td><td class="chev">›</td></tr>${open ? `<tr class="detail-row"><td colspan="8">${detail(s, c)}</td></tr>` : ''}`;
  }).join('');
  return `<div class="section rounds"><div class="section-head"><h2 class="t-section">全部轮次</h2><span class="t-note">最新在前；点击展开说明、改动与分数构成</span></div>
    <table class="table"><thead><tr><th>轮次</th><th>结局</th><th class="r">分数</th><th class="r">Δ</th><th class="r">agent</th><th class="r">费用</th><th>说明 / 原因</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
// ---------------------------------------------------------------- 渲染 / 交互 / 实时
function render() {
  if (!D.states.length) { document.getElementById('app').innerHTML = topbar() + `<div class="main"><div class="surface"><p class="t-muted">账本里还没有任何 subject。</p></div></div>`; return; }
  const si = Math.min(UI.tab, D.states.length - 1), s = D.states[si];
  document.getElementById('app').innerHTML = topbar() + `<div class="main"><div class="surface">` + pageHead(s) + tabs() + action(s) + conclusion(s) + matrix(s) + chartSection(s, si) + nowAndRemaining(s) + bestPanel(s) + rounds(s) +
    `<p class="foot">所有数字来自账本的 checkpoint 文件。每轮的 prompt、harness 输出、gate 与打分器输出、patch 保存在 artifacts/&lt;subject&gt;/&lt;checkpoint&gt;/。</p></div></div>`;
  mountChart(s, si);
}
function openRow(id) { if (!UI.open.includes(id)) UI.open.push(id); save(); render(); const el = document.getElementById('row-' + id); if (el) el.scrollIntoView({behavior: 'smooth', block: 'center'}); }
document.addEventListener('click', e => {
  const t = e.target.closest('[data-go],[data-tab],[data-more],[data-unclip],[data-scroll],tr.is-link');
  if (!t) return;
  if (t.dataset.scroll) { const el = document.getElementById(t.dataset.scroll); if (el) el.scrollIntoView({behavior: 'smooth', block: 'center'}); return; }
  if (t.dataset.go) return openRow(t.dataset.go);
  if (t.dataset.tab !== undefined) { UI.tab = Number(t.dataset.tab); save(); return render(); }
  if (t.dataset.more) { document.getElementById(t.dataset.more).hidden = false; t.remove(); return; }
  if (t.dataset.unclip) { document.getElementById(t.dataset.unclip).classList.remove('clipped'); t.remove(); return; }
  if (e.target.closest('a[href]')) return;
  const id = t.dataset.id; const i = UI.open.indexOf(id); if (i >= 0) UI.open.splice(i, 1); else UI.open.push(id); save(); render();
});
setInterval(() => {
  const el = document.getElementById('elapsed');
  if (el) { const ms = Date.now() - Date.parse(el.dataset.since); el.textContent = F.dur(ms); const med = Number(el.dataset.med); const bar = document.getElementById('elapsed-bar'); if (bar && med) bar.style.width = Math.min(100, ms / med * 100).toFixed(0) + '%'; }
  const la = document.getElementById('live-ago'); if (la) la.textContent = F.ago(new Date(NET.at).toISOString());
}, 1000);
const fingerprint = d => JSON.stringify([d.run, d.states.map(s => [s.index, s.checkpoints.length, s.scorer_changed_since_best, s.unreadable])]);
async function poll() {
  let changed = false;
  try {
    const r = await fetch('data.json', {cache: 'no-store'});
    if (!r.ok) throw new Error(r.status);
    const next = await r.json();
    changed = fingerprint(next) !== fingerprint(D) || !NET.ok;
    D = next; NET.ok = true; NET.at = Date.now();
  } catch (err) { changed = NET.ok; NET.ok = false; }
  if (changed) render(); else { const el = document.getElementById('live'); if (el) el.innerHTML = liveLabel(); }
  setTimeout(poll, D.run && D.run.running ? 5000 : 10000);
}
render();
if (LIVE) setTimeout(poll, 5000);
</script></body></html>
"""


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_text(path, default=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


_ECHARTS = None


def echarts_source():
    """The vendored ECharts build, read once. Missing file → the page still renders; only
    the chart is replaced by a sentence saying what is missing."""
    global _ECHARTS
    if _ECHARTS is None:
        src = read_text(ECHARTS_PATH)
        _ECHARTS = src if src else (
            "window.echarts=null;document.addEventListener('DOMContentLoaded',function(){"
            "var e=document.querySelector('.ec');if(e)e.innerHTML='<p class=\"t-muted\">缺少 "
            + ECHARTS_PATH.replace("\\", "/") + "，图表无法绘制。</p>';});")
    return _ECHARTS


def report_data(cfg, states, run=None, generated=None):
    """The JSON the page renders from. `states` are what ar.py's subject_state() returns
    (plus limits / depends_on / harness / timeout_sec / scorer_changed_since_best / unreadable
    when known); checkpoints are copied, not mutated, and gain the artifacts path and the
    round's patch when the runner saved one."""
    out_states = []
    for s in states:
        cps = []
        for c in s.get("checkpoints") or []:
            c = dict(c)
            art = os.path.join(cfg["ar_dir"], "artifacts", s["subject"], c["id"])
            c["artifacts"] = art
            patch = read_text(os.path.join(art, "changes.patch"))
            c["patch"] = (patch[:PATCH_CAP] or None) if patch else None
            c["patch_truncated"] = bool(patch) and len(patch) > PATCH_CAP
            cps.append(c)
        st = {k: v for k, v in s.items() if k != "checkpoints"}
        st["checkpoints"] = cps
        out_states.append(st)
    return {"cfg": {"name": cfg["name"], "description": cfg.get("description") or "",
                    "direction": cfg.get("direction") or "max", "ar_dir": cfg["ar_dir"]},
            "run": run or {}, "states": out_states, "generated": generated or now_iso()}


def render(cfg, states, run=None):
    data = report_data(cfg, states, run)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("@@ECHARTS@@", echarts_source())
            .replace("@@DATA@@", payload)
            .replace("@@TITLE@@", cfg["name"]))


def write_report(path, cfg, states, run=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(render(cfg, states, run))
    os.replace(tmp, path)
    return path


def states_from_ledger(ar_dir):
    """Rebuild what ar.py would pass, from the ledger alone (no repository needed)."""
    sys.path.insert(0, SCRIPT_DIR)
    import ar

    snap = ar.read_json(os.path.join(ar_dir, "research.snapshot.json"), {}) or {}
    ledger = ar.Ledger(ar_dir)
    subjects = snap.get("subjects", [])
    names = [s["name"] for s in subjects]
    if not names:
        names = sorted(os.path.basename(p) for p in
                       glob.glob(os.path.join(ar_dir, "researches", "*"))
                       if os.path.isdir(p))
        subjects = [{"name": n} for n in names]
    direction = snap.get("direction") or "max"
    states = []
    for s in subjects:
        name = s["name"]
        records = ledger.checkpoints(name)
        idx = ar.derive_index(name, records, direction, s.get("limits"))
        states.append({"subject": name, "summary": ar.summary_line(name, records, idx),
                       "index": idx, "limits": s.get("limits"),
                       "depends_on": s.get("depends_on") or [], "harness": s.get("harness"),
                       "timeout_sec": s.get("timeout_sec"), "checkpoints": records,
                       "unreadable": ledger.unreadable(name)})
    cfg = {"name": snap.get("name") or os.path.basename(ar_dir.rstrip("/")).replace(".ar", ""),
           "description": snap.get("description") or "", "direction": direction, "ar_dir": ar_dir}
    return cfg, states, ledger.report_path(), ar.run_info(ledger)


def main(argv):
    if len(argv) != 2 or argv[1].startswith("-"):
        print(json.dumps({"ok": False, "error": "usage: report.py <ar-dir>"}))
        return 2
    ar_dir = os.path.abspath(argv[1])
    if not os.path.isdir(os.path.join(ar_dir, "researches")):
        print(json.dumps({"ok": False, "error": "{} does not look like a ledger (no "
                                                "researches/)".format(ar_dir)}))
        return 1
    try:
        cfg, states, path, run = states_from_ledger(ar_dir)
        write_report(path, cfg, states, run)
    except Exception as exc:  # noqa: BLE001 - one JSON line, whatever went wrong
        print(json.dumps({"ok": False, "error": "{}: {}".format(type(exc).__name__, exc)}))
        return 1
    print(json.dumps({"ok": True, "report": path, "subjects": [s["subject"] for s in states],
                      "checkpoints": sum(len(s["checkpoints"]) for s in states)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
