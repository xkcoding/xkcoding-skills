#!/usr/bin/env python3
"""
Session Insights - Parallel Analysis Orchestrator

Reads extracted session JSON, splits into batches, and uses `claude -p` (non-interactive mode)
to analyze each batch in true OS-level parallelism via ThreadPoolExecutor.

Usage:
    python3 session-insights-analyze.py [--input FILE] [--output FILE] [--batch-size N]
"""

import json
import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# claude -p (pipe mode) is non-interactive and process-isolated,
# so it's safe to run inside another Claude Code session.
# Remove CLAUDECODE env var to bypass the nested session check.
_SUBPROCESS_ENV = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

# ─── Prompt Template ─────────────────────────────────────────────

BATCH_PROMPT = """你是 session-insights 的会话分析 Sub-Agent。请分析以下 {batch_size} 个会话数据，为每个会话生成详细分析的 Markdown 片段。

## 输入数据

{batch_json}

## 输出格式

对每个会话生成以下结构（不要包含「三、各会话详情」章节标题，直接从 ### 开始）：

### 会话 N：{{日期}} {{主题概括}}

**核心交互时序图**

```mermaid
sequenceDiagram
    participant U as 用户
    participant A as Claude Agent
    participant S as 子 Agent

    Note over U,S: Phase 1 — 阶段描述
    U->>A: 概括用户指令
    A-->>U: 结果
```

（不超过 15 个交互节点，用 par/loop/Note over 语法，合并连续同类操作）

**统计**：用户消息 X | 工具调用 Y | 子 Agent Z | Git 提交 W

**精选用户指令**

| # | 用户指令（精简） | Agent 响应 |
|---|-----------------|-----------|
（精选 5-10 条最有代表性的指令：关键需求、Bug 报告、架构决策、方向转变）

**Agent 团队拓扑**（仅当该会话有 sub_agents 数据时展示）

```mermaid
flowchart TD
    Main["🎯 Main Agent"]
    Sub1["🔍 子 Agent 名 ×N"]
    Main --> Sub1
    style Main fill:#f0fdfa,stroke:#0d9488,stroke-width:2px
    style Sub1 fill:#dbeafe,stroke:#3b82f6
```

（必须用 style 为每个节点设置不同 fill/stroke 颜色）

## 规则
- 用自己的理解来分析，不机械复制数据
- 时序图合并连续同类操作，控制在 15 节点以内
- flowchart 必须用 style 为每个节点设置不同颜色
- 按会话时间顺序排列
- 返回纯 Markdown 片段，不要额外解释或包裹代码块
- 输出语言：中文
"""


# ─── Batch Analysis ──────────────────────────────────────────────

def analyze_batch(batch_data, batch_index, total_batches):
    """Analyze a single batch using claude -p (non-interactive mode)."""
    batch_json = json.dumps(batch_data, ensure_ascii=False, indent=2)
    prompt = BATCH_PROMPT.format(
        batch_size=len(batch_data),
        batch_json=batch_json,
    )

    try:
        proc = subprocess.run(
            ["claude", "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min per batch
            env=_SUBPROCESS_ENV,
        )

        if proc.returncode == 0 and proc.stdout.strip():
            return {
                "batch_index": batch_index,
                "status": "success",
                "content": proc.stdout.strip(),
            }
        else:
            err = proc.stderr.strip() if proc.stderr else f"exit code {proc.returncode}"
            print(f"  ⚠️ 批次 {batch_index}/{total_batches} 错误: {err[:200]}", file=sys.stderr)
            return {
                "batch_index": batch_index,
                "status": "error",
                "content": generate_fallback(batch_data),
            }

    except subprocess.TimeoutExpired:
        print(f"  ⚠️ 批次 {batch_index}/{total_batches} 超时（5 分钟）", file=sys.stderr)
        return {
            "batch_index": batch_index,
            "status": "timeout",
            "content": generate_fallback(batch_data),
        }
    except FileNotFoundError:
        print("  ❌ 未找到 claude 命令，请确认 Claude Code CLI 已安装", file=sys.stderr)
        return {
            "batch_index": batch_index,
            "status": "error",
            "content": generate_fallback(batch_data),
        }
    except Exception as e:
        print(f"  ⚠️ 批次 {batch_index}/{total_batches} 异常: {e}", file=sys.stderr)
        return {
            "batch_index": batch_index,
            "status": "error",
            "content": generate_fallback(batch_data),
        }


def generate_fallback(batch_data):
    """Generate simplified summaries when a batch fails."""
    lines = ["> ⚠️ 以下会话因分析超时或失败，仅展示简要摘要\n"]
    for sess in batch_data:
        inputs = sess.get("user_inputs", [])
        topic = inputs[0][:100] if inputs else "未知主题"
        lines.append(f"### 会话：{sess.get('time_start', '?')} — {topic}")
        lines.append(
            f"**统计**：用户消息 {sess.get('user_count', 0)} | "
            f"工具调用 {sess.get('tool_calls', 0)} | "
            f"子 Agent {sess.get('subagent_count', 0)} | "
            f"Git 提交 {len(sess.get('git_commits', []))}"
        )
        lines.append("")
    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Session Insights - Parallel Analysis Orchestrator")
    parser.add_argument("--input", default="/tmp/session-insights-raw.json",
                        help="Input JSON from session-insights.py (default: /tmp/session-insights-raw.json)")
    parser.add_argument("--output", default="/tmp/session-insights-chapter3.md",
                        help="Output file for chapter 3 markdown (default: /tmp/session-insights-chapter3.md)")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Sessions per batch (default: 5)")
    parser.add_argument("--max-workers", type=int, default=None,
                        help="Max parallel workers (default: number of batches)")
    args = parser.parse_args()

    # ── Read data ──
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(json.dumps({"error": f"Input file not found: {args.input}"}))
        sys.exit(1)

    sessions = data.get("sessions", [])
    if not sessions:
        print(json.dumps({"error": "No sessions in input data"}))
        sys.exit(1)

    # ── Sort by time ──
    sessions.sort(key=lambda s: s.get("time_start", ""))

    # ── Split into batches ──
    batches = [sessions[i:i + args.batch_size] for i in range(0, len(sessions), args.batch_size)]
    total = len(batches)
    workers = args.max_workers or total

    print(f"📊 并行分析: {len(sessions)} 个会话 → {total} 批 × {args.batch_size} 个/批, {workers} 个并行进程",
          file=sys.stderr)

    # ── Parallel analysis ──
    start_time = datetime.now()
    results = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(analyze_batch, batch, i + 1, total): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            idx = futures[future]
            result = future.result()
            results[idx] = result

            emoji = "✓" if result["status"] == "success" else "⚠️"
            batch_sessions = batches[idx]
            t_start = batch_sessions[0].get("time_start", "?")
            t_end = batch_sessions[-1].get("time_start", "?")
            elapsed = (datetime.now() - start_time).seconds
            print(f"  {emoji} 批次 {idx + 1}/{total} 完成 ({t_start} ~ {t_end}) [{elapsed}s]",
                  file=sys.stderr)

    elapsed_total = (datetime.now() - start_time).seconds
    print(f"✓ 所有批次分析完成 (总耗时 {elapsed_total}s)", file=sys.stderr)

    # ── Assemble chapter 3 ──
    parts = ["## 三、各会话详情\n"]
    for i in sorted(results.keys()):
        parts.append(results[i]["content"])

    chapter3 = "\n\n".join(parts)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(chapter3)

    # ── Print summary to stdout ──
    success = sum(1 for r in results.values() if r["status"] == "success")
    summary = {
        "status": "complete",
        "total_sessions": len(sessions),
        "total_batches": total,
        "success": success,
        "failed": total - success,
        "elapsed_seconds": elapsed_total,
        "output_file": args.output,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
