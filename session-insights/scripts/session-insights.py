#!/usr/bin/env python3
"""
Claude Session Insights - Data Extractor
提取 Claude Code 会话 JSONL 数据，输出结构化 JSON 供 Agent 分析。

Usage:
    python3 session-insights.py <project_path_or_keyword> [--last N] [--depth summary|detailed]

Output: JSON to stdout (structured session data for Agent to analyze and generate reports)
"""

import json
import ast
import sys
import os
import re
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict


# ─── Constants ────────────────────────────────────────────────

IDLE_THRESHOLD = timedelta(minutes=5)  # gap > 5min = idle


# ─── Message Parsing ──────────────────────────────────────────

def parse_message_field(raw):
    """Parse the message field which may be a dict or a stringified Python dict.

    Claude Code JSONL stores `message` as either:
    - A proper JSON object (parsed as dict by json.loads)
    - A stringified Python dict (e.g. "{'role': 'user', ...}") needing ast.literal_eval
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return ast.literal_eval(raw)
        except Exception:
            try:
                return json.loads(raw)
            except Exception:
                return {"content": raw}
    return {"content": str(raw)}


def extract_text(content):
    """Extract text from content (str or list of content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def extract_tool_calls(content):
    """Extract tool_use details from content blocks."""
    tools = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools.append({
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                })
    return tools


def clean_user_text(text):
    """Clean user message text: remove system-reminder, command wrappers, etc."""
    if not text:
        return ""
    # Remove system reminders
    text = re.sub(r'<system-reminder>.*?</system-reminder>', '', text, flags=re.DOTALL)
    # Remove command wrappers (keep content)
    text = re.sub(r'<command-message>.*?</command-message>\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'<command-name>.*?</command-name>\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'<command-args>(.*?)</command-args>', r'\1', text, flags=re.DOTALL)
    return text.strip()


# ─── Active Time Calculation ──────────────────────────────────

def calculate_active_time(timestamps):
    """Calculate active vs idle time from sorted timestamps using gap analysis.

    Returns dict with active_min, idle_min, session_min, active_pct, idle_periods.
    """
    if len(timestamps) < 2:
        return {
            "active_min": 0, "idle_min": 0, "session_min": 0,
            "active_pct": 0, "idle_periods": []
        }

    session_duration = timestamps[-1] - timestamps[0]
    active_time = timedelta()
    idle_time = timedelta()
    idle_periods = []

    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        if gap <= IDLE_THRESHOLD:
            active_time += gap
        else:
            idle_time += gap
            idle_periods.append({
                "start": timestamps[i - 1].strftime("%H:%M"),
                "end": timestamps[i].strftime("%H:%M"),
                "min": int(gap.total_seconds() / 60),
            })

    session_min = int(session_duration.total_seconds() / 60)
    active_min = int(active_time.total_seconds() / 60)
    idle_min = int(idle_time.total_seconds() / 60)
    active_pct = round(active_min / session_min * 100) if session_min > 0 else 0

    # Sort idle periods by duration descending, keep top 5
    idle_periods.sort(key=lambda x: x["min"], reverse=True)

    return {
        "active_min": active_min,
        "idle_min": idle_min,
        "session_min": session_min,
        "active_pct": active_pct,
        "idle_periods": idle_periods[:5],
    }


# ─── Project Discovery ───────────────────────────────────────

def encode_path_to_dirname(path_str):
    """Encode a filesystem path to Claude's project directory name format.

    Claude Code replaces all non-alphanumeric characters (except -) with -.
    e.g. /Users/yangkai.shen/code/foo -> -Users-yangkai-shen-code-foo
    """
    return re.sub(r'[^a-zA-Z0-9-]', '-', path_str)


def extract_project_display_name(dir_name):
    """Extract human-readable project name from encoded directory name."""
    parts = dir_name.strip("-").split("-")
    for marker in ("code", "projects", "repos", "src", "work", "dev"):
        if marker in parts:
            idx = parts.index(marker)
            remaining = parts[idx + 1:]
            if remaining:
                return "/".join(remaining)
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return dir_name


def find_project_dir(project_query):
    """Find the project directory in ~/.claude/projects/ matching the query."""
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists():
        return None

    # If query is a full path, try encoded match (walking up ancestors)
    if os.path.isabs(project_query):
        query_path = Path(project_query)
        for ancestor in [query_path] + list(query_path.parents):
            encoded = encode_path_to_dirname(str(ancestor))
            candidate = projects_root / encoded
            if candidate.exists() and any(candidate.glob("*.jsonl")):
                return str(candidate)

    # Fuzzy match: find directories containing the query string (case-insensitive)
    matches = []
    for d in projects_root.iterdir():
        if d.is_dir() and project_query.lower() in d.name.lower():
            matches.append(d)

    if len(matches) == 1:
        return str(matches[0])
    elif len(matches) > 1:
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        print(json.dumps({
            "warning": "Multiple project matches",
            "matches": [m.name for m in matches],
            "selected": matches[0].name,
        }), file=sys.stderr)
        return str(matches[0])

    return None


# ─── Session Parsing ──────────────────────────────────────────

def parse_session(filepath):
    """Parse a single session JSONL file into structured data."""
    f = Path(filepath)
    sid = f.stem
    data = {
        "id": sid[:8],
        "full_id": sid,
        "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
        "user_inputs": [],
        "agent_summaries": [],
        "tools": Counter(),
        "sub_agents": Counter(),
        "files_edited": Counter(),  # filename -> edit count
        "files_written": set(),
        "skills": [],
        "git_commits": [],
        "models": Counter(),
        "timestamps": [],   # all message timestamps (datetime objects)
    }

    # Count subagent JSONL files
    sa_dir = f.parent / sid / "subagents"
    data["subagent_file_count"] = len(list(sa_dir.glob("*.jsonl"))) if sa_dir.exists() else 0

    with open(filepath, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rec_type = record.get("type", "")
            ts_str = record.get("timestamp", "")

            # Collect timestamps for active time calculation
            if ts_str and rec_type in ("user", "assistant"):
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    data["timestamps"].append(ts)
                except (ValueError, TypeError):
                    pass

            if rec_type not in ("user", "assistant"):
                continue

            # Parse message field (handles both dict and stringified dict)
            msg = parse_message_field(record.get("message", ""))
            role = msg.get("role", "")
            content = msg.get("content", "")
            model = msg.get("model", "")

            if model:
                data["models"][model] += 1

            # ── User messages ──
            if rec_type == "user" and role == "user":
                text = extract_text(content).strip()
                text = clean_user_text(text)
                # Skip empty, too short, or system-only messages
                if text and len(text) > 5:
                    data["user_inputs"].append(text[:500])

            # ── Assistant messages ──
            if rec_type == "assistant" and role == "assistant":
                text = extract_text(content).strip()
                tool_calls = extract_tool_calls(content)

                for tc in tool_calls:
                    tname = tc["name"]
                    inp = tc.get("input", {})
                    data["tools"][tname] += 1

                    # Track sub-agent delegations
                    if tname == "Task":
                        sat = inp.get("subagent_type", inp.get("description", "unknown"))
                        data["sub_agents"][sat] += 1

                    # Track file edits (with frequency count)
                    elif tname in ("Edit", "MultiEdit"):
                        fp = inp.get("file_path", "")
                        if fp:
                            data["files_edited"][fp.split("/")[-1]] += 1

                    # Track file writes
                    elif tname == "Write":
                        fp = inp.get("file_path", "")
                        if fp:
                            data["files_written"].add(fp.split("/")[-1])

                    # Track skills
                    elif tname == "Skill":
                        sk = inp.get("skill", "")
                        if sk:
                            data["skills"].append(sk)

                    # Track git commits
                    elif tname == "Bash":
                        cmd = inp.get("command", "")
                        if "git commit" in cmd:
                            data["git_commits"].append(cmd[:200])

                if text and len(text) > 10:
                    data["agent_summaries"].append(text[:300])

    return data


# ─── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Claude Session Insights - Data Extractor")
    parser.add_argument("project", nargs="?", default=None,
                        help="Project path or keyword (auto-detect from CWD if omitted)")
    parser.add_argument("--last", type=int, default=None, help="Only analyze last N sessions")
    parser.add_argument("--depth", choices=["summary", "detailed"], default="summary",
                        help="Controls how much user input text to include")
    args = parser.parse_args()

    # ── Find project directory ──
    project_query = args.project or os.getcwd()
    project_dir = find_project_dir(project_query)
    if not project_dir:
        print(json.dumps({"error": f"No project found matching: {project_query}"}))
        sys.exit(1)

    project_name = extract_project_display_name(Path(project_dir).name)
    print(json.dumps({"status": "found", "project": project_name, "dir": project_dir}), file=sys.stderr)

    # ── List session files (sorted by mtime, newest first) ──
    p = Path(project_dir)
    files = sorted(p.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if args.last:
        files = files[:args.last]

    print(json.dumps({"status": "parsing", "files": len(files)}), file=sys.stderr)

    # ── Parse all sessions ──
    sessions = []
    for f in files:
        data = parse_session(str(f))
        if not data["user_inputs"] and not data["agent_summaries"]:
            continue  # skip empty sessions

        # Calculate active time
        ts_list = sorted(data["timestamps"])
        active_info = calculate_active_time(ts_list)

        # Format time range
        time_start = ""
        time_end = ""
        duration_min = 0
        if ts_list:
            time_start = ts_list[0].strftime("%Y-%m-%d %H:%M")
            time_end = ts_list[-1].strftime("%Y-%m-%d %H:%M")
            duration_min = int((ts_list[-1] - ts_list[0]).total_seconds() / 60)

        # Build files_edited with counts, sorted by frequency desc
        files_edited_ranked = data["files_edited"].most_common(20)

        # Build session output (JSON-serializable)
        sess = {
            "id": data["id"],
            "full_id": data["full_id"],
            "size_mb": data["size_mb"],
            "time_start": time_start,
            "time_end": time_end,
            "duration_min": duration_min,
            "active_min": active_info["active_min"],
            "active_pct": active_info["active_pct"],
            "idle_periods": active_info["idle_periods"],
            "user_count": len(data["user_inputs"]),
            "agent_count": len(data["agent_summaries"]),
            "tool_calls": sum(data["tools"].values()),
            "subagent_count": data["subagent_file_count"],
            "top_tools": data["tools"].most_common(10),
            "sub_agents": dict(data["sub_agents"]),
            "models": dict(data["models"]),
            "files_edited": files_edited_ranked,  # [(filename, count), ...]
            "files_written": sorted(data["files_written"])[:15],
            "skills": data["skills"],
            "git_commits": data["git_commits"],
        }

        # Include user inputs based on depth
        # Both modes get curated inputs; detailed gets more
        if args.depth == "detailed":
            sess["user_inputs"] = data["user_inputs"][:50]
        else:
            sess["user_inputs"] = data["user_inputs"][:5]

        sessions.append(sess)

    if not sessions:
        print(json.dumps({"error": "No valid sessions found"}))
        sys.exit(1)

    # ── Aggregate totals ──
    all_tools = Counter()
    all_sub_agents = Counter()
    all_files_edited = Counter()  # filename -> total edit count across sessions
    all_files_written = set()
    total_active_min = 0
    total_session_min = 0

    for s in sessions:
        for tool_name, count in s["top_tools"]:
            all_tools[tool_name] += count
        for sa_type, count in s["sub_agents"].items():
            all_sub_agents[sa_type] += count
        for fname, count in s["files_edited"]:
            all_files_edited[fname] += count
        all_files_written.update(s["files_written"])
        total_active_min += s["active_min"]
        total_session_min += s["duration_min"]

    # ── Build output JSON ──
    output = {
        "project_name": project_name,
        "project_dir": project_dir,
        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "depth": args.depth,
        "totals": {
            "session_count": len(sessions),
            "user_messages": sum(s["user_count"] for s in sessions),
            "agent_outputs": sum(s["agent_count"] for s in sessions),
            "tool_calls": sum(s["tool_calls"] for s in sessions),
            "subagent_sessions": sum(s["subagent_count"] for s in sessions),
            "total_active_min": total_active_min,
            "total_session_min": total_session_min,
            "overall_active_pct": round(total_active_min / total_session_min * 100) if total_session_min > 0 else 0,
        },
        "all_tools": all_tools.most_common(20),
        "all_sub_agents": all_sub_agents.most_common(),
        "all_files_edited": all_files_edited.most_common(30),  # [(filename, count), ...]
        "all_files_written": sorted(all_files_written),
        "sessions": sessions,
    }

    # Output JSON to stdout
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
