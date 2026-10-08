#!/usr/bin/env python3
"""report.py - turn a ledger into the one page a person reads.

    report.py <ar-dir>        regenerate <ar-dir>/report/index.html from the checkpoints

ar.py calls write_report() after every round; this entry point exists so a ledger can
be rendered on its own, without the repository the research ran in.

The page answers four questions in order, top to bottom: where does the subject stand
(best, how far from the baseline, rounds, money, time, running or stopped), is it still
moving (a smooth curve through the kept rounds, every attempt as a point), what is it
working on (the best checkpoint's measurement and its remaining list), and what happened
in each round (one line per round, expandable). Labels are Chinese; the four outcome words
keep / discard / crash / error stay as they are in the ledger and in `status`. One HTML
file with the data embedded: no network, no assets, no build.

Standard library only; runs on Python 3.9.
"""

import datetime
import glob
import json
import os
import sys

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>@@TITLE@@</title>
<style>
:root {
  --bg: #0f1012; --panel: #17181c; --panel2: #1c1e24; --line: #262830; --ink: #e7e7ea;
  --dim: #9a9aa6; --keep: #6fcf97; --discard: #e0c770; --crash: #eb6a6a; --error: #a98bd8;
  --accent: #7fb0ff; --best: #ffd166;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.6 -apple-system,
  BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC",
  "Segoe UI", Helvetica, Arial, sans-serif; }
a { color: var(--accent); }
header, section, footer { max-width: 1120px; margin: 0 auto; padding: 0 24px; }
header { padding-top: 36px; padding-bottom: 6px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; }
h2 { font-size: 18px; font-weight: 600; margin: 0; display: flex; align-items: center; gap: 10px; }
h3 { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--dim); letter-spacing: .04em; }
.desc { color: var(--dim); margin: 0 0 4px; max-width: 80ch; }
.meta { color: var(--dim); font-size: 12px; margin: 0; }
.subject { border-top: 1px solid var(--line); margin-top: 28px; padding-top: 22px; }
.summary { color: var(--dim); font-size: 12px; margin: 4px 0 14px; font-variant-numeric: tabular-nums; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;
  margin: 0 0 14px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px; }
.card .k { color: var(--dim); font-size: 12px; letter-spacing: .04em; }
.card .v { font-size: 20px; font-weight: 600; margin: 2px 0 0; font-variant-numeric: tabular-nums;
  line-height: 1.25; }
.card .s { color: var(--dim); font-size: 12px; margin-top: 2px; }
.chartbox { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 8px 8px 4px; }
.chartbar { display: flex; gap: 16px; align-items: center; color: var(--dim); font-size: 12px;
  padding: 2px 8px 6px; flex-wrap: wrap; }
.chartbar label { cursor: pointer; user-select: none; }
.legend span { display: inline-flex; align-items: center; gap: 5px; margin-right: 12px; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.tip { position: fixed; pointer-events: none; background: #23262e; border: 1px solid #3a3d47;
  border-radius: 4px; padding: 6px 9px; font-size: 12px; color: var(--ink); max-width: 380px;
  display: none; z-index: 9; white-space: pre-wrap; }
.now { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(300px, 1.4fr); gap: 12px; margin: 14px 0; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; }
table.kv { border-collapse: collapse; width: 100%; }
table.kv td { border-top: 1px solid var(--line); padding: 4px 10px 4px 0; font-size: 12.5px;
  vertical-align: top; font-variant-numeric: tabular-nums; }
table.kv tr:first-child td { border-top: 0; }
table.kv td:first-child { color: var(--dim); width: 38%; }
table.kv.sub { margin: 2px 0; }
table.kv.sub td { padding: 2px 10px 2px 0; font-size: 12px; width: auto; white-space: nowrap; }
table.kv.sub td:first-child { width: auto; }
ul.rem { margin: 0; padding-left: 18px; }
ul.rem li { font-size: 12.5px; margin: 2px 0; word-break: break-word; }
.more { color: var(--accent); cursor: pointer; font-size: 12.5px; }
table.rounds { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; margin-top: 6px; }
table.rounds th { text-align: left; color: var(--dim); font-weight: 500; font-size: 12px;
  letter-spacing: .04em; padding: 0 8px 6px; }
table.rounds td { padding: 6px 8px; border-top: 1px solid var(--line); font-size: 13px; vertical-align: top; }
table.rounds tr.row { cursor: pointer; }
table.rounds tr.row:hover td { background: var(--panel2); }
table.rounds tr.on td { background: #212530; }
table.rounds td.what { color: var(--dim); max-width: 480px; }
table.rounds tr.on td.what { color: var(--ink); }
table.rounds tr.expand td { background: #121318; padding: 12px 16px 14px; border-top: 0; }
.chip { display: inline-block; min-width: 58px; text-align: center; border-radius: 3px;
  padding: 0 6px; font-size: 11.5px; border: 1px solid; }
.keep { color: var(--keep); border-color: #2f5f45; }
.discard { color: var(--discard); border-color: #5d5330; }
.crash { color: var(--crash); border-color: #6b3434; }
.error { color: var(--error); border-color: #4b3f66; }
.up { color: var(--keep); } .down { color: var(--dim); }
.dim { color: var(--dim); } .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.note { white-space: pre-wrap; background: var(--panel); border: 1px solid var(--line); border-radius: 4px;
  padding: 10px 12px; margin: 8px 0 12px; font-size: 13px; }
.x2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 760px) { .now, .x2 { grid-template-columns: 1fr; } }
footer { margin-top: 36px; margin-bottom: 60px; color: var(--dim); font-size: 12px; }
text { font-size: 10.5px; fill: #8b8b96; }
</style>
<header>
  <h1>@@HEADING@@</h1>
  <p class="desc">@@DESCRIPTION@@</p>
  <p class="meta">生成于 @@GENERATED@@ · 账本 @@AR_DIR@@</p>
</header>
<main id="root"></main>
<div class="tip" id="tip"></div>
<footer>页面上的每个数字都来自这份账本里的 checkpoint 文件，不联网。每一轮的原始材料（prompt、harness 输出、gate 与打分器输出）在 <span class="mono">artifacts/&lt;subject&gt;/&lt;checkpoint&gt;/</span> 下。</footer>
<script type="application/json" id="ar-data">@@DATA@@</script>
<script>
const DATA = JSON.parse(document.getElementById("ar-data").textContent);
const COLORS = {keep: "#6fcf97", discard: "#e0c770", crash: "#eb6a6a", error: "#a98bd8"};
const MIN = DATA.direction === "min";
const esc = (s) => String(s === null || s === undefined ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const isNum = (v) => typeof v === "number" && isFinite(v);
const num = (v) => isNum(v) ? v.toLocaleString("en-US") : "—";
const score = (v) => !isNum(v) ? "—" :
  (Math.abs(v - Math.round(v)) < 1e-9 ? Math.round(v).toLocaleString("en-US") : String(Number(v.toFixed(4))));
const money = (v) => isNum(v) ? "$" + (v < 10 ? v.toFixed(2) : v.toFixed(1)) : "—";
function dur(ms) {
  if (!isNum(ms)) return "—";
  if (ms < 1000) return ms + " ms";
  const s = ms / 1000;
  if (s < 90) return s.toFixed(1) + " 秒";
  const m = Math.floor(s / 60);
  if (m < 90) return m + " 分 " + String(Math.round(s - m * 60)).padStart(2, "0") + " 秒";
  return (m / 60).toFixed(1) + " 小时";
}
const when = (iso) => iso ? iso.replace("T", " ").replace(/\+.*$|Z$/, "") : "—";
const firstLine = (t, n) => {
  const s = (t || "").replace(/\s+/g, " ").trim();
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
};
// A gain is good in the direction the research wants; delta is always printed as score - before.
const delta = (c) => (isNum(c.score) && isNum(c.best_before)) ? c.score - c.best_before : null;
const better = (d) => d === null ? null : (MIN ? d < 0 : d > 0);
const fmtDelta = (d) => d === null ? "" : (d > 0 ? "+" : "") + score(d);
const median = (xs) => {
  const a = xs.slice().sort((p, q) => p - q);
  return a.length ? (a.length % 2 ? a[(a.length - 1) / 2] : (a[a.length / 2 - 1] + a[a.length / 2]) / 2) : null;
};

function bands(cps) {
  // A crashed or errored round has no version; it belongs to the band it happened in.
  const out = [];
  cps.forEach((c) => {
    const v = c.version || (out.length ? out[out.length - 1].version : null);
    if (!out.length || out[out.length - 1].version !== v) out.push({version: v, from: c.n, to: c.n});
    else out[out.length - 1].to = c.n;
  });
  return out;
}

function summaryZh(s) {
  const idx = s.index || {}, tot = idx.totals || {};
  const best = s.checkpoints.find((c) => c.id === idx.best_id);
  const versions = Array.from(new Set(s.checkpoints.map((c) => c.version).filter(Boolean)));
  return `${tot.checkpoints || 0} 个 checkpoint · ${tot.keep || 0} keep · ${tot.discard || 0} discard · ${tot.crash || 0} crash · ${tot.error || 0} error` +
    ` · 最佳 ${score(idx.best)}${best ? "（#" + best.n + "）" : ""}` +
    (versions.length ? ` · 打分器 ${versions.map((v) => "v" + v).join(" → ")}` : "") +
    ` · 更新于 ${when(idx.updated_at) === "—" ? "从未" : when(idx.updated_at)}`;
}

function cards(s) {
  const cps = s.checkpoints, idx = s.index || {}, lim = s.limits || {}, tot = idx.totals || {};
  const best = cps.find((c) => c.id === idx.best_id);
  const out = [];
  const card = (k, v, sub) => out.push(`<div class="card"><div class="k">${k}</div><div class="v">${v}</div>` +
    (sub ? `<div class="s">${sub}</div>` : "") + `</div>`);
  card("最佳分数", score(idx.best), best ? `#${best.n} · ${MIN ? "越低越好" : "越高越好"}` : "还没有打过分的轮次");
  // From the current scorer version's own baseline when it has a kept round after it; otherwise
  // the whole journey, flagged when it crosses scorer versions.
  let base = cps.find((c) => isNum(c.score) && c.version === idx.version) || null, crossed = false;
  if (best && (!base || base.id === best.id)) {
    const first = cps.find((c) => isNum(c.score));
    if (first && first.id !== best.id) { base = first; crossed = first.version !== best.version; }
  }
  if (base && best && base.id !== best.id && isNum(base.score)) {
    const d = best.score - base.score, pct = base.score ? d / Math.abs(base.score) * 100 : null;
    card("相对基线", `${score(base.score)} → ${score(best.score)}`,
      `${fmtDelta(d)}${pct !== null ? "（" + (pct > 0 ? "+" : "") + pct.toFixed(1) + "%）" : ""}自 #${base.n} 起` +
      (crossed ? ` · 打分器 v${esc(base.version)} → v${esc(best.version)}，不是同一把尺子` : (idx.version ? ` · 打分器 v${esc(idx.version)}` : "")));
  } else {
    card("相对基线", "—", base ? "基线之后还没有 keep 的轮次" : "");
  }
  const chips = ["keep", "discard", "crash", "error"].filter((k) => tot[k])
    .map((k) => `<span class="chip ${k}">${tot[k]} ${k}</span>`).join(" ");
  card("轮次", num(tot.checkpoints || 0), chips || "还没有记录");
  const costs = cps.map((c) => (c.harness || {}).cost_usd).filter(isNum);
  const outTok = cps.map((c) => (c.usage || {}).output).filter(isNum).reduce((a, b) => a + b, 0);
  const inTok = cps.map((c) => ((c.usage || {}).input || 0) + ((c.usage || {}).cache_read || 0) + ((c.usage || {}).cache_write || 0))
    .filter(isNum).reduce((a, b) => a + b, 0);
  card("花费", costs.length ? money(costs.reduce((a, b) => a + b, 0)) : (outTok ? num(outTok) + " 输出 token" : "—"),
    costs.length ? `${costs.length} 轮有计价 · 中位 ${money(median(costs))}/轮` + (outTok ? ` · 输出 ${num(outTok)} / 输入 ${num(inTok)} token` : "")
    : (outTok ? `输入 ${num(inTok)} token · 这个 harness 不报费用` : "没有用量记录"));
  const agent = cps.map((c) => (c.timings_ms || {}).agent).filter((v) => isNum(v) && v > 0);
  card("agent 用时", agent.length ? dur(agent.reduce((a, b) => a + b, 0)) : "—",
    agent.length ? `中位 ${dur(median(agent))}/轮 · 最近更新 ${when(idx.updated_at)}` : `最近更新 ${when(idx.updated_at)}`);
  const run = DATA.run || {};
  let state, sub = "";
  if (run.running && run.subject === s.subject) {
    state = `<span class="up">运行中</span>`;
    sub = `第 #${idx.n_next} 轮进行中 · 自 ${when(run.since)} 起`;
  } else if (idx.stopped_reason) {
    state = "已停止";
    sub = ({
      max_rounds: `轮数到上限：${idx.n_next}/${lim.max_rounds}`,
      consecutive_discards: `连续 ${idx.consecutive_discards} 轮 discard（上限 ${lim.max_consecutive_discards}）`,
      consecutive_errors: `连续 ${idx.consecutive_errors} 轮 error（上限 ${lim.max_consecutive_errors}）`,
      target_score: `达到目标分 ${score(lim.target_score)}`,
    }[idx.stopped_reason] || esc(idx.stopped_reason)) + " · 要继续就改 research.json 里的上限";
  } else {
    state = "空闲";
    const parts = [];
    if (lim.max_consecutive_discards) parts.push(`连续 discard ${idx.consecutive_discards || 0}/${lim.max_consecutive_discards}`);
    if (lim.max_rounds) parts.push(`轮数 ${idx.n_next || 0}/${lim.max_rounds}`);
    if (run.stopped && run.subject === s.subject) parts.push(`上次 run 停于 ${esc(run.stopped)}`);
    sub = parts.join(" · ");
  }
  card("状态", state, sub);
  return `<div class="cards">${out.join("")}</div>`;
}

function ticks(lo, hi, isLog) {
  // Round numbers at a round step, so the axis reads like a ruler rather than a printout.
  if (isLog) return [0, 0.25, 0.5, 0.75, 1].map((f) => lo + (hi - lo) * f);
  const raw = (hi - lo) / 5, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(Number(t.toFixed(10)));
  return out;
}

function smoothPath(pts) {
  // Monotone cubic (Fritsch-Carlson): a smooth curve through the points that never overshoots
  // them, so the line of kept scores is never drawn as better than any round actually was.
  const n = pts.length;
  if (n < 2) return "";
  const f = (v) => Number(v.toFixed(1));
  if (n === 2) return `M${f(pts[0].x)},${f(pts[0].y)}L${f(pts[1].x)},${f(pts[1].y)}`;
  const dx = [], m = [];
  for (let i = 0; i < n - 1; i++) { dx.push(pts[i + 1].x - pts[i].x); m.push((pts[i + 1].y - pts[i].y) / dx[i]); }
  const t = [m[0]];
  for (let i = 1; i < n - 1; i++) t.push(m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2);
  t.push(m[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
    if (s > 9) { const tau = 3 / Math.sqrt(s); t[i] = tau * a * m[i]; t[i + 1] = tau * b * m[i]; }
  }
  let d = `M${f(pts[0].x)},${f(pts[0].y)}`;
  for (let i = 0; i < n - 1; i++) {
    d += `C${f(pts[i].x + dx[i] / 3)},${f(pts[i].y + t[i] * dx[i] / 3)} ${f(pts[i + 1].x - dx[i] / 3)},${f(pts[i + 1].y - t[i + 1] * dx[i] / 3)} ${f(pts[i + 1].x)},${f(pts[i + 1].y)}`;
  }
  return d;
}

function chart(s, opts) {
  const cps = s.checkpoints;
  const W = 1060, H = 270, L = 70, R = 16, T = 30, B = 30;
  const scored = cps.filter((c) => isNum(c.score));
  if (!scored.length) return '<p class="dim">还没有打过分的轮次。</p>';
  const maxN = Math.max(1, ...cps.map((c) => c.n));
  let view = opts.baseline ? scored : scored.filter((c) => c.n > 0);
  if (view.length < 2) view = scored;
  const useLog = opts.log && view.every((c) => c.score > 0);
  const tr = (v) => useLog ? Math.log(v) : v;
  let lo = Math.min(...view.map((c) => tr(c.score))), hi = Math.max(...view.map((c) => tr(c.score)));
  if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.1;
  lo -= pad; hi += pad;
  const x = (n) => L + (W - L - R) * (n / maxN);
  const y = (v) => T + (H - T - B) * (1 - (tr(v) - lo) / (hi - lo));
  const inView = (v) => tr(v) >= lo && tr(v) <= hi;
  const parts = [];
  bands(cps).forEach((b, i) => {
    const x0 = x(b.from) - (b.from === 0 ? L - 2 : 6), x1 = x(b.to) + 6;
    parts.push(`<rect x="${x0}" y="${T - 20}" width="${Math.max(2, x1 - x0)}" height="${H - T - B + 20}"
      fill="${i % 2 ? "#ffffff" : "#7fb0ff"}" opacity="0.045"></rect>`);
    if (b.version) parts.push(x0 + 90 > W - R
      ? `<text x="${Math.min(x1, W - R) - 4}" y="${T - 9}" text-anchor="end">打分器 v${esc(b.version)}</text>`
      : `<text x="${x0 + 5}" y="${T - 9}">打分器 v${esc(b.version)}</text>`);
  });
  ticks(lo, hi, useLog).forEach((t) => {
    const v = useLog ? Math.exp(t) : t, yy = T + (H - T - B) * (1 - (t - lo) / (hi - lo));
    parts.push(`<line x1="${L}" y1="${yy}" x2="${W - R}" y2="${yy}" stroke="#262830"></line>`);
    parts.push(`<text x="${L - 6}" y="${yy + 3.5}" text-anchor="end">${esc(score(v))}</text>`);
  });
  const step = Math.max(1, Math.ceil(maxN / 12));
  for (let n = 0; n <= maxN; n += step) parts.push(`<text x="${x(n)}" y="${H - 9}" text-anchor="middle">#${n}</text>`);
  // The curve goes through the kept rounds, restarted at every scorer version. It is the line
  // that says whether the research is still moving; the points around it are the attempts.
  let ver = null, run = [];
  const flush = () => {
    if (run.length > 1) parts.push(`<path d="${smoothPath(run)}" fill="none" stroke="#ffd166" stroke-width="1.6" opacity="0.9"></path>`);
    run = [];
  };
  cps.forEach((c) => {
    if (c.status !== "keep" || !isNum(c.score)) return;
    if (c.version !== ver) { flush(); ver = c.version; }
    if (!inView(c.score)) { flush(); return; }
    run.push({x: x(c.n), y: y(c.score)});
  });
  flush();
  const hidden = [];
  cps.forEach((c) => {
    const cx = x(c.n), col = COLORS[c.status] || "#8b8b96";
    const tipTxt = `#${c.n} ${c.status}${isNum(c.score) ? " · " + score(c.score) : ""}` +
      (delta(c) !== null && c.n > 0 ? "（" + fmtDelta(delta(c)) + "）" : "") +
      (c.reason ? " · " + firstLine(c.reason, 90) : "") + (c.note ? "\n" + firstLine(c.note, 140) : "");
    const g = (inner, cy) => parts.push(`<g class="pt" data-id="${esc(c.id)}" data-tip="${esc(tipTxt)}">${inner}
      <circle cx="${cx}" cy="${cy}" r="8" fill="transparent"></circle></g>`);
    if (!isNum(c.score)) {
      const cy = H - B - 6;
      g(`<path d="M${cx - 4},${cy - 4}L${cx + 4},${cy + 4}M${cx + 4},${cy - 4}L${cx - 4},${cy + 4}" stroke="${col}" stroke-width="1.8"></path>`, cy);
    } else if (!inView(c.score)) {
      hidden.push(c);
    } else if (c.status === "keep") {
      g(`<circle cx="${cx}" cy="${y(c.score)}" r="3.4" fill="${col}"></circle>`, y(c.score));
    } else {
      g(`<circle cx="${cx}" cy="${y(c.score)}" r="3.6" fill="none" stroke="${col}" stroke-width="1.5"></circle>`, y(c.score));
    }
  });
  if (hidden.length) parts.push(`<text x="${W - R}" y="${T - 9}" text-anchor="end">图外：${hidden.map((c) => "#" + c.n + " = " + score(c.score)).join("，")}</text>`);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">${parts.join("")}</svg>`;
}

function chartbar(si, s, opts) {
  const scored = s.checkpoints.filter((c) => isNum(c.score));
  const canLog = scored.every((c) => c.score > 0) && scored.length > 2;
  return `<div class="chartbar">
    <span class="legend"><span><i class="sw" style="background:#ffd166"></i>keep 的轮次</span>
      <span><i class="sw" style="background:${COLORS.keep}"></i>keep</span>
      <span><i class="sw" style="border:1.5px solid ${COLORS.discard}"></i>discard</span>
      <span><b style="color:${COLORS.crash}">✕</b> crash</span><span><b style="color:${COLORS.error}">✕</b> error（无分数）</span></span>
    <label><input type="checkbox" data-opt="baseline" data-s="${si}" ${opts.baseline ? "checked" : ""}> 显示 #0 基线</label>
    ${canLog ? `<label><input type="checkbox" data-opt="log" data-s="${si}" ${opts.log ? "checked" : ""}> 对数轴</label>` : ""}
  </div>`;
}

function cell(v) {
  return v && typeof v === "object" ? `<span class="mono">${esc(JSON.stringify(v))}</span>` : esc(isNum(v) ? num(v) : v);
}

function nested(v) {
  // A dict whose values are dicts with the same keys is a table (per-file sizes, per-split
  // metrics); a dict of primitives is a list; anything else stays JSON.
  if (!v || typeof v !== "object") return cell(v);
  if (Array.isArray(v)) return `<span class="mono">${esc(JSON.stringify(v))}</span>`;
  const inner = Object.values(v);
  if (inner.length && inner.every((x) => x && typeof x === "object" && !Array.isArray(x))) {
    const cols = Array.from(new Set(inner.flatMap((x) => Object.keys(x))));
    return `<table class="kv sub"><tr><td></td>${cols.map((c) => `<td class="dim">${esc(c)}</td>`).join("")}</tr>` +
      Object.keys(v).map((k) => `<tr><td>${esc(k)}</td>${cols.map((c) => `<td>${cell(v[k][c])}</td>`).join("")}</tr>`).join("") + `</table>`;
  }
  return Object.keys(v).map((k) => `<span class="dim">${esc(k)}</span> ${cell(v[k])}`).join(" · ");
}

function kv(obj) {
  const keys = Object.keys(obj || {});
  if (!keys.length) return '<p class="dim">打分器没有报告 details</p>';
  return `<table class="kv">` + keys.map((k) =>
    `<tr><td>${esc(k)}</td><td>${nested(obj[k])}</td></tr>`).join("") + `</table>`;
}

function remaining(list, limit, key) {
  const rem = list || [];
  if (!rem.length) return '<p class="dim">remaining 为空——按这把尺子已经没有事可做</p>';
  const shown = rem.slice(0, limit);
  let html = `<ul class="rem">` + shown.map((r) => `<li>${esc(r)}</li>`).join("") + `</ul>`;
  if (rem.length > limit) html += `<p class="more" data-more="${key}">展开全部 ${rem.length} 条</p>
    <ul class="rem" id="${key}" style="display:none">${rem.slice(limit).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`;
  return html;
}

function now(s, si) {
  const idx = s.index || {};
  const best = s.checkpoints.find((c) => c.id === idx.best_id);
  if (!best) return "";
  return `<div class="now">
    <div class="panel"><h3>最佳分数（#${best.n}）是怎么来的</h3>${kv(best.details)}</div>
    <div class="panel"><h3>打分器在 #${best.n} 认为还差什么（remaining）</h3>${remaining(best.remaining, 12, "rem" + si)}</div>
  </div>`;
}

function what(c) {
  if (c.n === 0 && c.status === "keep" && !(c.changed_files || []).length) return "基线：按 HEAD 原样测量，没有跑 agent。";
  if ((c.status === "crash" || c.status === "error") && c.reason) return firstLine(c.reason, 150);
  const m = /^scorer version (\S+) → (\S+): new comparison baseline$/.exec(c.reason || "");
  if (m) return `打分器版本 ${esc(m[1])} → ${esc(m[2])}：作为新版本的比较基线`;
  return c.note ? firstLine(c.note, 150) : '<span class="dim">（agent 没有留下自述）</span>';
}

function rowsOf(s, si) {
  return s.checkpoints.slice().reverse().map((c) => {
    const d = c.n > 0 ? delta(c) : null;
    const dcls = d === null ? "dim" : (better(d) ? "up" : "down");
    const h = c.harness || {};
    return `<tr class="row" data-s="${si}" data-id="${esc(c.id)}"><td>#${c.n}</td>
      <td><span class="chip ${esc(c.status)}">${esc(c.status)}</span></td>
      <td>${esc(score(c.score))}</td><td class="${dcls}">${fmtDelta(d)}</td>
      <td class="what">${what(c)}</td>
      <td class="dim">${(c.changed_files || []).length || ""}</td>
      <td class="dim">${dur((c.timings_ms || {}).agent)}</td><td class="dim">${isNum(h.cost_usd) ? money(h.cost_usd) : ""}</td></tr>`;
  }).join("");
}

function expand(c) {
  const h = c.harness || {}, u = c.usage || {}, t = c.timings_ms || {};
  const rows = [];
  const put = (k, v) => rows.push(`<tr><td>${esc(k)}</td><td>${v}</td></tr>`);
  put("分数", isNum(c.score) ? `${esc(score(c.score))} <span class="dim">打分器 v${esc(c.version)} · 之前的最佳 ${esc(score(c.best_before))}</span>` : '<span class="dim">没有测量</span>');
  if (c.reason) put("原因", `<span class="mono">${esc(c.reason)}</span>`);
  put("时间", esc(when(c.at)));
  put("commit", `<span class="mono">${esc((c.commit || "").slice(0, 10)) || "—"}</span>` +
    (c.reverted_by ? ` <span class="dim">已被 ${esc(c.reverted_by.slice(0, 10))} revert</span>` :
      (c.status === "keep" ? "" : ` <span class="dim">（空轮次，无需 revert）</span>`)));
  put("耗时", Object.keys(t).map((k) => `${esc(k)} ${dur(t[k])}`).join(" · ") || "—");
  put("token", `输出 ${num(u.output)} · 输入 ${num(u.input)} · 缓存读 ${num(u.cache_read)} · 缓存写 ${num(u.cache_write)}`);
  put("harness", `${esc(h.type)}${h.model ? " · " + esc(h.model) : ""}${isNum(h.turns) ? " · " + h.turns + " turns" : ""}` +
    `${isNum(h.exit) ? " · exit " + h.exit : ""}${h.cut_off ? " · 被 " + esc(h.cut_off) + " 截断" : ""}${isNum(h.cost_usd) ? " · " + money(h.cost_usd) : ""}` +
    (h.session_id ? `<br><span class="dim mono">${esc(h.session_id)}</span>` : ""));
  const files = c.changed_files || [];
  put("改动", files.length ? files.map((f) => `<span class="mono">${esc(f)}</span>`).join(", ") : '<span class="dim">没有文件变动</span>');
  put("产物", `<span class="mono">artifacts/${esc(c.subject)}/${esc(c.id)}/</span>`);
  let html = `<div class="x2"><div><h3>第 #${c.n} 轮 <span class="mono dim">${esc(c.id)}</span></h3><table class="kv">${rows.join("")}</table></div>`;
  html += `<div><h3>测量结果（details）</h3>${isNum(c.score) ? kv(c.details) : '<p class="dim">没有测量</p>'}
    <h3 style="margin-top:12px">还差什么（remaining）</h3>${remaining(c.remaining, 8, "r" + c.id)}</div></div>`;
  html += `<h3 style="margin-top:12px">agent 的自述</h3>` + (c.note ? `<div class="note">${esc(c.note)}</div>` : '<p class="dim">没有</p>');
  return html;
}

const OPTS = {};
function defaults(s) {
  // Hide the baseline by default when it would flatten everything else: a first round that
  // jumps far is the common case for a research that starts from nothing.
  const sc = s.checkpoints.filter((c) => isNum(c.score));
  const rest = sc.filter((c) => c.n > 0).map((c) => c.score);
  if (rest.length < 2 || !sc.length || sc[0].n !== 0) return {baseline: true, log: false};
  const spread = Math.max(...rest) - Math.min(...rest);
  const far = Math.abs(sc[0].score - median(rest));
  return {baseline: !(spread > 0 ? far > 3 * spread : far > 0), log: false};
}

function drawChart(si) {
  const s = DATA.subjects[si];
  const box = document.getElementById("chart" + si);
  box.innerHTML = chartbar(si, s, OPTS[si]) + chart(s, OPTS[si]);
  box.querySelectorAll("input[data-opt]").forEach((el) => el.addEventListener("change", () => {
    OPTS[si][el.dataset.opt] = el.checked; drawChart(si);
  }));
  const tip = document.getElementById("tip");
  box.querySelectorAll("g.pt").forEach((g) => {
    g.addEventListener("mousemove", (e) => { tip.style.display = "block"; tip.textContent = g.dataset.tip;
      tip.style.left = (e.clientX + 14) + "px"; tip.style.top = (e.clientY + 12) + "px"; });
    g.addEventListener("mouseleave", () => { tip.style.display = "none"; });
    g.addEventListener("click", () => open(si, g.dataset.id, true));
  });
}

function open(si, id, scroll) {
  const s = DATA.subjects[si];
  const c = s.checkpoints.find((k) => k.id === id);
  if (!c) return;
  const sec = document.getElementById("s" + si);
  sec.querySelectorAll("tr.expand").forEach((tr) => tr.remove());
  let target = null;
  sec.querySelectorAll("tr.row").forEach((tr) => {
    const on = tr.dataset.id === id && !tr.classList.contains("on");
    tr.classList.toggle("on", on);
    if (on) target = tr;
  });
  if (!target) return;
  const ex = document.createElement("tr");
  ex.className = "expand";
  ex.innerHTML = `<td colspan="8">${expand(c)}</td>`;
  target.after(ex);
  wireMore(ex);
  if (scroll) target.scrollIntoView({block: "center", behavior: "smooth"});
}

function wireMore(root) {
  root.querySelectorAll("p.more").forEach((p) => p.addEventListener("click", () => {
    const ul = document.getElementById(p.dataset.more);
    const hidden = ul.style.display === "none";
    ul.style.display = hidden ? "" : "none";
    p.textContent = hidden ? "收起" : p.dataset.label;
  }));
  root.querySelectorAll("p.more").forEach((p) => { p.dataset.label = p.textContent; });
}

function render() {
  const root = document.getElementById("root");
  root.innerHTML = DATA.subjects.map((s, si) => {
    OPTS[si] = defaults(s);
    return `<section class="subject" id="s${si}">
      <h2>${esc(s.subject)}${(s.depends_on || []).length ? `<span class="dim" style="font-size:12px;font-weight:400">依赖 ${s.depends_on.map(esc).join("、")}</span>` : ""}</h2>
      <p class="summary">${summaryZh(s)}</p>
      ${cards(s)}
      <div class="chartbox" id="chart${si}"></div>
      ${now(s, si)}
      <table class="rounds"><thead><tr><th>轮次</th><th>结果</th><th>分数</th><th>Δ</th>
        <th>这一轮发生了什么</th><th>文件</th><th>agent</th><th>费用</th></tr></thead>
        <tbody>${rowsOf(s, si) || '<tr><td colspan="8" class="dim">还没有记录</td></tr>'}</tbody></table>
    </section>`;
  }).join("");
  DATA.subjects.forEach((s, si) => {
    if (s.checkpoints.length) drawChart(si);
    document.querySelectorAll("#s" + si + " tr.row").forEach((tr) =>
      tr.addEventListener("click", () => open(si, tr.dataset.id, false)));
  });
  wireMore(root);
}
render();
</script>
</html>
"""


def write_report(path, cfg, states, run=None):
    """One HTML file, data inside it, no network. Called after every round.

    `run` says what the runner knows and the ledger does not: {"running": bool, "subject",
    "since", "stopped"}; the standalone entry point derives it from run.lock.
    """
    data = {"name": cfg["name"], "description": cfg.get("description") or "",
            "direction": cfg.get("direction") or "max", "run": run or {},
            "subjects": [{"subject": s["subject"], "summary": s["summary"], "index": s["index"],
                          "limits": s.get("limits"), "depends_on": s.get("depends_on") or [],
                          "checkpoints": s["checkpoints"]} for s in states]}
    title = "{} · autoresearch".format(cfg["name"])
    html = (TEMPLATE.replace("@@TITLE@@", esc(title)).replace("@@HEADING@@", esc(title))
            .replace("@@DESCRIPTION@@", esc(cfg.get("description") or ""))
            .replace("@@GENERATED@@", datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())
            .replace("@@AR_DIR@@", esc(cfg.get("ar_dir") or ""))
            .replace("@@DATA@@", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def states_from_ledger(ar_dir):
    """Rebuild what ar.py would pass, from the ledger alone."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
                       "depends_on": s.get("depends_on") or [], "checkpoints": records})
    cfg = {"name": snap.get("name") or os.path.basename(ar_dir.rstrip("/")).replace(".ar", ""),
           "description": snap.get("description") or "", "direction": direction, "ar_dir": ar_dir}
    live = ar.active_run(ledger)
    run = {"running": True, "subject": live.get("subject"), "since": live.get("started"),
           "run_id": live.get("run_id")} if live else {}
    return cfg, states, ledger.report_path(), run


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
        cfg, states, out_path, run = states_from_ledger(ar_dir)
        path = write_report(out_path, cfg, states, run)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": "{}: {}".format(type(exc).__name__, exc)}))
        return 1
    print(json.dumps({"ok": True, "report": path,
                      "subjects": [s["subject"] for s in states]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
