#!/usr/bin/env python3
"""ar.py - the loop behind /autoresearch: one subject, many rounds, no session.

Every subcommand prints exactly one JSON object on stdout and never raises.
Exit code: 0 = done, 1 = refused or failed (see "error"), 2 = usage.

  doctor [--repo DIR]                      what is installed and what state the repo is in
  init [--repo DIR] [--name N] [--subject S ...] [--harness T] [--describe TEXT]
                                           scaffold autoresearch/research.json + subject templates
  run <subject> [--repo DIR] [--rounds N] [--dry-prompt]
                                           drive rounds until a stop condition; the loop itself
  status [<subject>] [--repo DIR]          every subject's summary, rebuilt from the checkpoints
  report [--repo DIR]                      regenerate <research>.ar/report/index.html
  serve [--repo DIR] [--port N] [--no-open]
                                           serve the report at http://127.0.0.1:<port>/, re-read
                                           from the ledger on every request; the page polls it
  example <name> <dir>                     generate a self-contained research to try the loop on
                                           (<name> is a directory under examples/)

A round is: build prompt -> harness -> boundary check -> gate -> score -> commit
-> decide (keep / discard / crash / error) -> revert unless kept -> checkpoint
-> report -> stop conditions. The runner is deliberately dumb: all intelligence
lives in the agent it calls and in the scorer the person writes.

Progress goes to stderr and to <research>.ar/runs/<run-id>.log; stdout stays JSON.

Standard library only; runs on Python 3.9.
"""

import argparse
import datetime
import errno
import fnmatch
import glob
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEF_DIR = "autoresearch"            # the definition directory inside the target repo
STATUSES = ("keep", "discard", "crash", "error")
ALWAYS_LOCKED = DEF_DIR + "/**"     # the scorer is the person's lever; the agent never touches it
RECENT_ROUNDS = 5
HARNESS_TYPES = ("claude", "codex", "shell")
# claude -p reports these in `subtype` when a cap you asked for stops the agent. That is the cap
# working, not the harness failing: whatever the agent left in the tree is still measured.
CUT_OFF_SUBTYPES = ("error_max_turns", "error_max_budget_usd")
ALLOWED_KEYS = {
    "research": ("name", "description", "ar_dir", "direction", "harness", "subjects"),
    "harness": ("type", "model", "max_turns", "timeout_sec", "max_budget_usd", "command", "args",
                "env"),
    "subject": ("name", "program", "score", "gate", "editable", "locked", "depends_on",
                "agent_may_score", "max_rounds", "max_consecutive_discards",
                "max_consecutive_errors", "target_score", "budget", "recent_rounds", "harness"),
    "budget": ("minutes", "tokens"),
}

# Set by the SIGINT handler: 1 = finish this round then stop, 2 = kill the harness now.
INTERRUPT = 0
CHILD_PGID = None


class Refusal(Exception):
    """A reason to not do the thing, phrased for the person who asked."""

    def __init__(self, message, **extra):
        Exception.__init__(self, message)
        self.extra = extra


class UsageError(Exception):
    """argparse wanted to print to stderr and exit; the caller wants JSON instead."""

    def __init__(self, message, usage):
        Exception.__init__(self, message)
        self.usage = usage


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message, self.format_usage().strip())


# --------------------------------------------------------------------------- utils


def now_iso():
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def ms(t0):
    return int((time.time() - t0) * 1000)


def read_text(path, default=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


def write_text(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def read_json(path, default=None):
    text = read_text(path)
    if text is None:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def tail(text, lines=6, chars=600):
    text = (text or "").strip()
    if not text:
        return ""
    return "\n".join(text.splitlines()[-lines:])[-chars:]


def strip_doc(obj):
    """research.json carries its own documentation in _doc keys; they are not config."""
    if isinstance(obj, dict):
        return dict((k, strip_doc(v)) for k, v in obj.items() if not k.startswith("_"))
    if isinstance(obj, list):
        return [strip_doc(v) for v in obj]
    return obj


def reject_unknown(obj, kind, where):
    """A misspelt key would switch something off without a word - a stop condition, say, on a
    loop nobody is watching. Notes go in keys that start with an underscore."""
    if not isinstance(obj, dict):
        raise Refusal("{}/research.json: {} must be an object".format(DEF_DIR, where))
    unknown = sorted(k for k in obj if k not in ALLOWED_KEYS[kind])
    if unknown:
        raise Refusal("{}/research.json: {} has unknown key(s): {}. Allowed: {}".format(
            DEF_DIR, where, ", ".join(unknown), ", ".join(ALLOWED_KEYS[kind])),
            unknown_keys=unknown)


def path_matches(path, patterns):
    """fnmatch-style match where * also crosses directory separators.

    `autoresearch/**` matches `autoresearch/subjects/cases/score`;
    `cases/*.json` matches `cases/a.json`; a bare directory name matches its contents.
    """
    path = path.replace(os.sep, "/").lstrip("./")
    for pat in patterns or []:
        pat = pat.replace(os.sep, "/").lstrip("./")
        if not pat:
            continue
        if fnmatch.fnmatchcase(path, pat):
            return pat
        if pat.endswith("/**") and (path == pat[:-3] or path.startswith(pat[:-2])):
            return pat
        if pat.endswith("/") and path.startswith(pat):
            return pat
        if "*" not in pat and "?" not in pat and path.startswith(pat.rstrip("/") + "/"):
            return pat
    return None


def which(cmd):
    return shutil.which(cmd)


def tool_version(cmd, args):
    """Availability is what the tool prints when asked, not what a path check guesses."""
    path = which(cmd)
    if not path:
        return {"available": False, "path": None, "version": None}
    try:
        p = subprocess.run([cmd] + args, capture_output=True, text=True, timeout=30)
        out = (p.stdout or p.stderr or "").strip().splitlines()
        return {"available": p.returncode == 0, "path": path,
                "version": out[0].strip() if out else None}
    except Exception as exc:  # noqa: BLE001 - a tool that cannot be asked is unavailable
        return {"available": False, "path": path, "version": None, "error": str(exc)[:160]}


# ----------------------------------------------------------------------------- git


def git(args, cwd, check=True):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise Refusal("git {} failed: {}".format(" ".join(args), tail(p.stderr or p.stdout, 3)))
    return p


def git_out(args, cwd):
    return git(args, cwd).stdout.strip()


def repo_root(start):
    start = os.path.abspath(start or ".")
    if not os.path.isdir(start):
        raise Refusal("{} is not a directory".format(start))
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal("{} is not inside a git repository".format(start))
    return p.stdout.strip()


def porcelain(repo):
    """[(code, path)] for every change in the tree, untracked files included."""
    out = []
    raw = git(["status", "--porcelain", "-z", "--untracked-files=all"], repo).stdout
    fields = [f for f in raw.split("\0") if f]
    i = 0
    while i < len(fields):
        entry = fields[i]
        code, path = entry[:2], entry[3:]
        if code[0] in ("R", "C") and i + 1 < len(fields):
            i += 1  # rename/copy source follows; the destination path is what changed
        out.append((code.strip() or "??", path))
        i += 1
    return out


def current_branch(repo):
    p = git(["symbolic-ref", "--quiet", "--short", "HEAD"], repo, check=False)
    return p.stdout.strip() or None


def head_sha(repo):
    p = git(["rev-parse", "HEAD"], repo, check=False)
    return p.stdout.strip() if p.returncode == 0 else None


def tree_sha(repo, ref="HEAD"):
    p = git(["rev-parse", ref + "^{tree}"], repo, check=False)
    return p.stdout.strip() if p.returncode == 0 else None


def is_ancestor(repo, a, b):
    return git(["merge-base", "--is-ancestor", a, b], repo, check=False).returncode == 0


def commit_is_empty(repo, sha):
    """An agent that changed nothing leaves an empty commit; it must not be reverted."""
    parents = git_out(["rev-list", "--parents", "-n", "1", sha], repo).split()
    if len(parents) < 2:
        return False  # root commit: whatever it holds, it is not empty
    return tree_sha(repo, sha) == tree_sha(repo, parents[1])


# -------------------------------------------------------------------------- config


def research_path(repo):
    return os.path.join(repo, DEF_DIR, "research.json")


def load_research(repo):
    path = research_path(repo)
    raw = read_json(path)
    if raw is None:
        if not os.path.exists(path):
            raise Refusal("no research definition at {}/research.json; run init first".format(DEF_DIR))
        raise Refusal("{}/research.json is not valid JSON".format(DEF_DIR))
    cfg = strip_doc(raw)
    reject_unknown(cfg, "research", "the top level")
    name = cfg.get("name")
    if not name or not isinstance(name, str):
        raise Refusal("{}/research.json: name is required".format(DEF_DIR))
    if not re.match(r"^[A-Za-z0-9][\w.-]*$", name):
        raise Refusal("{}/research.json: name {!r} must be a plain identifier "
                      "(letters, digits, dot, dash, underscore)".format(DEF_DIR, name))
    cfg["name"] = name
    cfg["description"] = cfg.get("description") or ""
    cfg["direction"] = cfg.get("direction") or "max"
    if cfg["direction"] not in ("max", "min"):
        raise Refusal("{}/research.json: direction must be \"max\" or \"min\"".format(DEF_DIR))
    cfg["harness"] = cfg.get("harness") or {}
    reject_unknown(cfg["harness"], "harness", "harness")
    subjects = cfg.get("subjects")
    if not isinstance(subjects, list) or not subjects:
        raise Refusal("{}/research.json: subjects must be a non-empty array".format(DEF_DIR))

    names = []
    resolved = []
    for i, raw_sub in enumerate(subjects):
        if not isinstance(raw_sub, dict) or not raw_sub.get("name"):
            raise Refusal("{}/research.json: subjects[{}] needs a name".format(DEF_DIR, i))
        resolved.append(resolve_subject(cfg, raw_sub))
        names.append(raw_sub["name"])
    if len(set(names)) != len(names):
        raise Refusal("{}/research.json: duplicate subject names {}".format(DEF_DIR, names))
    for sub in resolved:
        for dep in sub["depends_on"]:
            if dep not in names:
                raise Refusal("{}/research.json: subject {} depends_on {!r}, which is not a "
                              "subject in this research (have: {})".format(
                                  DEF_DIR, sub["name"], dep, ", ".join(names)))
            if dep == sub["name"]:
                raise Refusal("{}/research.json: subject {} depends on itself".format(
                    DEF_DIR, sub["name"]))
    cfg["subjects"] = resolved
    cfg["ar_dir"] = resolve_ar_dir(repo, cfg)
    return cfg


def resolve_subject(cfg, raw):
    name = raw["name"]
    reject_unknown(raw, "subject", "subject {}".format(name))
    reject_unknown(raw.get("budget") or {}, "budget", "subject {} budget".format(name))
    reject_unknown(raw.get("harness") or {}, "harness", "subject {} harness".format(name))
    base = "{}/subjects/{}".format(DEF_DIR, name)
    sub = {
        "name": name,
        "program": raw.get("program") or base + "/program.md",
        "score": raw.get("score") or base + "/score",
        "gate": raw.get("gate") or base + "/gate",
        "editable": raw.get("editable") or [],
        "locked": [ALWAYS_LOCKED] + [p for p in (raw.get("locked") or []) if p != ALWAYS_LOCKED],
        "depends_on": raw.get("depends_on") or [],
        "agent_may_score": bool(raw.get("agent_may_score", False)),
        "max_rounds": raw.get("max_rounds"),
        "max_consecutive_discards": raw.get("max_consecutive_discards"),
        "max_consecutive_errors": raw.get("max_consecutive_errors", 3),
        "target_score": raw.get("target_score"),
        "budget": raw.get("budget") or {},
        "recent_rounds": raw.get("recent_rounds", RECENT_ROUNDS),
    }
    for key in ("editable", "locked", "depends_on"):
        if not isinstance(sub[key], list) or any(not isinstance(v, str) for v in sub[key]):
            raise Refusal("{}/research.json: subject {}: {} must be an array of strings".format(
                DEF_DIR, name, key))
    for key in ("max_rounds", "max_consecutive_discards", "max_consecutive_errors"):
        if sub[key] is not None and not (isinstance(sub[key], int) and sub[key] > 0):
            raise Refusal("{}/research.json: subject {}: {} must be a positive integer or "
                          "null".format(DEF_DIR, name, key))
    if sub["target_score"] is not None and not isinstance(sub["target_score"], (int, float)):
        raise Refusal("{}/research.json: subject {}: target_score must be a number or null".format(
            DEF_DIR, name))
    if not isinstance(sub["budget"], dict):
        raise Refusal("{}/research.json: subject {}: budget must be an object".format(DEF_DIR, name))
    for key in ("minutes", "tokens"):
        val = sub["budget"].get(key)
        if val is not None and not isinstance(val, (int, float)):
            raise Refusal("{}/research.json: subject {}: budget.{} must be a number or null".format(
                DEF_DIR, name, key))
    merged = dict(cfg.get("harness") or {})
    merged.update(raw.get("harness") or {})
    sub["harness"] = resolve_harness(name, merged)
    return sub


def resolve_harness(subject_name, h):
    out = {
        "type": h.get("type") or "shell",
        "model": h.get("model"),
        "max_turns": h.get("max_turns", 40),
        "timeout_sec": h.get("timeout_sec", 1800),
        "max_budget_usd": h.get("max_budget_usd"),
        "command": h.get("command"),
        "args": h.get("args") or [],
        "env": h.get("env") or {},
    }
    if out["type"] not in HARNESS_TYPES:
        raise Refusal("{}/research.json: subject {}: harness.type must be one of {}".format(
            DEF_DIR, subject_name, ", ".join(HARNESS_TYPES)))
    if out["type"] == "shell" and not out["command"]:
        raise Refusal("{}/research.json: subject {}: the shell harness needs harness.command".format(
            DEF_DIR, subject_name))
    if not isinstance(out["env"], dict) or any(not isinstance(v, str) for v in out["env"].values()):
        raise Refusal("{}/research.json: subject {}: harness.env must be an object of "
                      "strings".format(DEF_DIR, subject_name))
    if not isinstance(out["timeout_sec"], (int, float)) or out["timeout_sec"] <= 0:
        raise Refusal("{}/research.json: subject {}: harness.timeout_sec must be a positive "
                      "number".format(DEF_DIR, subject_name))
    if out["max_turns"] is not None and not (isinstance(out["max_turns"], int) and
                                             out["max_turns"] > 0):
        raise Refusal("{}/research.json: subject {}: harness.max_turns must be a positive "
                      "integer or null".format(DEF_DIR, subject_name))
    if out["max_budget_usd"] is not None and not (isinstance(out["max_budget_usd"], (int, float))
                                                  and out["max_budget_usd"] > 0):
        raise Refusal("{}/research.json: subject {}: harness.max_budget_usd must be a positive "
                      "number or null".format(DEF_DIR, subject_name))
    return out


def resolve_env(harness_env):
    """`$NAME` in harness.env means "take it from my environment" - keys stay out of the repo."""
    out = {}
    missing = []
    for key, val in (harness_env or {}).items():
        if isinstance(val, str) and re.match(r"^\$[A-Za-z_][A-Za-z0-9_]*$", val):
            name = val[1:]
            if name not in os.environ:
                missing.append(name)
            else:
                out[key] = os.environ[name]
        else:
            out[key] = val
    if missing:
        raise Refusal("harness.env references environment variable(s) that are not set: {}".format(
            ", ".join(missing)), missing_env=missing)
    return out


MODEL_ALIASES = ("opus", "sonnet", "haiku", "default", "opusplan")


def unknown_window_warning(sub):
    """claude -p assumes a 200k context window for a model name it does not know (2.1.295:
    modelUsage.contextWindow 200000 for glm-5.3) and compacts the round at that size, however
    large the real window is. CLAUDE_CODE_MAX_CONTEXT_TOKENS declares the real one; a [1m]
    suffix on the name is the other spelling the CLI understands."""
    h = sub["harness"]
    if h["type"] != "claude" or h.get("model"):
        return None
    try:
        env = harness_env(os.environ, resolve_env(h["env"]))
    except Refusal:
        return None
    model = env.get("ANTHROPIC_MODEL") or ""
    low = model.lower()
    if not env.get("ANTHROPIC_BASE_URL") or not model or low.startswith("claude-") \
            or low in MODEL_ALIASES or "[1m]" in low or env.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS"):
        return None
    return ("subject {}: ANTHROPIC_MODEL={} is not a name Claude Code knows, so it assumes a "
            "200000-token context window and compacts the round at that size; set "
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS in harness.env to the model's real window".format(
                sub["name"], model))


def pick_subject(cfg, name):
    for sub in cfg["subjects"]:
        if sub["name"] == name:
            return sub
    raise Refusal("no subject {!r} in this research (have: {})".format(
        name, ", ".join(s["name"] for s in cfg["subjects"])))


def check_subject_files(repo, sub):
    missing = []
    for key, needs_exec in (("program", False), ("score", True), ("gate", True)):
        path = os.path.join(repo, sub[key])
        if not os.path.isfile(path):
            missing.append({"what": key, "path": sub[key], "why": "missing"})
        elif needs_exec and not os.access(path, os.X_OK):
            missing.append({"what": key, "path": sub[key], "why": "not executable"})
    return missing


def resolve_ar_dir(repo, cfg):
    raw = cfg.get("ar_dir")
    if raw:
        return os.path.abspath(os.path.join(repo, os.path.expanduser(raw)))
    return os.path.join(os.path.dirname(os.path.abspath(repo)), cfg["name"] + ".ar")


# -------------------------------------------------------------------------- ledger


class Ledger(object):
    """Everything the runner remembers, beside the repository and never inside it."""

    def __init__(self, ar_dir):
        self.root = ar_dir

    def subject_dir(self, subject):
        return os.path.join(self.root, "researches", subject)

    def index_path(self, subject):
        return os.path.join(self.subject_dir(subject), "index.json")

    def artifacts(self, subject, cid):
        return os.path.join(self.root, "artifacts", subject, cid)

    def run_log(self, run_id):
        return os.path.join(self.root, "runs", run_id + ".log")

    def report_path(self):
        return os.path.join(self.root, "report", "index.html")

    def checkpoints(self, subject):
        return self.load(subject)[0]

    def unreadable(self, subject):
        return self.load(subject)[1]

    def load(self, subject):
        """(records, paths that do not parse). A broken checkpoint is never dropped in silence:
        if it was the best one, every comparison after it would be against the wrong tree."""
        out, bad = [], []
        for path in sorted(glob.glob(os.path.join(self.subject_dir(subject), "*.json"))):
            if os.path.basename(path) == "index.json":
                continue
            rec = read_json(path)
            if isinstance(rec, dict) and isinstance(rec.get("n"), int):
                out.append(rec)
            else:
                bad.append(path)
        out.sort(key=lambda r: (r["n"], r.get("at") or ""))
        return out, bad

    def lock_path(self):
        return os.path.join(self.root, "run.lock")

    def write_checkpoint(self, rec):
        write_json(os.path.join(self.subject_dir(rec["subject"]), rec["id"] + ".json"), rec)

    def index(self, subject, direction="max", limits=None):
        """Always derived from the checkpoint files; index.json is only a cache of this."""
        return derive_index(subject, self.checkpoints(subject), direction, limits)

    def rebuild_index(self, subject, direction="max", limits=None):
        idx = self.index(subject, direction, limits)
        write_json(self.index_path(subject), idx)
        return idx

    def snapshot(self, cfg):
        write_json(os.path.join(self.root, "research.snapshot.json"), {
            "name": cfg["name"], "description": cfg["description"], "direction": cfg["direction"],
            "subjects": [{"name": s["name"], "depends_on": s["depends_on"],
                          "harness": s["harness"]["type"],
                          "timeout_sec": s["harness"]["timeout_sec"], "limits": subject_limits(s)}
                         for s in cfg["subjects"]],
            "at": now_iso(),
        })


def better(score, best, direction):
    if best is None:
        return True
    return score < best if direction == "min" else score > best


def subject_limits(sub):
    """The stop conditions, pulled out so that the index can derive why a subject stopped."""
    return {"max_rounds": sub["max_rounds"],
            "max_consecutive_discards": sub["max_consecutive_discards"],
            "max_consecutive_errors": sub["max_consecutive_errors"],
            "target_score": sub["target_score"], "direction": None}


def derive_index(subject, records, direction="max", limits=None):
    idx = {"subject": subject, "n_next": 0, "best": None, "best_id": None, "version": None,
           "scorer_sha": None, "consecutive_discards": 0, "consecutive_errors": 0,
           "stopped_reason": None, "updated_at": None,
           "totals": {"checkpoints": 0, "keep": 0, "discard": 0, "crash": 0, "error": 0}}
    for rec in records:
        idx["n_next"] = max(idx["n_next"], rec["n"] + 1)
        idx["totals"]["checkpoints"] += 1
        status = rec.get("status")
        if status in STATUSES:
            idx["totals"][status] += 1
        idx["updated_at"] = rec.get("at") or idx["updated_at"]
        if status == "keep":
            idx["best"], idx["best_id"] = rec.get("score"), rec["id"]
            idx["version"] = rec.get("version") or idx["version"]
            idx["scorer_sha"] = rec.get("scorer_sha")
            idx["consecutive_discards"] = 0
            idx["consecutive_errors"] = 0
        elif status == "discard":
            idx["consecutive_discards"] += 1
            idx["consecutive_errors"] = 0
        elif status == "crash":
            # A gate that keeps failing is as stuck as a score that keeps not improving.
            idx["consecutive_discards"] += 1
            idx["consecutive_errors"] = 0
        elif status == "error":
            idx["consecutive_errors"] += 1
    idx["stopped_reason"] = derived_stop(idx, limits, direction)
    return idx


def derived_stop(idx, limits, direction):
    """Why this subject is standing still, as far as the checkpoints and the limits can say.

    Reasons that belong to one run rather than to the subject - a token budget, a Ctrl-C, the
    --rounds you asked for - are reported by that run, not stored here: the index must stay
    reconstructible from the checkpoint files alone.
    """
    if not limits:
        return None
    if limits.get("max_rounds") and idx["n_next"] >= limits["max_rounds"]:
        return "max_rounds"
    if limits.get("max_consecutive_discards") and \
            idx["consecutive_discards"] >= limits["max_consecutive_discards"]:
        return "consecutive_discards"
    if limits.get("max_consecutive_errors") and \
            idx["consecutive_errors"] >= limits["max_consecutive_errors"]:
        return "consecutive_errors"
    if limits.get("target_score") is not None and idx["best"] is not None and \
            not better(limits["target_score"], idx["best"], direction):
        return "target_score"
    return None


# ------------------------------------------------------------------------- harness


def kill_group(proc):
    global CHILD_PGID
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError as exc:
        if exc.errno not in (errno.ESRCH, errno.EPERM):
            raise
    CHILD_PGID = None


def spawn(cmd, cwd, env, out_path, err_path, stdin_path=None, timeout_sec=None):
    """Run one harness invocation in its own process group; on timeout kill the group.

    Returns (exit_code, reason) where reason is None, "timeout" or "interrupt".
    """
    global CHILD_PGID
    stdin_fh = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=stdin_fh, stdout=out_fh,
                                stderr=err_fh, start_new_session=True)
    if stdin_path:
        stdin_fh.close()
    CHILD_PGID = os.getpgid(proc.pid)
    deadline = time.time() + float(timeout_sec) if timeout_sec else None
    try:
        while True:
            code = proc.poll()
            if code is not None:
                CHILD_PGID = None
                return code, None
            if INTERRUPT >= 2:
                kill_group(proc)
                proc.wait()
                return -signal.SIGKILL, "interrupt"
            if deadline and time.time() > deadline:
                kill_group(proc)
                proc.wait()
                return -signal.SIGKILL, "timeout"
            time.sleep(0.2)
    finally:
        CHILD_PGID = None




def harness_env(base_env, extra):
    env = dict(base_env)
    # A nested Claude Code refuses to start normally while this is set.
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_SSE_PORT", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.update(extra or {})
    return env


def claude_result(stdout):
    """The final result object of a Claude Code -p run, whatever the output format: one JSON
    object (--output-format json) or a stream of events (stream-json, as a shell wrapper may
    well ask for) whose last `type: result` line carries the same fields. None when there is
    no such object. Scanning 40k lines of thinking_tokens events is a few milliseconds."""
    s = (stdout or "").strip()
    if not s:
        return None
    if s.startswith("{") and s.endswith("}") and "\n" not in s:
        try:
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, dict) and ("result" in obj or obj.get("type") == "result"):
            return obj
    found = None
    for line in s.splitlines():
        line = line.strip()
        # Key order is not stable across versions ("type" is not first on 2.1.295's
        # stream-json result line), so look anywhere in the line before parsing it.
        if not line.startswith("{") or ('"type":"result"' not in line and
                                        '"type": "result"' not in line):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "result":
            found = obj
    return found


def run_harness(h, prompt, repo, artdir, log):
    """One stateless invocation. Returns a dict the round records verbatim."""
    prompt_path = os.path.join(artdir, "prompt.md")
    write_text(prompt_path, prompt)
    out_path, err_path = os.path.join(artdir, "harness.out"), os.path.join(artdir, "harness.err")
    env = harness_env(os.environ, resolve_env(h["env"]))
    result = {"type": h["type"], "model": h.get("model"), "session_id": None, "turns": None,
              "exit": None, "cost_usd": None}
    usage = {"input": None, "output": None, "cache_read": None, "cache_write": None}
    stdin_path = None
    last_msg = None

    if h["type"] == "claude":
        # Every flag here is in the official CLI reference for print mode. `claude --help` does
        # not list all of them (the reference says so), so the help text is never consulted: a
        # flag this CLI rejects makes the round an error carrying the CLI's own message, which
        # is better than a cap that was asked for and silently not applied.
        cmd = ["claude", "-p", prompt, "--output-format", "json",
               "--dangerously-skip-permissions", "--no-session-persistence",
               "--exclude-dynamic-system-prompt-sections"]
        if h.get("max_turns"):
            cmd += ["--max-turns", str(int(h["max_turns"]))]
        if h.get("model"):
            cmd += ["--model", h["model"]]
        if h.get("max_budget_usd"):
            cmd += ["--max-budget-usd", str(h["max_budget_usd"])]
    elif h["type"] == "codex":
        last_msg = os.path.join(artdir, "codex.last.txt")
        cmd = ["codex", "exec", prompt, "--json", "-o", last_msg,
               "-s", "workspace-write", "-C", repo, "--skip-git-repo-check"]
        if h.get("model"):
            cmd += ["-m", h["model"]]
    else:
        cmd = list(h["command"]) if isinstance(h["command"], list) else ["sh", "-c", h["command"]]
        cmd += list(h.get("args") or [])
        stdin_path = prompt_path

    shown = ["<prompt>" if a == prompt else a for a in cmd]
    log("harness {}: {}".format(h["type"], " ".join(shown[:4]) + (" …" if len(shown) > 4 else "")))
    t0 = time.time()
    code, reason = spawn(cmd, repo, env, out_path, err_path, stdin_path, h["timeout_sec"])
    result["exit"] = code
    result["elapsed_ms"] = ms(t0)
    stdout, stderr = read_text(out_path, "") or "", read_text(err_path, "") or ""
    text = tail(stdout, 40, 4000) or tail(stderr, 40, 4000)
    failure = reason

    if h["type"] in ("claude", "shell"):
        # A shell harness is usually someone's own wrapper around `claude -p`; when its
        # stdout is Claude Code's JSON, the round gets the same facts as the claude adapter.
        parsed = claude_result(stdout)
        if parsed:
            text = parsed.get("result") or text
            result["session_id"] = parsed.get("session_id")
            result["turns"] = parsed.get("num_turns")
            result["cost_usd"] = parsed.get("total_cost_usd")
            result["subtype"] = parsed.get("subtype")
            models = parsed.get("modelUsage") or {}
            if models and not result.get("model"):
                result["model"] = next(iter(models))
                result["context_window"] = (models[result["model"]] or {}).get("contextWindow")
            u = parsed.get("usage") or {}
            usage = {"input": u.get("input_tokens"), "output": u.get("output_tokens"),
                     "cache_read": u.get("cache_read_input_tokens"),
                     "cache_write": u.get("cache_creation_input_tokens")}
            if parsed.get("is_error") and not failure:
                subtype = str(parsed.get("subtype") or "is_error")
                if subtype in CUT_OFF_SUBTYPES:
                    result["cut_off"] = subtype
                    log("harness stopped by {}; measuring what it left behind".format(subtype))
                else:
                    failure = "harness_error:" + subtype
        elif h["type"] == "claude" and code == 0 and not failure:
            failure = "harness_output_not_json"
    elif h["type"] == "codex":
        text = read_text(last_msg, "") or text
        usage, result["turns"], result["session_id"] = codex_events(stdout)
        if code != 0 and not stdout.strip() and "trust" in (stderr or "").lower() and not failure:
            failure = "codex_untrusted_directory"
    if code != 0 and not failure and not result.get("cut_off"):
        # claude -p exits 1 when one of its own caps trips (observed on 2.1.294); the JSON on
        # stdout already said which, and that is not a failed round.
        failure = "harness_exit:{}".format(code)

    result["failure"] = failure
    write_json(os.path.join(artdir, "harness.meta.json"),
               {"cmd": cmd, "env_extra": sorted((h.get("env") or {}).keys()),
                "harness": result, "usage": usage})
    return {"harness": result, "usage": usage, "text": text.strip(), "failure": failure}


def codex_events(stdout):
    """codex exec --json prints one event per line; take the usage, turns and thread from them.

    Verified against codex-cli 0.156.1 (2026-10-08): turn.completed carries usage as
    input_tokens / cached_input_tokens / cache_write_input_tokens / output_tokens, and
    thread.started carries thread_id. Anything this version does not print stays null.
    """
    usage = {"input": None, "output": None, "cache_read": None, "cache_write": None}
    turns, thread = 0, None
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        found = find_usage(ev)
        if found:
            usage = found
        if ev.get("type") == "turn.completed":
            turns += 1
        if ev.get("thread_id"):
            thread = ev["thread_id"]
    return usage, turns or None, thread


def find_usage(node):
    """Depth-first hunt for a token-usage object, whatever the event wraps it in."""
    if isinstance(node, dict):
        keys = set(node.keys())
        if {"input_tokens", "output_tokens"} <= keys:
            return {"input": node.get("input_tokens"), "output": node.get("output_tokens"),
                    "cache_read": node.get("cached_input_tokens",
                                           node.get("cache_read_input_tokens")),
                    "cache_write": node.get("cache_creation_input_tokens",
                                            node.get("cache_write_input_tokens"))}
        for key in ("info", "usage", "token_usage", "total_token_usage", "last_token_usage", "msg"):
            if key in node:
                found = find_usage(node[key])
                if found:
                    return found
        for val in node.values():
            if isinstance(val, (dict, list)):
                found = find_usage(val)
                if found:
                    return found
    elif isinstance(node, list):
        for val in node:
            found = find_usage(val)
            if found:
                return found
    return None


# -------------------------------------------------------------------- gate / score


def run_tool(path, repo, artdir, prefix, env_extra, timeout_sec=1800):
    out_path = os.path.join(artdir, prefix + ".out")
    err_path = os.path.join(artdir, prefix + ".err")
    env = dict(os.environ)
    env.update(env_extra)
    t0 = time.time()
    code, reason = spawn([path], repo, env, out_path, err_path, None, timeout_sec)
    return {"exit": code, "reason": reason, "ms": ms(t0),
            "stdout": read_text(out_path, "") or "", "stderr": read_text(err_path, "") or ""}


def parse_score(stdout):
    """The scorer's whole contract: one JSON object, numeric score, non-empty version."""
    text = (stdout or "").strip()
    if not text:
        return None, "scorer printed nothing"
    start = text.find("{")
    if start == -1:
        return None, "scorer stdout is not a JSON object"
    try:
        obj = json.loads(text[start:])
    except ValueError as exc:
        return None, "scorer stdout is not valid JSON: {}".format(exc)
    if not isinstance(obj, dict):
        return None, "scorer stdout is not a JSON object"
    if not isinstance(obj.get("score"), (int, float)) or isinstance(obj.get("score"), bool):
        return None, "scorer did not report a numeric score"
    if not obj.get("version") or not isinstance(obj["version"], str):
        return None, "scorer did not report a version string"
    if obj.get("remaining") is not None and not isinstance(obj["remaining"], list):
        return None, "scorer remaining must be an array"
    return obj, None


def sha_of(path):
    import hashlib
    data = read_text(path)
    if data is None:
        return None
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- prompt


RULES = """\
## Rules

- One round, one direction. Make the single change you think most improves the score, then stop.
- Do not run any git command that writes: no commit, no checkout, no stash, no reset. The runner
  commits your work for you when you are done, and reverts it if the score did not improve.
- Never edit the locked paths listed below. The scorer and the research definition are not yours
  to change; a round that touches them is thrown away before it is even measured.
- Leave no scratch files behind. Everything in the working tree becomes part of this round.
- End your turn with one short paragraph: the assumption you acted on, what you changed, and the
  effect you expect. That paragraph is the only thing the next round will read from you.
"""


def build_prompt(cfg, sub, repo, idx, records, cid, n):
    """Stable prefix first (it is what the prompt cache hits), per-round tail last."""
    program = read_text(os.path.join(repo, sub["program"]), "") or ""
    gate_cmd = "./" + sub["gate"]
    head = ["# Research: {}".format(cfg["name"])]
    if cfg["description"]:
        head.append(cfg["description"].strip())
    program = program.strip()
    if not program.startswith("#"):  # the template opens with "# Subject: <name>" already
        program = "# Subject: {}\n\n{}".format(sub["name"], program)
    head.append("\n" + program)
    head.append("\n" + RULES)
    head.append("## Paths\n")
    head.append("- repository root: `{}` (you are already there)".format(repo))
    head.append("- you may edit: {}".format(", ".join("`{}`".format(p) for p in sub["editable"])
                                            or "anything outside the locked paths"))
    head.append("- locked, never edit: {}".format(", ".join("`{}`".format(p) for p in sub["locked"])))
    head.append("- gate (run it as often as you like): `{}`".format(gate_cmd))
    if sub["agent_may_score"]:
        head.append("- scorer (you may run it): `./{}`".format(sub["score"]))
    else:
        head.append("- the scorer runs after you stop; do not run it yourself")
    prefix = "\n".join(head).rstrip() + "\n"

    tail_lines = ["\n---\n", "## This round\n", "- round #{} of subject `{}`".format(n, sub["name"])]
    if idx.get("best") is None:
        tail_lines.append("- no measurement yet: this is the first round that changes anything")
    else:
        tail_lines.append("- best so far: {} (scorer version {}) at round #{}".format(
            fmt_score(idx["best"]), idx.get("version"), round_of(records, idx.get("best_id"))))
    best_rec = next((r for r in records if r["id"] == idx.get("best_id")), None)
    if best_rec:
        if best_rec.get("details"):
            tail_lines.append("- measurement at the best round: `{}`".format(
                json.dumps(best_rec["details"], ensure_ascii=False)))
        rem = best_rec.get("remaining") or []
        if rem:
            tail_lines.append("\n### Still missing ({} items)\n".format(len(rem)))
            tail_lines += ["- {}".format(item) for item in rem[:200]]
            if len(rem) > 200:
                tail_lines.append("- … {} more".format(len(rem) - 200))
    recent = [r for r in records if r["n"] > 0][-int(sub["recent_rounds"] or 0):]
    if recent:
        tail_lines.append("\n### Recent rounds\n")
        for rec in recent:
            note = " ".join((rec.get("note") or "").split())[:300]
            line = "- #{} {} {}".format(rec["n"], rec["status"], fmt_score(rec.get("score")))
            if rec["status"] in ("crash", "error") and rec.get("reason"):
                # Without this the next agent cannot know what failed and tends to do it again.
                line += " — {}".format(" ".join(rec["reason"].split())[:300])
            if note:
                line += " — " + note
            tail_lines.append(line)
    tail_lines.append("\nCheckpoint id for this round: `{}`".format(cid))
    return prefix + "\n".join(tail_lines).rstrip() + "\n"


def fmt_score(score):
    if score is None:
        return "—"
    if isinstance(score, float) and score != int(score):
        return "{:.4g}".format(score)
    return str(score)


def round_of(records, cid):
    for rec in records:
        if rec["id"] == cid:
            return rec["n"]
    return "?"


# ------------------------------------------------------------------------ the round


def new_cid(subject, n):
    return "{}-{}-{}".format(subject, n, uuid.uuid4().hex[:6])


def scorer_env(repo, ledger, sub, cid, n):
    return {"AR_REPO": repo, "AR_SUBJECT": sub["name"], "AR_ROUND": str(n),
            "AR_CHECKPOINT": cid, "AR_ARTIFACT_DIR": ledger.artifacts(sub["name"], cid),
            "AR_DIR": ledger.root}


def do_round(cfg, sub, repo, ledger, log, baseline=False):
    """One round, from prompt to checkpoint. Returns the checkpoint record."""
    direction = cfg["direction"]
    idx = ledger.index(sub["name"], direction, subject_limits(sub))
    records = ledger.checkpoints(sub["name"])
    n = idx["n_next"]
    cid = new_cid(sub["name"], n)
    artdir = ledger.artifacts(sub["name"], cid)
    os.makedirs(artdir, exist_ok=True)
    env_extra = scorer_env(repo, ledger, sub, cid, n)
    rec = {"id": cid, "n": n, "subject": sub["name"], "status": None, "at": now_iso(),
           "commit": None, "reverted_by": None, "score": None, "version": None,
           "best_before": idx.get("best"), "details": None, "remaining": None,
           "timings_ms": {"agent": 0, "gate": 0, "score": 0}, "note": None,
           "usage": {"input": None, "output": None, "cache_read": None, "cache_write": None},
           "harness": {"type": "none", "model": None, "session_id": None, "turns": None,
                       "exit": 0},
           "changed_files": [], "reason": None, "scorer_sha": sha_of(os.path.join(repo, sub["score"]))}

    settle_tree(sub, repo, log)
    log("round #{} {} ({})".format(n, cid, "baseline" if baseline else sub["harness"]["type"]))
    mark_round(ledger, n, cid)
    safe_report(cfg, ledger, repo, log)
    if baseline:
        rec["note"] = "Baseline measured on HEAD; the harness was not invoked."
    else:
        prompt = build_prompt(cfg, sub, repo, idx, records, cid, n)
        res = run_harness(sub["harness"], prompt, repo, artdir, log)
        rec["timings_ms"]["agent"] = res["harness"].get("elapsed_ms", 0)
        rec["usage"] = res["usage"]
        rec["harness"] = res["harness"]
        rec["note"] = res["text"] or None
        if res["failure"] == "interrupt":
            return None  # second Ctrl-C: nothing is recorded for a round we cut in half
        if res["failure"]:
            rec["status"], rec["reason"] = "error", res["failure"]
            log("  harness failed: {}".format(res["failure"]))

    changed = [path for _code, path in porcelain(repo)]
    rec["changed_files"] = changed

    if rec["status"] is None:
        hit = next(((p, path_matches(p, sub["locked"])) for p in changed
                    if path_matches(p, sub["locked"])), None)
        if hit:
            rec["status"], rec["reason"] = "crash", "locked:{}".format(hit[0])
            log("  locked path changed: {}".format(hit[0]))

    if rec["status"] is None:
        gate = run_tool(os.path.join(repo, sub["gate"]), repo, artdir, "gate", env_extra)
        rec["timings_ms"]["gate"] = gate["ms"]
        write_text(os.path.join(artdir, "gate.log"),
                   (gate["stdout"] or "") + ("\n" + gate["stderr"] if gate["stderr"] else ""))
        if gate["exit"] != 0:
            rec["status"] = "crash"
            rec["reason"] = tail(gate["stderr"] or gate["stdout"], 4) or "gate exit {}".format(
                gate["exit"])
            log("  gate failed: {}".format(" ".join(rec["reason"].split())[:120]))

    if rec["status"] is None:
        sc = run_tool(os.path.join(repo, sub["score"]), repo, artdir, "score", env_extra)
        rec["timings_ms"]["score"] = sc["ms"]
        obj, err = parse_score(sc["stdout"])
        if sc["exit"] != 0:
            rec["status"] = "error"
            rec["reason"] = "scorer exit {}: {}".format(
                sc["exit"], tail(sc["stderr"] or sc["stdout"], 3))
        elif err:
            rec["status"], rec["reason"] = "error", err
        else:
            write_json(os.path.join(artdir, "score.json"), obj)
            rec["score"] = obj["score"]
            rec["version"] = obj["version"]
            rec["details"] = obj.get("details")
            rec["remaining"] = obj.get("remaining") or []
            for key, val in (obj.get("timings_ms") or {}).items():
                if isinstance(val, (int, float)) and key not in rec["timings_ms"]:
                    rec["timings_ms"][key] = val
        if rec["status"] == "error":
            log("  scorer error: {}".format(" ".join((rec["reason"] or "").split())[:120]))

    if (rec["reason"] or "").startswith("locked:"):
        # The round is thrown away, and the runner cannot tell whether the agent changed the
        # locked file or a person did while the round was running. Protecting the scorer wins,
        # so it is reverted either way - but the diff is kept, so a hand edit caught by this
        # check can be re-applied and a tampering agent can be audited.
        patch_path = os.path.join(artdir, "locked-changes.patch")
        write_text(patch_path, git(["diff", "HEAD", "--", DEF_DIR], repo, check=False).stdout or "")
        rec["reason"] += " (reverted; the diff is kept at {} — if this was your own edit, "
        rec["reason"] = rec["reason"].format(patch_path) + "re-apply it between rounds)"
    else:
        rec["scorer_commit"] = commit_definition(sub, repo, log)
        if rec["scorer_commit"]:
            rec["scorer_sha"] = sha_of(os.path.join(repo, sub["score"]))
    git(["add", "-A"], repo)
    git(["commit", "--allow-empty", "-m", "ar {}".format(cid)], repo)
    rec["commit"] = head_sha(repo)
    if changed:
        # "What did #17 change" is the question the report answers most often; the sha alone
        # answers it only for someone with the repository open.
        shown = git(["show", "--format=", "--stat", "-p", rec["commit"]], repo, check=False)
        write_text(os.path.join(artdir, "changes.patch"), shown.stdout or "")

    if rec["status"] is None:
        same_version = idx.get("version") in (None, rec["version"])
        if not same_version:
            rec["status"] = "keep"
            rec["reason"] = "scorer version {} → {}: new comparison baseline".format(
                idx.get("version"), rec["version"])
        elif better(rec["score"], idx.get("best"), direction):
            rec["status"] = "keep"
        else:
            rec["status"] = "discard"

    if rec["status"] != "keep":
        if commit_is_empty(repo, rec["commit"]):
            log("  round commit is empty; nothing to revert")
        else:
            p = git(["revert", "--no-edit", "HEAD"], repo, check=False)
            if p.returncode != 0:
                git(["revert", "--quit"], repo, check=False)
                why = tail(p.stderr or p.stdout, 4)
                rec["reason"] = "{} — and its revert failed: {}".format(rec["reason"] or
                                                                        rec["status"], why)
                ledger.write_checkpoint(rec)  # the stuck round must still be in the ledger
                ledger.rebuild_index(sub["name"], direction, subject_limits(sub))
                raise Refusal("git revert of {} failed, the loop stops here rather than "
                              "resetting: {}. The round is recorded as {}; HEAD still holds its "
                              "work.".format(rec["commit"][:10], why, rec["id"]),
                              checkpoint=rec["id"])
            rec["reverted_by"] = head_sha(repo)

    log("  {} score {} (best {}){}".format(
        rec["status"], fmt_score(rec["score"]), fmt_score(rec["best_before"]),
        " — " + " ".join((rec["reason"] or "").split())[:100] if rec["reason"] else ""))
    ledger.write_checkpoint(rec)
    ledger.rebuild_index(sub["name"], direction, subject_limits(sub))
    return rec


# -------------------------------------------------------------------------- the run


def settle_tree(sub, repo, log):
    """A round may only start on a tree nobody else is holding.

    Checked before every round, not just the first: a hand edit to the scorer or the program
    lands in its own commit and takes effect in the very next round, which is what the person
    editing it expects. Anything else uncommitted belongs to someone else and stops the loop.
    """
    dirty = porcelain(repo)
    if not dirty:
        return None
    outside = [p for _c, p in dirty if not path_matches(p, [DEF_DIR + "/**"])]
    if outside:
        raise Refusal("the working tree is not clean, so a round would measure someone else's "
                      "work (or what a killed run left behind): {}. Commit or discard these by "
                      "hand, then run again.".format(", ".join(sorted(outside)[:12])),
                      dirty=sorted(outside))
    return commit_definition(sub, repo, log)


def commit_definition(sub, repo, log):
    """Commit only what is under the definition directory, as the person's own commit.

    Called at the start of a round and again just before the round's commit: an edit that
    lands while the round is running must not end up inside the agent's commit, where a
    revert would silently undo it.
    """
    if not [p for _c, p in porcelain(repo) if path_matches(p, [DEF_DIR + "/**"])]:
        return None
    git(["add", "-A", "--", DEF_DIR], repo)
    git(["commit", "-m", "ar scorer {}".format(sub["name"])], repo)
    log("committed the hand edit under {}/ as 'ar scorer {}'".format(DEF_DIR, sub["name"]))
    return head_sha(repo)


def preflight(cfg, sub, repo, ledger, log):
    """Everything that must be true before a round starts, checked in order."""
    missing = check_subject_files(repo, sub)
    if missing:
        raise Refusal("subject {} is not runnable: {}".format(sub["name"], "; ".join(
            "{} {} is {}".format(m["what"], m["path"], m["why"]) for m in missing)),
            missing=missing)
    bad = ledger.unreadable(sub["name"])
    if bad:
        raise Refusal("{} checkpoint file(s) in the ledger do not parse: {}. Restore or move "
                      "them away first; a round that cannot see every checkpoint might compare "
                      "against the wrong best.".format(len(bad), ", ".join(bad[:5])),
                      unreadable=bad)
    resolve_env(sub["harness"]["env"])
    if sub["harness"]["type"] in ("claude", "codex") and not which(sub["harness"]["type"]):
        raise Refusal("the {} harness needs the {} CLI on PATH; run doctor".format(
            sub["harness"]["type"], sub["harness"]["type"]))
    if head_sha(repo) is None:
        raise Refusal("this repository has no commits yet; make an initial commit first")

    for dep in sub["depends_on"]:
        dep_idx = ledger.index(dep, cfg["direction"])
        if dep_idx["totals"]["keep"] == 0:
            raise Refusal("subject {} depends on {}, which has no kept checkpoint yet; "
                          "run {} first".format(sub["name"], dep, dep))

    branch = "research/" + cfg["name"]
    cur = current_branch(repo)
    if cur != branch:
        settle_tree(sub, repo, log)  # refuse before touching branches if someone else is mid-edit
        if git(["rev-parse", "--verify", "--quiet", "refs/heads/" + branch], repo,
               check=False).returncode == 0:
            git(["checkout", branch], repo)
            log("switched to {}".format(branch))
        else:
            git(["checkout", "-b", branch], repo)
            log("created {} from {}".format(branch, (head_sha(repo) or "")[:10]))
    settle_tree(sub, repo, log)

    idx = ledger.index(sub["name"], cfg["direction"], subject_limits(sub))
    records = ledger.checkpoints(sub["name"])
    if records:
        # HEAD has to still carry this subject's history. It is allowed to be ahead of it: hand
        # edits to the scorer, and rounds of another subject on the same branch, both move it on.
        # What is not allowed is HEAD having left that history - a checkout of an older state, a
        # rewritten branch, a reverted keep - because then the next round measures something the
        # ledger never recorded and compares it against a best that no longer exists.
        last = records[-1]
        for rec in (last, next((r for r in records if r["id"] == idx.get("best_id")), None)):
            if rec and rec.get("commit") and not is_ancestor(repo, rec["commit"], "HEAD"):
                raise Refusal("checkpoint {} (round #{}, commit {}) is not in HEAD's history, so "
                              "this working tree is no longer the one the ledger describes. Check "
                              "out {} at a commit that contains it, or start a new "
                              "research.".format(rec["id"], rec["n"], rec["commit"][:10],
                                                 "research/" + cfg["name"]),
                              head=head_sha(repo), checkpoint_commit=rec["commit"])
    return idx


def stop_reason(sub, idx, run_state):
    """The subject's own conditions first, then the ones that belong to this run."""
    standing = derived_stop(idx, subject_limits(sub), run_state["direction"])
    if standing:
        return standing
    budget = sub["budget"] or {}
    if budget.get("minutes") and (time.time() - run_state["started"]) / 60.0 >= budget["minutes"]:
        return "budget.minutes"
    if budget.get("tokens") and run_state["tokens"] >= budget["tokens"]:
        return "budget.tokens"
    if INTERRUPT:
        return "interrupt"
    return None


def active_run(ledger):
    """The run holding run.lock, if its process is still alive. A lock whose process is gone
    (a SIGKILL, a reboot) is stale and reads as no run."""
    info = read_json(ledger.lock_path())
    if not isinstance(info, dict) or not isinstance(info.get("pid"), int):
        return None
    try:
        os.kill(info["pid"], 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return None
    return info


def take_run_lock(ledger, run_id, subject):
    """Returns the stale lock it replaced, if any, so the run can say so in its log."""
    live = active_run(ledger)
    if live:
        raise Refusal("a run is already active on this research: {} (subject {}, pid {}, started "
                      "{}). Two runs would commit over each other's rounds; wait for it, or stop "
                      "it with SIGINT or SIGTERM.".format(
                          live.get("run_id"), live.get("subject"), live.get("pid"),
                          live.get("started")), active_run=live)
    stale = read_json(ledger.lock_path())
    write_json(ledger.lock_path(), {"pid": os.getpid(), "run_id": run_id, "subject": subject,
                                    "started": now_iso()})
    return stale if isinstance(stale, dict) else None


def release_run_lock(ledger, run_id):
    info = read_json(ledger.lock_path())
    if isinstance(info, dict) and info.get("run_id") == run_id:
        try:
            os.remove(ledger.lock_path())
        except OSError:
            pass


def mark_round(ledger, n, cid):
    """Note in run.lock which round is in progress and since when, so a report rendered
    mid-round shows a clock that is right instead of a guess from the last checkpoint."""
    info = read_json(ledger.lock_path())
    if isinstance(info, dict) and info.get("pid") == os.getpid():
        info.update({"round": n, "checkpoint": cid, "round_started": now_iso()})
        write_json(ledger.lock_path(), info)


def run_info(ledger):
    """What the report shows about a run in progress: nothing, or the live lock's facts."""
    live = active_run(ledger)
    if not live:
        return {}
    return {"running": True, "subject": live.get("subject"), "run_id": live.get("run_id"),
            "pid": live.get("pid"), "since": live.get("started"), "round": live.get("round"),
            "round_started": live.get("round_started")}


def serve_lock_path(ledger):
    return os.path.join(ledger.root, "serve.lock")


def active_serve(ledger):
    """The `serve` process holding serve.lock, if it is still alive; a dead pid reads as none."""
    info = read_json(serve_lock_path(ledger))
    if not isinstance(info, dict) or not isinstance(info.get("pid"), int):
        return None
    try:
        os.kill(info["pid"], 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return None
    return info


def serve_url(ledger):
    live = active_serve(ledger)
    return live.get("url") if live else None


def release_serve_lock(ledger):
    info = read_json(serve_lock_path(ledger))
    if isinstance(info, dict) and info.get("pid") == os.getpid():
        try:
            os.remove(serve_lock_path(ledger))
        except OSError:
            pass


def cmd_run(args):
    repo = repo_root(args.repo)
    cfg = load_research(repo)
    sub = pick_subject(cfg, args.subject)
    ledger = Ledger(cfg["ar_dir"])
    run_id = "{}-{}-{}".format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), sub["name"],
                               uuid.uuid4().hex[:4])
    stale = take_run_lock(ledger, run_id, sub["name"])
    try:
        return run_rounds(args, repo, cfg, sub, ledger, run_id, stale)
    finally:
        release_run_lock(ledger, run_id)


def run_rounds(args, repo, cfg, sub, ledger, run_id, stale_lock):
    global INTERRUPT
    os.makedirs(os.path.dirname(ledger.run_log(run_id)), exist_ok=True)
    log_fh = open(ledger.run_log(run_id), "a", encoding="utf-8")

    def log(line):
        stamped = "[{}] {}".format(now_iso(), line)
        log_fh.write(stamped + "\n")
        log_fh.flush()
        sys.stderr.write(stamped + "\n")
        sys.stderr.flush()

    def on_sigint(_sig, _frame):
        global INTERRUPT
        INTERRUPT += 1
        if INTERRUPT == 1:
            log("interrupt: finishing this round, then stopping (press Ctrl-C again to kill it)")
        else:
            log("interrupt: killing the harness process group now")

    signal.signal(signal.SIGINT, on_sigint)
    signal.signal(signal.SIGTERM, on_sigint)

    log("run {} — subject {} — harness {} — ledger {}".format(
        run_id, sub["name"], sub["harness"]["type"], ledger.root))
    if stale_lock:
        log("replaced a stale run.lock left by {} (pid {} is gone)".format(
            stale_lock.get("run_id"), stale_lock.get("pid")))
    if serve_url(ledger):
        log("live report: {}".format(serve_url(ledger)))
    idx = preflight(cfg, sub, repo, ledger, log)
    window = unknown_window_warning(sub)
    if window:
        log("warning: " + window)
    ledger.snapshot(cfg)

    if args.dry_prompt:
        records = ledger.checkpoints(sub["name"])
        prompt = build_prompt(cfg, sub, repo, idx, records, new_cid(sub["name"], idx["n_next"]),
                              idx["n_next"])
        log_fh.close()
        return {"ok": True, "subject": sub["name"], "prompt": prompt,
                "prompt_chars": len(prompt)}, 0

    run_state = {"started": time.time(), "tokens": 0, "direction": cfg["direction"]}
    done = []
    stopped = None
    # A scorer whose file changed since the best checkpoint may report a new version; measure
    # HEAD first so the new version's baseline is the best tree, not whatever a round leaves.
    baseline_needed = idx["best_id"] is None or idx.get("scorer_sha") != sha_of(
        os.path.join(repo, sub["score"]))
    rounds_left = args.rounds

    while True:
        # A baseline is a measurement, not a round of work: --rounds 0 still takes it, which is
        # how you ask "where does this subject stand right now" without spending an agent.
        if rounds_left is not None and rounds_left <= 0 and not baseline_needed:
            stopped = "rounds_requested"
            break
        idx = ledger.index(sub["name"], cfg["direction"], subject_limits(sub))
        stopped = stop_reason(sub, idx, run_state)
        # A baseline is never blocked by a stop condition: the counters that stopped the last run
        # were measured with the scorer as it was then, and a new version is a new question.
        if stopped and not baseline_needed:
            break
        rec = do_round(cfg, sub, repo, ledger, log, baseline=baseline_needed)
        if rec is None:
            stopped = "interrupt"
            break
        done.append(rec)
        run_state["tokens"] += sum(v for v in (rec["usage"] or {}).values()
                                  if isinstance(v, (int, float)))
        if baseline_needed:
            baseline_needed = False
        else:
            rounds_left = rounds_left - 1 if rounds_left is not None else None
        safe_report(cfg, ledger, repo, log)

    idx = ledger.rebuild_index(sub["name"], cfg["direction"], subject_limits(sub))
    safe_report(cfg, ledger, repo, log)
    log("stopped: {} — {} round(s) this run — best {} ({}) — report {}".format(
        stopped, len(done), fmt_score(idx["best"]), idx.get("version"), ledger.report_path()))
    log_fh.close()
    return {"ok": True, "subject": sub["name"], "run_id": run_id, "stopped": stopped,
            "rounds": [{"id": r["id"], "n": r["n"], "status": r["status"], "score": r["score"],
                        "version": r["version"], "reason": r["reason"]} for r in done],
            "index": idx, "run_log": ledger.run_log(run_id),
            "report": ledger.report_path(), "url": serve_url(ledger)}, 0


# ------------------------------------------------------------------- status, report


def summary_line(subject, records, idx):
    """The one line a person reads to know where a subject stands."""
    totals = idx["totals"]
    versions = [r["version"] for r in records if r.get("version")]
    best_n = round_of(records, idx.get("best_id"))
    span = ""
    if versions:
        span = " · score v{}".format(versions[0]) + (
            " → v{}".format(versions[-1]) if versions[-1] != versions[0] else "")
    return "{} checkpoints · {} kept · {} discarded · {} crashed · {} errors · best {} at #{}{} · updated {}".format(
        totals["checkpoints"], totals["keep"], totals["discard"], totals["crash"],
        totals["error"], fmt_score(idx.get("best")), best_n, span, idx.get("updated_at") or "never")


def subject_state(cfg, ledger, sub, repo=None, rebuild=True):
    records = ledger.checkpoints(sub["name"])
    limits = subject_limits(sub)
    idx = (ledger.rebuild_index if rebuild else ledger.index)(sub["name"], cfg["direction"], limits)
    state = {"subject": sub["name"], "summary": summary_line(sub["name"], records, idx),
             "index": idx, "checkpoints": records, "limits": limits,
             "depends_on": sub["depends_on"], "harness": sub["harness"]["type"],
             "timeout_sec": sub["harness"]["timeout_sec"],
             "unreadable": ledger.unreadable(sub["name"])}
    if repo:
        # The next run re-measures HEAD as a new baseline when the scorer file changed since
        # the best checkpoint - say so before it happens.
        state["scorer_changed_since_best"] = bool(
            idx.get("best_id") and
            idx.get("scorer_sha") != sha_of(os.path.join(repo, sub["score"])))
    return state


def cmd_status(args):
    repo = repo_root(args.repo)
    cfg = load_research(repo)
    subs = [pick_subject(cfg, args.subject)] if args.subject else cfg["subjects"]
    ledger = Ledger(cfg["ar_dir"])
    out = []
    for sub in subs:
        state = subject_state(cfg, ledger, sub, repo)
        missing = check_subject_files(repo, sub)
        entry = {k: v for k, v in state.items() if k not in ("checkpoints", "timeout_sec")}
        entry.update({"runnable": not missing, "missing": missing})
        out.append(entry)
    return {"ok": True, "research": cfg["name"], "ar_dir": cfg["ar_dir"],
            "branch": current_branch(repo), "report": ledger.report_path(),
            "url": serve_url(ledger), "active_run": active_run(ledger), "subjects": out}, 0


def report_cfg(cfg):
    return {"name": cfg["name"], "description": cfg["description"],
            "direction": cfg["direction"], "ar_dir": cfg["ar_dir"]}


def report_states(cfg, ledger, repo=None):
    # Derived, not rebuilt: `serve` renders on every request while a run may be writing the
    # index, and two writers on index.json would be a race for nothing.
    return [subject_state(cfg, ledger, sub, repo, rebuild=False) for sub in cfg["subjects"]]


def write_report(cfg, ledger, repo=None):
    sys.path.insert(0, SCRIPT_DIR)
    import report as report_mod
    return report_mod.write_report(ledger.report_path(), report_cfg(cfg),
                                   report_states(cfg, ledger, repo), run_info(ledger))


def safe_report(cfg, ledger, repo, log):
    try:
        write_report(cfg, ledger, repo)
    except Exception as exc:  # noqa: BLE001 - a broken report must not stop the loop
        log("  report failed: {}: {}".format(type(exc).__name__, exc))


def cmd_report(args):
    repo = repo_root(args.repo)
    cfg = load_research(repo)
    ledger = Ledger(cfg["ar_dir"])
    ledger.snapshot(cfg)
    path = write_report(cfg, ledger, repo)
    url = serve_url(ledger)
    return {"ok": True, "report": path, "url": url, "open": "open {}".format(url or path)}, 0


def cmd_serve(args):
    """Serve the report at a fixed local URL, re-rendered from the ledger on every request,
    with /data.json for the page to poll. Runs until SIGINT / SIGTERM. The URL is printed
    first, so a caller that backgrounds this can pick it up from the first line."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import webbrowser
    repo = repo_root(args.repo)
    cfg = load_research(repo)
    ledger = Ledger(cfg["ar_dir"])
    ledger.snapshot(cfg)
    live = active_serve(ledger)
    if live:
        raise Refusal("a server for this research is already running at {} (pid {}); open that, "
                      "or stop it first".format(live.get("url"), live.get("pid")),
                      url=live.get("url"))
    sys.path.insert(0, SCRIPT_DIR)
    import report as report_mod

    def page():
        return report_mod.render(report_cfg(cfg), report_states(cfg, ledger, repo),
                                 run_info(ledger))

    def data():
        return json.dumps(report_mod.report_data(report_cfg(cfg), report_states(cfg, ledger, repo),
                                                 run_info(ledger)), ensure_ascii=False)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html"):
                    body, ctype = page().encode("utf-8"), "text/html; charset=utf-8"
                elif path == "/data.json":
                    body, ctype = data().encode("utf-8"), "application/json; charset=utf-8"
                else:
                    self.send_error(404)
                    return
            except Exception as exc:  # noqa: BLE001 - the page must say so, not the socket
                self.send_error(500, "{}: {}".format(type(exc).__name__, exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        raise Refusal("cannot listen on 127.0.0.1:{}: {}. Pick another --port, or stop whatever "
                      "holds it".format(args.port, exc.strerror or exc), port=args.port)
    url = "http://127.0.0.1:{}/".format(args.port)
    write_json(serve_lock_path(ledger), {"pid": os.getpid(), "port": args.port, "url": url,
                                         "research": cfg["name"], "started": now_iso()})
    print(json.dumps({"ok": True, "url": url, "pid": os.getpid(), "research": cfg["name"],
                      "stop": "send SIGINT or SIGTERM to pid {}".format(os.getpid())},
                     ensure_ascii=False, indent=2), flush=True)
    if not args.no_open:
        webbrowser.open(url)

    def stop(*_sig):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        release_serve_lock(ledger)
    return None, 0


# ---------------------------------------------------------------------- doctor/init


def cmd_doctor(args):
    tools = {
        "python3": {"available": True, "path": sys.executable,
                    "version": sys.version.split()[0]},
        "git": tool_version("git", ["--version"]),
        "claude": tool_version("claude", ["--version"]),
        "codex": tool_version("codex", ["--version"]),
    }
    problems, warnings = [], []
    if sys.version_info < (3, 9):
        problems.append("python3 is {}; 3.9 or newer is required".format(
            tools["python3"]["version"]))
    if not tools["git"]["available"]:
        problems.append("git is not available")
    if not tools["claude"]["available"] and not tools["codex"]["available"]:
        warnings.append("neither claude nor codex is on PATH; only the shell harness can run")
    if tools["codex"]["available"]:
        warnings.append("codex exits at startup in a directory it has not been trusted in; "
                        "run `codex` once in the target repository and accept the trust prompt")

    repo_info = {"repo": None, "branch": None, "clean": None, "head": None}
    research = {"defined": False}
    try:
        repo = repo_root(args.repo)
        repo_info["repo"] = repo
        repo_info["branch"] = current_branch(repo)
        dirty = [p for _c, p in porcelain(repo)]
        repo_info["clean"] = not dirty
        repo_info["dirty"] = sorted(dirty)[:20]
        repo_info["head"] = (head_sha(repo) or "")[:10] or None
        if not repo_info["head"]:
            problems.append("the repository has no commits yet")
    except Refusal as exc:
        warnings.append(str(exc))
        repo = None

    if repo:
        try:
            cfg = load_research(repo)
            research = {"defined": True, "name": cfg["name"], "ar_dir": cfg["ar_dir"],
                        "ar_dir_exists": os.path.isdir(cfg["ar_dir"]), "subjects": []}
            for sub in cfg["subjects"]:
                missing = check_subject_files(repo, sub)
                entry = {"name": sub["name"], "harness": sub["harness"]["type"],
                         "depends_on": sub["depends_on"], "missing": missing}
                try:
                    resolve_env(sub["harness"]["env"])
                except Refusal as exc:
                    entry["env"] = str(exc)
                    problems.append("subject {}: {}".format(sub["name"], exc))
                window = unknown_window_warning(sub)
                if window:
                    entry["warning"] = window
                    warnings.append(window)
                if missing:
                    problems.append("subject {}: {}".format(sub["name"], "; ".join(
                        "{} {} is {}".format(m["what"], m["path"], m["why"]) for m in missing)))
                if sub["harness"]["type"] in ("claude", "codex") and \
                        not tools[sub["harness"]["type"]]["available"]:
                    problems.append("subject {} wants the {} harness, which is not available".format(
                        sub["name"], sub["harness"]["type"]))
                research["subjects"].append(entry)
        except Refusal as exc:
            research = {"defined": False, "error": str(exc)}

    return {"ok": not problems, "tools": tools, "repo": repo_info, "research": research,
            "problems": problems, "warnings": warnings}, 0 if not problems else 1


SCORE_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"Score the repository as it stands now: one number, bigger is better.

The runner calls this from the repository root after the gate passes and reads one JSON
object from stdout. Everything the loop does is decided by what you measure here:
a dimension with no term in `score` gets no attention from the agent, and a `remaining`
list that is empty leaves the next round with nothing to aim at.

Bump `VERSION` whenever you change what is measured. The runner compares scores only
within one version; a new version starts a fresh baseline and a new band in the report.
\"\"\"

import json
import os

VERSION = "0.1.0"


def measure():
    # Replace this with the real measurement. Anything deterministic that ends in a number.
    files = [f for f in sorted(os.listdir(".")) if f.endswith(".md")]
    return {
        "score": float(len(files)),
        "version": VERSION,
        "details": {"markdown files": len(files)},
        "remaining": ["replace this scorer with the real measurement"],
    }


print(json.dumps(measure(), ensure_ascii=False))
"""

GATE_TEMPLATE = """\
#!/bin/sh
# Pass (exit 0) or crash the round (any other exit code). The gate is the cheap, fast
# check that says "this tree is not even worth measuring": syntax, lint, formatting,
# a smoke test. The agent is allowed to run it as often as it likes.
#
# Whatever you add here, keep it fast: it runs every round, before the scorer.
exit 0
"""

PROGRAM_TEMPLATE = """\
# Subject: {name}

## Goal

<One paragraph: what this subject is trying to make better, in terms of the score.>

## What you are working with

- <the files that matter, and what they mean>

## How you are measured

- <what the scorer rewards, what it penalises, and what the gate rejects>

## Ground rules for this subject

- <anything specific to this subject beyond the general rules the runner adds>
"""

RESEARCH_TEMPLATE = {
    "_doc": "A research is one goal, measured by one scorer per subject. Keys starting with _ are "
            "documentation and are ignored.",
    "name": "my-autoresearch",
    "_doc_name": "Identifier for the research; the ledger directory is <name>.ar beside the repo "
                 "and the loop runs on the branch research/<name>.",
    "description": "",
    "_doc_description": "Goes into the stable prefix of every prompt. Say what the research is "
                        "for and what good looks like.",
    "ar_dir": None,
    "_doc_ar_dir": "Where the ledger goes. null = <repo parent>/<name>.ar; never inside the repo.",
    "direction": "max",
    "_doc_direction": "\"max\" = higher score is better, \"min\" = lower is better.",
    "harness": {
        "_doc": "Defaults for every subject; a subject can override any of these.",
        "type": "claude",
        "_doc_type": "claude = claude -p, codex = codex exec, shell = any command with the prompt "
                     "on stdin (used for self-tests and custom executors).",
        "model": None,
        "max_turns": 40,
        "_doc_max_turns": "claude only: how many agentic turns (tool calls) one round may take. "
                          "The CLI stops the agent with error_max_turns and the round is still "
                          "measured. null = no cap.",
        "timeout_sec": 1800,
        "_doc_timeout_sec": "A round that runs longer than this is killed, process group and all, "
                            "and recorded as an error.",
        "max_budget_usd": None,
        "_doc_max_budget_usd": "claude only: the CLI's own client-side cost estimate at Anthropic "
                               "prices (not a bill, and not what a third-party endpoint charges). "
                               "The agent is stopped with error_max_budget_usd and the round is "
                               "still measured.",
        "command": None,
        "_doc_command": "shell harness only: the command to run, prompt arrives on stdin.",
        "env": {},
        "_doc_env": "Passed to the harness process. \"$NAME\" is read from your environment at "
                    "launch, so API keys never land in this file. Third-party Anthropic-compatible "
                    "endpoint: ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN (\"$KEY\"), ANTHROPIC_MODEL "
                    "(not harness.model), and CLAUDE_CODE_MAX_CONTEXT_TOKENS set to the model's "
                    "real context window - Claude Code assumes 200000 for a name it does not know.",
    },
    "subjects": [],
}

SUBJECT_TEMPLATE = {
    "name": "",
    "editable": [],
    "_doc_editable": "Paths the agent is told it may change. Informational: it goes into the "
                     "prompt, it is not enforced.",
    "locked": [],
    "_doc_locked": "Paths that make a round crash if they changed. autoresearch/** is always "
                   "locked; add the hidden answers your scorer reads.",
    "depends_on": [],
    "_doc_depends_on": "Subjects that must have at least one kept checkpoint before this one runs.",
    "agent_may_score": False,
    "_doc_agent_may_score": "Let the agent run the scorer itself. Off by default: scoring can be "
                            "slow or expensive, and an agent that can see the score will fit it.",
    "max_rounds": 50,
    "max_consecutive_discards": 5,
    "_doc_max_consecutive_discards": "Crashes count here too: a gate that keeps failing is as "
                                     "stuck as a score that keeps not improving.",
    "max_consecutive_errors": 3,
    "_doc_max_consecutive_errors": "Scorer or harness failures in a row. These do not count as "
                                   "discards: a broken scorer is not the agent's fault.",
    "target_score": None,
    "budget": {"minutes": None, "tokens": None},
    "recent_rounds": 5,
    "_doc_recent_rounds": "How many previous rounds get a one-line summary in the prompt.",
}


def cmd_init(args):
    repo = repo_root(args.repo)
    created, skipped = [], []

    def put(rel, text, mode=0o644):
        path = os.path.join(repo, rel)
        if os.path.exists(path):
            skipped.append(rel)
            return
        write_text(path, text)
        os.chmod(path, mode)
        created.append(rel)

    subjects = args.subject or ["main"]
    cfg_path = os.path.join(repo, DEF_DIR, "research.json")
    if os.path.exists(cfg_path):
        skipped.append(os.path.relpath(cfg_path, repo))
    else:
        cfg = json.loads(json.dumps(RESEARCH_TEMPLATE))
        cfg["name"] = args.name or (os.path.basename(repo) + "-autoresearch")
        cfg["description"] = args.describe or ""
        cfg["harness"]["type"] = args.harness
        if args.harness == "shell":
            cfg["harness"]["command"] = "echo 'replace harness.command with your executor'"
        for name in subjects:
            sub = json.loads(json.dumps(SUBJECT_TEMPLATE))
            sub["name"] = name
            sub["depends_on"] = []  # ordering between subjects is the person's call
            cfg["subjects"].append(sub)
        write_json(cfg_path, cfg)
        created.append(os.path.relpath(cfg_path, repo))

    for name in subjects:
        base = "{}/subjects/{}".format(DEF_DIR, name)
        put(base + "/program.md", PROGRAM_TEMPLATE.format(name=name))
        put(base + "/score", SCORE_TEMPLATE, 0o755)
        put(base + "/gate", GATE_TEMPLATE, 0o755)

    cfg = load_research(repo)
    return {"ok": True, "research": cfg["name"], "ar_dir": cfg["ar_dir"],
            "created": created, "skipped": skipped,
            "subjects": [s["name"] for s in cfg["subjects"]],
            "next": ["edit {}/subjects/<name>/score so it measures what you actually want".format(
                DEF_DIR),
                "edit {}/subjects/<name>/program.md so the agent knows the goal".format(DEF_DIR),
                "ar.py doctor", "ar.py run {}".format(subjects[0])]}, 0


# ------------------------------------------------------------------------- examples


def copy_tree(src, dst):
    out = []
    for dirpath, _dirs, names in os.walk(src):
        for name in sorted(names):
            if name == ".DS_Store":
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), src)
            full = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            shutil.copy2(os.path.join(dirpath, name), full)
            out.append(rel)
    return out


def examples_dir():
    return os.path.join(os.path.dirname(SCRIPT_DIR), "examples")


def example_names():
    root = examples_dir()
    return sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))) \
        if os.path.isdir(root) else []


def example_repo(which, path):
    """Copy examples/<which> into a fresh git repository with one initial commit.

    If the template carries autoresearch/setup.py, it runs once, from the new repository's
    root, before the commit: that is where generated data (hidden targets, corpora, held-out
    splits) comes from, so the template itself stays small and every generated repository is
    its own instance. Whatever JSON it prints on stdout is returned as `info`.
    """
    src = os.path.join(examples_dir(), which)
    if not os.path.isdir(src):
        raise Refusal("no example named {!r}; have: {}".format(which, ", ".join(example_names())))
    if os.path.exists(os.path.join(path, ".git")):
        raise Refusal("{} is already a git repository; pick a directory that does not exist "
                      "yet".format(path))
    os.makedirs(path, exist_ok=True)
    copied = copy_tree(src, path)
    for rel in copied:
        if os.path.basename(rel) in ("score", "gate"):
            os.chmod(os.path.join(path, rel), 0o755)
    info = {}
    setup = os.path.join(path, DEF_DIR, "setup.py")
    if os.path.isfile(setup):
        p = subprocess.run([sys.executable, setup], cwd=path, capture_output=True, text=True,
                           timeout=300)
        if p.returncode != 0:
            raise Refusal("{}'s setup.py failed: {}".format(which, tail(p.stderr or p.stdout, 6)))
        try:
            info = json.loads(p.stdout.strip() or "{}")
        except ValueError:
            info = {"setup_output": tail(p.stdout, 4)}
    git(["init", "-q", "-b", "main"], path)
    git(["add", "-A"], path)
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "autoresearch example")
    env.setdefault("GIT_AUTHOR_EMAIL", "ar@example.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "autoresearch example")
    env.setdefault("GIT_COMMITTER_EMAIL", "ar@example.invalid")
    subprocess.run(["git", "commit", "-q", "-m", "{}: initial state".format(which)], cwd=path,
                   env=env, check=True, capture_output=True)
    info["files"] = len(copied)
    return info


def cmd_example(args):
    path = os.path.abspath(args.dir)
    info = example_repo(args.which, path)
    cfg = load_research(path)
    subjects = [s["name"] for s in cfg["subjects"]]
    return {"ok": True, "example": args.which, "repo": path, "research": cfg["name"],
            "ar_dir": cfg["ar_dir"], "subjects": subjects, "info": info,
            "next": ["{} doctor --repo {}".format(os.path.basename(__file__), path),
                     "{} run {} --repo {}".format(os.path.basename(__file__), subjects[0],
                                                  path)]}, 0


# ----------------------------------------------------------------------------- main


def build_parser():
    p = Parser(prog="ar.py", add_help=True, description=__doc__.splitlines()[0])
    subs = p.add_subparsers(dest="cmd")
    # --repo lives on the subcommands, not here, so that it can follow them on the command line.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=".", help="the target repository (default: cwd)")

    subs.add_parser("doctor", parents=[common],
                    help="what is installed and what state the repo is in")

    init = subs.add_parser("init", parents=[common], help="scaffold a research definition")
    init.add_argument("--name")
    init.add_argument("--subject", action="append")
    init.add_argument("--harness", default="claude", choices=list(HARNESS_TYPES))
    init.add_argument("--describe", default="")

    run = subs.add_parser("run", parents=[common], help="drive rounds until a stop condition")
    run.add_argument("subject")
    run.add_argument("--rounds", type=int, default=None,
                     help="stop after this many rounds in this run (default: until a stop "
                          "condition)")
    run.add_argument("--dry-prompt", action="store_true",
                     help="print the prompt the next round would send, run nothing")

    st = subs.add_parser("status", parents=[common],
                         help="every subject, rebuilt from the checkpoints")
    st.add_argument("subject", nargs="?")

    subs.add_parser("report", parents=[common], help="regenerate the report")

    sv = subs.add_parser("serve", parents=[common],
                         help="serve the report at a local URL, re-read from the ledger")
    sv.add_argument("--port", type=int, default=7788)
    sv.add_argument("--no-open", action="store_true", help="do not open a browser tab")

    ex = subs.add_parser("example", help="generate a research to try the loop on")
    ex.add_argument("which", choices=example_names() or ["toy", "kata"],
                    help="one of the directories under examples/")
    ex.add_argument("dir")
    return p


def main(argv):
    parser = build_parser()
    if len(argv) == 1:
        print(json.dumps({"ok": False, "error": "no subcommand",
                          "usage": [l.strip() for l in __doc__.splitlines()
                                    if l.startswith("  ") and l.strip()]}, ensure_ascii=False,
                         indent=2))
        return 2
    try:
        args = parser.parse_args(argv[1:])
    except UsageError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "usage": exc.usage},
                         ensure_ascii=False))
        return 2
    except SystemExit as exc:  # --help printed itself
        return 2 if exc.code else 0
    handlers = {"doctor": cmd_doctor, "init": cmd_init, "run": cmd_run, "status": cmd_status,
                "report": cmd_report, "serve": cmd_serve, "example": cmd_example}
    if args.cmd not in handlers:
        print(json.dumps({"ok": False, "error": "unknown subcommand {!r}".format(args.cmd)},
                         ensure_ascii=False))
        return 2
    try:
        out, code = handlers[args.cmd](args)
    except Refusal as exc:
        out = {"ok": False, "error": str(exc)}
        out.update(exc.extra)
        code = 1
    except KeyboardInterrupt:
        out, code = {"ok": False, "error": "interrupted"}, 1
    except Exception as exc:  # noqa: BLE001 - a runner that crashes is a runner that lies
        import traceback
        out = {"ok": False, "error": "{}: {}".format(type(exc).__name__, exc),
               "traceback": traceback.format_exc().splitlines()[-6:]}
        code = 1
    if out is not None:  # serve prints its one object up front, before it blocks
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
