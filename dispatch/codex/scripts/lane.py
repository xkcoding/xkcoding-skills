#!/usr/bin/env python3
"""lane.py - the mechanical half of /dispatch:codex.

Every subcommand prints exactly one JSON object and never raises.
Exit code: 0 = done, 1 = refused or failed (see "error"), 2 = usage.

  plan [<change> ...]           which changes can be dispatched, and under which names (read-only)
  create <change>               worktree + lane branch; an uncommitted change becomes its first commit
  launch <change> [--strict]    start codex in the lane's pane; report ready / dialog / exited
  prompt <change> --goal|--plain|--continue|--resume|--correct TEXT
                                send one prompt, after checking identity and that no dialog is parked
  list [--table] [--no-remote]  overview of every lane, derived from git + herdr + openspec
  note <change> escalate REASON | clear | review-url URL
  record-verify <change>        write verify.md from a JSON report on stdin and commit it
  publish <change> --title T [--body-file F] [--ready] [--no-pr] [--via gh|glab|handoff] [--ack-remote]
                                push the lane branch, then open the review request (PR / MR) with the
                                tool that matches the remote, or hand the pieces over when it cannot
  forge [--set gh|glab|handoff|none [--tool NAME]] [--forget]
                                which tool opens review requests for this remote's host; remembered per host

Work state lives only in OpenSpec (tasks.md). The bookkeeping file holds what cannot
be derived (session id, posture, PR base, nudges, escalations, publish attempts) and is
disposable: delete it and `list` still reports every lane's progress correctly.

Standard library only.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

LANE_BRANCH_PREFIX = "change/"
AGENT_NAME_MAX = 32
START_TIMEOUT_MS = 120000
MAX_PUBLISH_ATTEMPTS = 3

GOAL_TEXT = (
    "Apply the OpenSpec change {c} by using $openspec-apply-change {c}. "
    "Work only inside this directory; never cd to another checkout and never touch files outside it. "
    "After completing each task: tick it in openspec/changes/{c}/tasks.md, then make one git commit "
    "(Conventional Commits) containing that task's files plus the tasks.md tick. "
    "Stage only the paths that belong to the task; never use git add -A. "
    "Do not amend or rebase commits you already made. "
    "If reality contradicts the plan, record the deviation in the commit message body instead of silently redesigning. "
    "Never push, never merge, never open a pull request: committing is where your job ends. "
    "You are done when every task is ticked and git status is clean."
)
CONTINUE_TEXT = (
    "Continue applying the OpenSpec change {c} with $openspec-apply-change {c}: pick up at the first "
    "unticked task in openspec/changes/{c}/tasks.md. Same rules as before: one commit per task, "
    "never push, never merge, never open a pull request."
)
CORRECT_TEXT = (
    "Verification failed for the OpenSpec change {c}: {detail} "
    "Fix it, keep tasks.md accurate (untick a task that is not actually done), commit, "
    "and stop when git status is clean. Never push."
)


# ---------- plumbing ----------

def run(cmd, cwd=None, timeout=90, stdin=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "{}: not found".format(cmd[0])
    except subprocess.TimeoutExpired:
        return 124, "", "{}: timed out after {}s".format(cmd[0], timeout)


def jrun(cmd, cwd=None, timeout=90):
    rc, out, _ = run(cmd, cwd=cwd, timeout=timeout)
    try:
        return rc, json.loads(out)
    except ValueError:
        return rc, None


def real(path):
    return os.path.realpath(path) if path else path


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def fail(msg, **extra):
    out = {"ok": False, "error": msg}
    out.update(extra)
    emit(out, 1)


def git(args, cwd, timeout=90):
    return run(["git"] + args, cwd=cwd, timeout=timeout)


def git_out(args, cwd):
    rc, out, _ = git(args, cwd)
    return out.strip() if rc == 0 else ""


# ---------- repository ----------

def main_root():
    """Main checkout of the repository family the cwd belongs to (works from a lane too)."""
    rc, out, _ = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], os.getcwd())
    if rc != 0:
        fail("not inside a git repository")
    common = real(out.strip())
    if os.path.basename(common) != ".git":
        fail("unsupported repository layout (bare or non-standard git dir): " + common)
    return os.path.dirname(common)


def in_main_checkout():
    a = git_out(["rev-parse", "--path-format=absolute", "--git-dir"], os.getcwd())
    b = git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], os.getcwd())
    return bool(a) and real(a) == real(b)


def lanes_dir(root):
    return root + ".lanes"


def bookkeeping_path(root):
    rid = "{}-{}".format(os.path.basename(root), hashlib.sha1(root.encode()).hexdigest()[:8])
    return os.path.join(os.path.expanduser("~/.claude/dispatch"), rid, "bookkeeping.json")


def book_load(root):
    try:
        with open(bookkeeping_path(root)) as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def book_update(root, change, **fields):
    data = book_load(root)
    lane = data.setdefault("lanes", {}).setdefault(change, {})
    for k, v in fields.items():
        if v is None:
            lane.pop(k, None)
        else:
            lane[k] = v
    path = bookkeeping_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return lane


# ---------- discovery: git + herdr + openspec ----------

def git_worktrees(root):
    out = git_out(["worktree", "list", "--porcelain"], root)
    items, cur = [], {}
    for line in out.splitlines() + [""]:
        if line.startswith("worktree "):
            cur = {"path": line[9:]}
        elif line.startswith("branch refs/heads/"):
            cur["branch"] = line[18:]
        elif not line and cur:
            items.append(cur)
            cur = {}
    return items


def find_lanes(root):
    """Linked worktrees on change/* whose directory name is a change that exists inside them."""
    lanes = []
    for wt in git_worktrees(root):
        path, branch = wt.get("path", ""), wt.get("branch", "")
        if real(path) == real(root) or not branch.startswith(LANE_BRANCH_PREFIX):
            continue
        change = os.path.basename(path)
        if os.path.isdir(os.path.join(path, "openspec", "changes", change)):
            lanes.append({"change": change, "branch": branch, "worktree": path})
    return lanes


def find_lane(root, change):
    for lane in find_lanes(root):
        if lane["change"] == change:
            return lane
    return None


def herdr_agents():
    rc, data = jrun(["herdr", "agent", "list"])
    if rc != 0 or not data:
        return None
    return (data.get("result") or {}).get("agents") or []


def agents_in(agents, worktree):
    target = real(worktree)
    return [a for a in (agents or []) if real(a.get("cwd")) == target or real(a.get("foreground_cwd")) == target]


def agent_ref(agent):
    return agent.get("name") or agent.get("pane_id")


def lane_pane(root, worktree):
    """Workspace and pane herdr opened for this worktree."""
    rc, data = jrun(["herdr", "worktree", "list", "--cwd", root])
    ws = None
    for wt in ((data or {}).get("result") or {}).get("worktrees") or []:
        if real(wt.get("path")) == real(worktree):
            ws = wt.get("open_workspace_id")
    if not ws:
        return None, None
    rc, data = jrun(["herdr", "pane", "list", "--workspace", ws])
    for pane in ((data or {}).get("result") or {}).get("panes") or []:
        if real(pane.get("cwd")) == real(worktree):
            return ws, pane.get("pane_id")
    return ws, None


def apply_status(cwd, change):
    rc, data = jrun(["openspec", "instructions", "apply", "--change", change, "--json"], cwd=cwd)
    if not data or "state" not in data:
        return None
    return {
        "state": data.get("state"),
        "progress": data.get("progress") or {},
        "missing": data.get("missingArtifacts") or [],
        "tasks": data.get("tasks") or [],
    }


def goal_probe(session):
    """Authoritative codex goal state. <CODEX_HOME>/sqlite/goals_1.sqlite is an empty decoy; not used."""
    if not session:
        return {"probe": "unavailable", "reason": "no session id yet"}
    db = os.path.join(os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex")), "goals_1.sqlite")
    if not os.path.isfile(db):
        return {"probe": "unavailable", "reason": "goal database not found"}
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(db), uri=True, timeout=2)
        try:
            row = conn.execute(
                "SELECT status, tokens_used, time_used_seconds FROM thread_goals WHERE thread_id = ?",
                (session,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"probe": "unavailable", "reason": str(exc)}
    if row is None:
        return {"probe": "unavailable", "reason": "no goal recorded for this session"}
    return {"probe": "ok", "goal_status": row[0], "tokens_used": row[1], "time_used_seconds": row[2]}


def lane_commits(worktree):
    """Commits on the lane that no non-lane branch has."""
    refs = git_out(["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"], worktree).splitlines()
    others = [r for r in refs if "/" + LANE_BRANCH_PREFIX not in r + "/" and not r.endswith("/HEAD")]
    out = git_out(["rev-list", "--count", "HEAD", "--not"] + others, worktree)
    return int(out) if out.isdigit() else 0


def read_pane(target):
    rc, out, _ = run(["herdr", "agent", "read", target, "--source", "visible"])
    if rc != 0 or out.lstrip().startswith('{"error"'):
        rc, out, _ = run(["herdr", "pane", "read", target, "--source", "visible"])
    return out if rc == 0 else ""


def pane_state(text):
    """ready = composer visible and no parked list. Conservative: when unsure, not ready."""
    tail = [ln for ln in text.splitlines() if ln.strip()][-14:]
    parked = any(re.match(r"^\s*›\s*\d+\.\s", ln) for ln in tail)
    composer = any(re.match(r"^\s*›(?!\s*\d+\.\s)", ln) for ln in tail)
    shell = bool(tail) and not composer and not parked and "OpenAI Codex" not in "\n".join(tail[-6:])
    if parked:
        return "dialog"
    # The composer stays visible while a turn runs, so its presence alone does not mean idle.
    if any("esc to interrupt" in ln for ln in tail):
        return "working"
    if composer:
        return "ready"
    return "exited" if shell else "unknown"


def pane_tail(text, n=24):
    return "\n".join([ln.rstrip() for ln in text.splitlines() if ln.strip()][-n:])


# ---------- naming ----------

def sanitize_agent_name(change, taken):
    name = re.sub(r"[^a-z0-9_-]", "-", change.lower())
    if not re.match(r"^[a-z]", name):
        name = "c-" + name
    words = name.split("-")
    while len("-".join(words)) > AGENT_NAME_MAX and len(words) > 1:
        words.pop()
    name = "-".join(words)[:AGENT_NAME_MAX].rstrip("-_")
    if name in taken:
        suffix = "-" + format(int(datetime.datetime.now().timestamp()), "x")[-3:]
        name = name[:AGENT_NAME_MAX - len(suffix)].rstrip("-_") + suffix
    return name


def branch_taken(root, branch, has_origin):
    if git_out(["branch", "--list", branch], root):
        return True
    if has_origin and git_out(["ls-remote", "--heads", "origin", branch], root):
        return True
    return False


def pick_branch(root, change, has_origin):
    branch = LANE_BRANCH_PREFIX + change
    if branch_taken(root, branch, has_origin):
        branch += "-" + format(int(datetime.datetime.now().timestamp()), "x")[-3:]
    return branch


# ---------- plan ----------

VERIFY_HINT = re.compile(r"verif|验证|确认|校验|assert|test|check|expect", re.I)


FORGE_PREFS = os.path.expanduser("~/.claude/dispatch/forges.json")
VIA_CHOICES = ("gh", "glab", "handoff", "none")


def origin_info(root):
    url = git_out(["remote", "get-url", "origin"], root)
    if not url:
        return None
    if url.startswith(("/", ".", "~", "file://")):
        return {"url": url, "host": "local-path"}  # a bare repository on disk: no forge behind it
    m = re.match(r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^:/]+)[:/]", url)
    return {"url": url, "host": m.group(1).lower() if m else "unknown"}


def forge_prefs():
    try:
        with open(FORGE_PREFS) as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def forge_pref_write(host, pref):
    data = forge_prefs()
    if pref is None:
        data.pop(host, None)
    else:
        data[host] = pref
    os.makedirs(os.path.dirname(FORGE_PREFS), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(FORGE_PREFS))
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, FORGE_PREFS)


def guess_via(host):
    if host == "github.com" or host.endswith(".github.com"):
        return "gh"
    if "gitlab" in host:
        return "glab"
    return None


def cli_target(via, root, origin):
    """(what to pass as the repository, None) when the forge CLI is usable here, else (None, why not)."""
    if via == "gh":
        if run(["gh", "auth", "status"])[0] != 0:
            return None, "gh is missing or not authenticated"
        rc, out, _ = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], cwd=root)
        if rc != 0 or not out.strip():
            return None, "gh cannot resolve the target repository"
        return out.strip(), None
    if run(["glab", "auth", "status", "--hostname", origin["host"]])[0] != 0:
        return None, "glab is missing or not authenticated for " + origin["host"]
    return origin["url"], None  # glab -R accepts the git URL itself


def review_route(root, pr_base, want_review=True, override=None):
    """How a verified lane gets its review request (PR / MR). Pushing is plain git and works on any host;
    only opening the request depends on the forge.

    mode: review     this script opens it with gh or glab
          handoff    this script only pushes; the orchestrator opens it with a tool or skill of the runtime
          undecided  unknown host and nothing remembered: ask the user once, then `forge --set`
          push-only / local-only, each with a reason
    """
    origin = origin_info(root)
    if not origin:
        return {"mode": "local-only", "reason": "no origin remote"}
    route = {"host": origin["host"], "remote_url": origin["url"]}
    if git(["ls-remote", "--exit-code", "--heads", "origin", pr_base], root)[0] != 0:
        route.update(mode="push-only", reason="base '{}' is not a branch on origin".format(pr_base))
        return route
    if not want_review:
        route.update(mode="push-only", reason="--no-pr")
        return route
    pref = forge_prefs().get(origin["host"]) or {}
    via = override or pref.get("via") or guess_via(origin["host"])
    route["remembered"] = bool(pref.get("via")) and not override
    if not via:
        route.update(mode="undecided",
                     reason="unknown forge host '{}': ask the user once which tool opens review requests "
                            "here (gh / glab / a tool or skill of the runtime / none), then remember it "
                            "with `forge --set`".format(origin["host"]))
        return route
    route["via"] = via
    if via == "none":
        route.update(mode="push-only", reason="review requests are turned off for " + origin["host"])
    elif via == "handoff":
        route.update(mode="handoff", tool=pref.get("tool"))
    else:
        repo, why = cli_target(via, root, origin)
        if why:
            route.update(mode="push-only", reason=why)
        else:
            route.update(mode="review", repo=repo)
    return route


def find_review(root, route, branch, noted_url):
    """The review request already open for this branch, normalized to {id, url, state, draft}."""
    found = None
    if route.get("mode") == "review" and route.get("via") == "gh":
        rc, prs = jrun(["gh", "pr", "list", "--repo", route["repo"], "--head", branch, "--state", "all",
                        "--json", "number,url,state,isDraft"], cwd=root)
        if rc == 0 and prs:
            found = {"id": prs[0].get("number"), "url": prs[0].get("url"),
                     "state": str(prs[0].get("state", "")).lower(), "draft": bool(prs[0].get("isDraft"))}
    elif route.get("mode") == "review" and route.get("via") == "glab":
        rc, mrs = jrun(["glab", "mr", "list", "-R", route["repo"], "-s", branch, "-A", "-F", "json"], cwd=root)
        if rc == 0 and mrs:
            found = {"id": mrs[0].get("iid"), "url": mrs[0].get("web_url"),
                     "state": str(mrs[0].get("state", "")).lower(),
                     "draft": bool(mrs[0].get("draft") or mrs[0].get("work_in_progress"))}
    if not found and noted_url:
        found = {"id": None, "url": noted_url, "state": "noted", "draft": None}
    return found


def plan_one(root, change, pr_base, has_origin, taken_names, lanes):
    item = {"change": change, "eligible": False}
    rel = os.path.join("openspec", "changes", change)
    if not os.path.isdir(os.path.join(root, rel)):
        lane = next((l for l in lanes if l["change"] == change), None)
        item["reason"] = "already has a lane; use the status sub-command" if lane else "no such change in the main checkout"
        return item
    if any(l["change"] == change for l in lanes) or os.path.exists(os.path.join(lanes_dir(root), change)):
        item["reason"] = ("a lane, or a directory left over from a failed create, already exists at {}. "
                          "A live lane is handled by the status sub-command; a leftover has to be removed by the "
                          "user (herdr worktree remove) before this change can be dispatched again").format(
            os.path.join(lanes_dir(root), change))
        return item
    st = apply_status(root, change)
    if not st:
        item["reason"] = "openspec could not report this change"
        return item
    item.update(state=st["state"], remaining=st["progress"].get("remaining"), total=st["progress"].get("total"))
    if st["state"] == "blocked":
        item["reason"] = "planning incomplete; missing artifact(s): " + ", ".join(st["missing"])
        return item
    if st["state"] == "all_done" or not st["progress"].get("remaining"):
        item["reason"] = "no tasks remain"
        return item
    tracked = bool(git_out(["ls-files", "--", rel], root))
    dirty = bool(git_out(["status", "--porcelain", "--", rel], root))
    if tracked and dirty:
        item["reason"] = "change directory is tracked but has uncommitted modifications; commit or discard them first"
        return item
    item["dir_state"] = "tracked" if tracked else "untracked"
    if tracked:
        item["base_ref"] = "HEAD"
    else:
        on_origin = has_origin and git(["ls-remote", "--exit-code", "--heads", "origin", pr_base], root)[0] == 0
        item["base_ref"] = "origin/" + pr_base if on_origin else pr_base
    item["branch"] = pick_branch(root, change, has_origin)
    item["agent_name"] = sanitize_agent_name(change, taken_names)
    taken_names.add(item["agent_name"])
    item["worktree"] = os.path.join(lanes_dir(root), change)
    item["tasks_without_verification"] = [t.get("description", "")[:90] for t in st["tasks"]
                                          if not t.get("done") and not VERIFY_HINT.search(t.get("description", ""))]
    item["eligible"] = True
    return item


def cmd_plan(args):
    if not in_main_checkout():
        fail("run this from the main checkout, not from a linked worktree")
    root = main_root()
    pr_base = git_out(["branch", "--show-current"], root)
    if not pr_base:
        fail("the main checkout is on a detached HEAD; switch to a branch first")
    has_origin = git(["remote", "get-url", "origin"], root)[0] == 0
    changes = args.changes
    if not changes:
        rc, data = jrun(["openspec", "list", "--json"], cwd=root)
        changes = [c["name"] for c in (data or {}).get("changes", [])]
    agents = herdr_agents()
    taken = {a.get("name") for a in (agents or []) if a.get("name")}
    lanes = find_lanes(root)
    items = [plan_one(root, c, pr_base, has_origin, taken, lanes) for c in changes]
    emit({"ok": True, "repo": root, "pr_base": pr_base,
          "herdr_reachable": agents is not None,
          "review": review_route(root, pr_base, not args.no_pr),
          "changes": items})


# ---------- create ----------

def workspace_ids():
    rc, data = jrun(["herdr", "workspace", "list"])
    return {w.get("workspace_id") for w in ((data or {}).get("result") or {}).get("workspaces") or []}


def cmd_create(args):
    if not in_main_checkout():
        fail("run this from the main checkout, not from a linked worktree")
    root = main_root()
    change = args.change
    pr_base = git_out(["branch", "--show-current"], root)
    if not pr_base:
        fail("the main checkout is on a detached HEAD")
    has_origin = git(["remote", "get-url", "origin"], root)[0] == 0
    agents = herdr_agents()
    if agents is None:
        fail("herdr is not reachable; are you inside a herdr pane?")
    item = plan_one(root, change, pr_base, has_origin, {a.get("name") for a in agents if a.get("name")}, find_lanes(root))
    if not item.get("eligible"):
        fail("not dispatchable: " + item.get("reason", "unknown"), change=change)

    base_head_before = git_out(["rev-parse", pr_base], root)
    if item["base_ref"].startswith("origin/"):
        rc, _, err = git(["fetch", "origin", pr_base], root, timeout=180)
        if rc != 0:
            fail("git fetch origin failed: " + err.strip()[:300], change=change)

    wt, branch, name = item["worktree"], item["branch"], item["agent_name"]
    before = workspace_ids()
    rc, data = jrun(["herdr", "worktree", "create", "--cwd", root, "--branch", branch, "--base", item["base_ref"],
                     "--path", wt, "--label", name, "--no-focus"], timeout=180)
    result = (data or {}).get("result") or {}
    if rc != 0 or not (result.get("worktree") or {}).get("path"):
        fail("herdr worktree create failed", change=change, herdr=(data or {}).get("error") or data)
    new_ws = sorted(w for w in workspace_ids() - before if w)

    # Guard: never move the change anywhere but into the worktree that was just created on its branch.
    if real(git_out(["rev-parse", "--show-toplevel"], wt)) != real(wt) or git_out(["branch", "--show-current"], wt) != branch:
        fail("the new worktree is not what was asked for; nothing was moved", change=change, worktree=wt)

    rel = os.path.join("openspec", "changes", change)
    propose_commit = None
    if item["dir_state"] == "untracked":
        if os.path.exists(os.path.join(wt, rel)):
            fail("the base already contains {}; nothing was moved".format(rel), change=change, worktree=wt)
        os.makedirs(os.path.join(wt, "openspec", "changes"), exist_ok=True)
        os.rename(os.path.join(root, rel), os.path.join(wt, rel))
        rc1, _, e1 = git(["add", "--", rel], wt)
        rc2, _, e2 = git(["commit", "-m", "docs(openspec): propose " + change, "--", rel], wt)
        if rc1 != 0 or rc2 != 0:
            os.rename(os.path.join(wt, rel), os.path.join(root, rel))  # put the user's files back
            fail("could not commit the change on the lane branch; it was moved back: " + (e1 or e2).strip()[:300],
                 change=change, worktree=wt)
        propose_commit = git_out(["rev-parse", "--short", "HEAD"], wt)

    st = apply_status(wt, change) or {}
    book_update(root, change, pr_base=pr_base, created_at=now())
    emit({"ok": True, "change": change, "worktree": wt, "branch": branch, "agent_name": name,
          "base_ref": item["base_ref"], "pr_base": pr_base,
          "workspace_id": (result.get("workspace") or {}).get("workspace_id"),
          "pane_id": (result.get("root_pane") or {}).get("pane_id"),
          "new_workspaces": new_ws,
          "propose_commit": propose_commit,
          "base_head_unchanged": git_out(["rev-parse", pr_base], root) == base_head_before,
          "state_in_lane": st.get("state")})


# ---------- launch ----------

def cmd_launch(args):
    root = main_root()
    lane = find_lane(root, args.change)
    if not lane:
        fail("no lane for this change; run create first", change=args.change)
    agents = herdr_agents()
    if agents is None:
        fail("herdr is not reachable")
    if agents_in(agents, lane["worktree"]):
        fail("an agent is already running in this lane", change=args.change)
    ws, pane = lane_pane(root, lane["worktree"])
    if not pane:
        fail("cannot find the herdr pane for this lane", change=args.change, workspace_id=ws)
    name = sanitize_agent_name(args.change, {a.get("name") for a in agents if a.get("name")})
    common = real(git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], root))
    posture = "strict" if args.strict else "auto-review"
    flags = ["--no-alt-screen"]
    # auto-review implies workspace-write and conflicts with --sandbox; strict must name the sandbox
    # explicitly, because an untrusted directory defaults to read-only and then rejects --add-dir.
    flags += (["--sandbox", "workspace-write", "--ask-for-approval", "on-request"] if args.strict
              else ["--approve-for-me"])
    flags += ["--add-dir", common]  # a linked worktree commits into the main repo's .git
    rc, data = jrun(["herdr", "agent", "start", name, "--kind", "codex", "--pane", pane,
                     "--timeout", str(START_TIMEOUT_MS), "--"] + flags, timeout=START_TIMEOUT_MS // 1000 + 30)
    err = ((data or {}).get("error") or {}).get("code")
    text = read_pane(name) or read_pane(pane)
    state = pane_state(text)
    book_update(root, args.change, posture=posture, agent_name=name)
    emit({"ok": state in ("ready", "dialog"), "change": args.change, "agent_name": name, "pane_id": pane,
          "workspace_id": ws, "posture": posture, "start_result": err or "started", "state": state,
          "pane_tail": pane_tail(text)}, 0 if state in ("ready", "dialog") else 1)


# ---------- prompt ----------

def cmd_prompt(args):
    root = main_root()
    lane = find_lane(root, args.change)
    if not lane:
        fail("no lane for this change", change=args.change)
    mine = agents_in(herdr_agents(), lane["worktree"])
    if len(mine) != 1:
        fail("expected exactly one agent in this lane, found {}; nothing was sent".format(len(mine)),
             change=args.change)
    agent = mine[0]
    target = agent_ref(agent)
    session = (agent.get("agent_session") or {}).get("value")
    # Never type into a turn that is in flight: codex drops slash commands mid-turn and queues plain text.
    if agent.get("agent_status") == "working":
        fail("the lane is working; nothing was sent", change=args.change)
    text = read_pane(target)
    state = pane_state(text)
    if state != "ready":
        fail("the pane is not at an idle composer (state: {}); nothing was sent".format(state),
             change=args.change, pane_tail=pane_tail(text))

    c = args.change
    if args.goal or args.plain:
        # herdr reports no session until the first turn ends, so the session alone cannot prove
        # "not primed yet"; the bookkeeping mark covers that window.
        primed = book_load(root).get("lanes", {}).get(c, {}).get("goal_sent_at")
        if primed or session or goal_probe(session).get("probe") == "ok" or lane_commits(lane["worktree"]) > 1:
            fail("this lane already received its goal; a goal is sent once", change=c, session=session,
                 goal_sent_at=primed)
        body = GOAL_TEXT.format(c=c)
        message = ("/goal " + body) if args.goal else body
    elif args.resume:
        message = "/goal resume"
    elif args.correct:
        message = CORRECT_TEXT.format(c=c, detail=args.correct.strip())
    else:
        message = CONTINUE_TEXT.format(c=c)

    rc, data = jrun(["herdr", "agent", "prompt", target, message])
    if args.goal or args.plain:
        # Marked even when the call errors: an interrupted prompt call has usually delivered its text.
        book_update(root, c, goal_sent_at=now(), goal_mode="goal" if args.goal else "plain")
    if args.cont:
        st = apply_status(lane["worktree"], c) or {}
        nudges = book_load(root).get("lanes", {}).get(c, {}).get("nudges", [])
        nudges.append({"at": now(), "head": git_out(["rev-parse", "HEAD"], lane["worktree"]),
                       "complete": (st.get("progress") or {}).get("complete")})
        book_update(root, c, nudges=nudges)
    after = agents_in(herdr_agents(), lane["worktree"])
    emit({"ok": rc == 0, "change": c, "sent": message.split(" ", 1)[0] if message.startswith("/") else "prompt",
          "herdr": ((data or {}).get("error") or {}).get("code"),
          "agent_status": after[0].get("agent_status") if after else None,
          "session": ((after[0].get("agent_session") or {}).get("value") if after else None),
          "note": "delivery is judged from the lane on the next list, not from this call"}, 0 if rc == 0 else 1)


# ---------- list ----------

def verify_record(worktree, change):
    path = os.path.join(worktree, "openspec", "changes", change, "verify.md")
    try:
        with open(path) as fh:
            m = re.search(r"^verified_commit:\s*([0-9a-f]{7,40})", fh.read(), re.M)
    except OSError:
        return None
    return {"verified_commit": m.group(1) if m else None}


def verification_current(worktree, change, rec):
    """True when HEAD is the verify.md commit sitting directly on the verified commit."""
    if not rec or not rec.get("verified_commit"):
        return False
    parent = git_out(["rev-parse", "HEAD~1"], worktree)
    files = git_out(["show", "--name-only", "--format=", "HEAD"], worktree).split()
    only_verify = files == [os.path.join("openspec", "changes", change, "verify.md")]
    return only_verify and parent.startswith(rec["verified_commit"])


def lane_overview(root, lane, agents, book, remote_heads, route):
    wt, c = lane["worktree"], lane["change"]
    info = dict(lane)
    mine = agents_in(agents, wt) if agents is not None else []
    agent = mine[0] if len(mine) == 1 else None
    session = (agent or {}).get("agent_session", {}) or {}
    session = session.get("value") or (book.get(c) or {}).get("session")
    st = apply_status(wt, c) or {}
    prog = st.get("progress") or {}
    info.update(
        agents_in_lane=len(mine),
        agent=({"ref": agent_ref(agent), "status": agent.get("agent_status"), "pane_id": agent.get("pane_id"),
                "workspace_id": agent.get("workspace_id")} if agent else None),
        session=session, state=st.get("state"), complete=prog.get("complete"), total=prog.get("total"),
        commits=lane_commits(wt), tree_clean=not git_out(["status", "--porcelain"], wt),
        goal=goal_probe(session), book=book.get(c) or {})
    rec = verify_record(wt, c)
    info["verified"] = verification_current(wt, c, rec)
    info["on_origin"] = None if remote_heads is None else lane["branch"] in remote_heads
    remote_sha = (remote_heads or {}).get(lane["branch"])
    info["review"] = None
    if info["on_origin"]:
        info["review"] = find_review(root, route, lane["branch"], info["book"].get("review_url"))

    nudges = info["book"].get("nudges") or []
    head = git_out(["rev-parse", "HEAD"], wt)
    stale = 0
    for n in reversed(nudges):
        if n.get("head") == head and n.get("complete") == prog.get("complete"):
            stale += 1
        else:
            break
    info["nudges_without_progress"] = stale

    status = (agent or {}).get("agent_status")
    goal = info["goal"].get("goal_status")
    done = st.get("state") == "all_done" and info["tree_clean"]
    if agents is None:
        verdict = "herdr_unreachable"
    elif len(mine) > 1:
        verdict = "ambiguous_agent"
    # What sits on origin is exactly the verified head: published, whoever ran the push, and
    # derivable without bookkeeping. A pull request is also proof that the orchestrator published.
    elif info["verified"] and (info["review"] or remote_sha == head):
        verdict = "published"
    elif info["on_origin"] and not info["review"] and not info["book"].get("pushed_sha"):
        verdict = "lane_pushed_itself"
    elif info["verified"]:
        verdict = "verified_unpublished"
    elif not mine:
        verdict = "no_agent"
    elif status == "blocked":
        verdict = "blocked"
    elif goal in ("paused", "usage_limited", "budget_limited", "blocked"):
        verdict = "goal_" + goal
    elif done and status != "working":
        verdict = "claims_done"
    elif status == "working":
        verdict = "working"
    else:
        verdict = "idle_unfinished"
    if info["book"].get("escalated") and verdict not in ("published", "working", "claims_done"):
        verdict = "awaiting_user"
    info["verdict"] = verdict
    return info


def cmd_list(args):
    root = main_root()
    lanes = find_lanes(root)
    agents = herdr_agents()
    book = book_load(root).get("lanes", {})
    remote_heads = None
    if lanes and not args.no_remote and git(["remote", "get-url", "origin"], root)[0] == 0:
        out = git_out(["ls-remote", "--heads", "origin", LANE_BRANCH_PREFIX + "*"], root)
        remote_heads = {ln.split("refs/heads/", 1)[1]: ln.split()[0] for ln in out.splitlines() if "refs/heads/" in ln}
    route = {}
    if remote_heads is not None:
        base = next((b.get("pr_base") for b in book.values() if b.get("pr_base")), None)
        route = review_route(root, base or git_out(["branch", "--show-current"], root))
    rows = [lane_overview(root, l, agents, book, remote_heads, route) for l in lanes]
    settled = {"published", "awaiting_user", "lane_pushed_itself", "ambiguous_agent", "no_agent"}
    if args.table:
        print("{:<28} {:<20} {:<8} {:>5}  {:>7}  {:<5}  {}".format("CHANGE", "VERDICT", "AGENT", "N/M", "COMMITS", "TREE", "REVIEW"))
        for r in rows:
            rv = r["review"]
            label = "-"
            if rv:
                label = ("#{} ".format(rv["id"]) if rv.get("id") else "") + ("draft" if rv.get("draft") else rv.get("state") or "")
            print("{:<28} {:<20} {:<8} {:>5}  {:>7}  {:<5}  {}".format(
                r["change"][:28], r["verdict"], (r["agent"] or {}).get("status") or "-",
                "{}/{}".format(r["complete"], r["total"]), r["commits"], "clean" if r["tree_clean"] else "dirty",
                label.strip() or "-"))
        sys.exit(0)
    emit({"ok": True, "repo": root, "herdr_reachable": agents is not None, "lanes": rows,
          "all_settled": bool(rows) and all(r["verdict"] in settled for r in rows)})


# ---------- note ----------

def cmd_note(args):
    root = main_root()
    if args.what == "clear":
        lane = book_update(root, args.change, escalated=None, nudges=None)
    elif args.what == "review-url":
        if not args.reason or not re.match(r"^https?://", args.reason):
            fail("review-url needs the URL of the review request")
        lane = book_update(root, args.change, review_url=args.reason)
    else:
        if not args.reason:
            fail("escalate needs a reason")
        lane = book_update(root, args.change, escalated={"at": now(), "reason": args.reason})
    emit({"ok": True, "change": args.change, "book": lane})


# ---------- record-verify ----------

def cmd_record_verify(args):
    root = main_root()
    lane = find_lane(root, args.change)
    if not lane:
        fail("no lane for this change", change=args.change)
    wt, c = lane["worktree"], args.change
    try:
        report = json.load(sys.stdin)
    except ValueError:
        fail('stdin must be JSON: {"tasks":[{"id","check","result","evidence"}], "deviations":[...]}')
    tasks = report.get("tasks") or []
    if not tasks or any(t.get("result") != "pass" for t in tasks):
        fail("verify.md records a PASSED verification; every task must have result 'pass'", change=c)
    st = apply_status(wt, c) or {}
    if st.get("state") != "all_done":
        fail("tasks remain; nothing to record", change=c, state=st.get("state"))
    if git_out(["status", "--porcelain"], wt):
        fail("the lane's working tree is not clean", change=c)
    rec = verify_record(wt, c)
    if verification_current(wt, c, rec):
        emit({"ok": True, "change": c, "already_recorded": True, "verified_commit": rec["verified_commit"]})
    if lane_commits(wt) < 2 and not st.get("tasks"):
        fail("the lane has no work beyond the propose commit", change=c)

    head = git_out(["rev-parse", "HEAD"], wt)
    book = book_load(root).get("lanes", {}).get(c, {})
    codex_version = run(["codex", "--version"])[1].strip().splitlines()[0:1]
    lines = ["# Verification", "",
             "verified_commit: " + head,
             "verified_at: " + now(),
             "executor: " + (codex_version[0] if codex_version else "codex (version unknown)"),
             "approval_posture: " + book.get("posture", "unknown"),
             "verified_by: orchestrator (re-ran every check below inside the lane worktree)", "",
             "## Checks", "", "| Task | Check | Result | Evidence |", "|---|---|---|---|"]
    for t in tasks:
        lines.append("| {} | `{}` | {} | {} |".format(
            t.get("id", ""), str(t.get("check", "")).replace("|", "\\|").replace("`", "'"),
            t.get("result", ""), str(t.get("evidence", "")).replace("|", "\\|").replace("\n", " ")))
    lines += ["", "## Deviations from the plan", ""]
    lines += ["- " + d for d in report.get("deviations") or []] or ["None reported."]
    rel = os.path.join("openspec", "changes", c, "verify.md")
    with open(os.path.join(wt, rel), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    rc1, _, e1 = git(["add", "--", rel], wt)
    rc2, _, e2 = git(["commit", "-m", "docs(openspec): record verification of " + c, "--", rel], wt)
    if rc1 != 0 or rc2 != 0:
        fail("could not commit verify.md: " + (e1 or e2).strip()[:300], change=c)
    emit({"ok": True, "change": c, "verified_commit": head, "verify_md": os.path.join(wt, rel)})


# ---------- publish ----------

def manual_command(via, repo, base, branch, title, body_file, ready):
    if via == "gh":
        return "gh pr create --repo {} --base {} --head {} --title '{}' --body-file {}{}".format(
            repo, base, branch, title, body_file, "" if ready else " --draft")
    if via == "glab":
        return "glab mr create -R {} -s {} -b {} -t '{}' -d \"$(cat {})\" --yes --no-editor{}".format(
            repo, branch, base, title, body_file, "" if ready else " --draft")
    return None


def cmd_publish(args):
    root = main_root()
    lane = find_lane(root, args.change)
    if not lane:
        fail("no lane for this change", change=args.change)
    wt, c, branch = lane["worktree"], args.change, lane["branch"]
    if not verification_current(wt, c, verify_record(wt, c)):
        fail("no current verification: run record-verify first, and re-verify if the lane committed since", change=c)
    book = book_load(root).get("lanes", {}).get(c, {})
    base = book.get("pr_base") or git_out(["branch", "--show-current"], root)
    head = git_out(["rev-parse", "HEAD"], wt)
    route = review_route(root, base, not args.no_pr, override=args.via)
    if route["mode"] == "local-only":
        emit({"ok": True, "change": c, "pushed": None, "review": None, "route": route, "note": "verified; stays local"})

    remote_sha = git_out(["ls-remote", "--heads", "origin", branch], root).split("\t")[0]
    if remote_sha and remote_sha != head and not book.get("pushed_sha") and not args.ack_remote:
        fail("the lane branch is already on origin and this orchestrator did not push it: the lane crossed its "
             "boundary. Ask the user; re-run with --ack-remote only if they accept that push.", change=c, branch=branch)

    attempts = int(book.get("publish_attempts", 0))
    if attempts >= MAX_PUBLISH_ATTEMPTS:
        fail("publishing already failed {} times; hand the command to the user".format(attempts), change=c,
             last_error=book.get("last_publish_error"))

    # 1) Push. Plain git: the same on GitHub, GitLab, an internal forge, or a bare repository.
    refspec = "refs/heads/{0}:refs/heads/{0}".format(branch)
    rc, _, err = git(["push", "-u", "origin", refspec], wt, timeout=300)
    if rc != 0:
        book_update(root, c, publish_attempts=attempts + 1, last_publish_error=err.strip()[:400])
        fail("push was rejected; never force it", change=c, git=err.strip()[:400])
    book_update(root, c, pushed_sha=head)

    # 2) The review request's text lives in a file first, so whichever tool opens it receives the same thing.
    body_file = args.body_file
    if not body_file:
        body_file = os.path.join(os.path.dirname(bookkeeping_path(root)), c + "-review.md")
        os.makedirs(os.path.dirname(body_file), exist_ok=True)
        with open(body_file, "w") as fh, open(os.path.join(wt, "openspec", "changes", c, "verify.md")) as src:
            fh.write("Applies the OpenSpec change `{}`. Written by codex in an isolated lane; "
                     "verified independently by the orchestrator before publishing.\n\n".format(c) + src.read())
    handoff = {"remote_url": route.get("remote_url"), "host": route.get("host"), "source_branch": branch,
               "target_branch": base, "title": args.title, "body_file": body_file, "draft": not args.ready,
               "tool": route.get("tool")}

    # 3) Open it here only when the forge has a CLI this script drives; otherwise hand the pieces over.
    if route["mode"] != "review":
        emit({"ok": True, "change": c, "pushed": head, "review": None, "route": route, "handoff": handoff,
              "next": "open the review request with the tool or skill the runtime has for this forge, "
                      "then record it: note {} review-url <url>".format(c)})

    existing = find_review(root, route, branch, None)
    if existing:
        book_update(root, c, review_url=existing.get("url"))
        emit({"ok": True, "change": c, "pushed": head, "review": existing, "reused": True})

    via, repo = route["via"], route["repo"]
    if via == "gh":
        cmd = ["gh", "pr", "create", "--repo", repo, "--base", base, "--head", branch,
               "--title", args.title, "--body-file", body_file] + ([] if args.ready else ["--draft"])
    else:
        with open(body_file) as fh:
            text = fh.read()
        cmd = ["glab", "mr", "create", "-R", repo, "-s", branch, "-b", base, "-t", args.title, "-d", text,
               "--yes", "--no-editor"] + ([] if args.ready else ["--draft"])
    rc, out, err = run(cmd, cwd=root, timeout=120)
    if rc != 0:
        book_update(root, c, publish_attempts=attempts + 1, last_publish_error=err.strip()[:400])
        fail(via + " could not open the review request", change=c, tool_error=err.strip()[:400], handoff=handoff,
             run_this_yourself=manual_command(via, repo, base, branch, args.title, body_file, args.ready))
    urls = re.findall(r"https?://\S+", out + "\n" + err)
    url = urls[-1] if urls else None
    book_update(root, c, publish_attempts=None, last_publish_error=None, review_url=url)
    emit({"ok": True, "change": c, "pushed": head, "review": {"url": url, "draft": not args.ready}, "via": via})


# ---------- forge ----------

def cmd_forge(args):
    root = main_root()
    origin = origin_info(root)
    if not origin:
        fail("no origin remote")
    host = origin["host"]
    if args.forget:
        forge_pref_write(host, None)
    elif args.set:
        if args.set == "handoff" and not args.tool:
            fail("handoff needs --tool: the name of the tool or skill that opens review requests on " + host)
        pref = {"via": args.set, "set_at": now()}
        if args.tool:
            pref["tool"] = args.tool
        forge_pref_write(host, pref)
    base = git_out(["branch", "--show-current"], root)
    emit({"ok": True, "host": host, "remote_url": origin["url"], "guessed": guess_via(host),
          "remembered": forge_prefs().get(host), "route": review_route(root, base) if base else None,
          "prefs_file": FORGE_PREFS})


# ---------- cli ----------

def main():
    ap = argparse.ArgumentParser(prog="lane.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan"); p.add_argument("changes", nargs="*"); p.add_argument("--no-pr", action="store_true")
    p = sub.add_parser("create"); p.add_argument("change")
    p = sub.add_parser("launch"); p.add_argument("change"); p.add_argument("--strict", action="store_true")
    p = sub.add_parser("prompt"); p.add_argument("change")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--goal", action="store_true"); g.add_argument("--plain", action="store_true")
    g.add_argument("--continue", dest="cont", action="store_true"); g.add_argument("--resume", action="store_true")
    g.add_argument("--correct", metavar="TEXT")
    p = sub.add_parser("list"); p.add_argument("--table", action="store_true"); p.add_argument("--no-remote", action="store_true")
    p = sub.add_parser("note"); p.add_argument("change"); p.add_argument("what", choices=["escalate", "clear", "review-url"])
    p.add_argument("reason", nargs="?")
    p = sub.add_parser("record-verify"); p.add_argument("change")
    p = sub.add_parser("publish"); p.add_argument("change"); p.add_argument("--title", required=True)
    p.add_argument("--body-file"); p.add_argument("--ready", action="store_true")
    p.add_argument("--no-pr", action="store_true"); p.add_argument("--ack-remote", action="store_true")
    p.add_argument("--via", choices=["gh", "glab", "handoff"])
    p = sub.add_parser("forge"); p.add_argument("--set", choices=list(VIA_CHOICES)); p.add_argument("--tool")
    p.add_argument("--forget", action="store_true")
    args = ap.parse_args()
    handlers = {"plan": cmd_plan, "create": cmd_create, "launch": cmd_launch, "prompt": cmd_prompt,
                "list": cmd_list, "note": cmd_note, "record-verify": cmd_record_verify, "publish": cmd_publish,
                "forge": cmd_forge}
    if args.cmd not in handlers:
        ap.print_help()
        sys.exit(2)
    try:
        handlers[args.cmd](args)
    except SystemExit:
        raise
    except Exception as exc:  # last resort: still one JSON object, never a traceback
        fail("{}: {}".format(type(exc).__name__, exc))


if __name__ == "__main__":
    main()
