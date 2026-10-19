"""Run the agent's recall.py / select.py on a split in a child process and score the output.

Shared by both subjects' gate and score. The child imports the modules from the repository
root, so a hang or a crash in the agent's code cannot take the scorer down with it.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen import read_jsonl  # noqa: E402

ASSETS = os.path.join("data", "assets.jsonl")
PUBLIC = os.path.join("data", "train.jsonl")
HELDOUT = os.path.join(os.path.dirname(HERE), "data", "heldout.jsonl")
TOP_K = 20
TIMEOUT_SEC = 90

WORKER = r'''
import json, sys
sys.path.insert(0, ".")
stage, assets_path, split_path = sys.argv[1], sys.argv[2], sys.argv[3]
assets = [json.loads(l) for l in open(assets_path, encoding="utf-8") if l.strip()]
queries = [json.loads(l) for l in open(split_path, encoding="utf-8") if l.strip()]
import recall as recall_mod
select_mod = __import__("select") if stage == "select" else None
out = {}
for q in queries:
    ids = recall_mod.recall(q["query"], assets)
    if not isinstance(ids, (list, tuple)):
        raise TypeError("recall() returned {} instead of a list".format(type(ids).__name__))
    ids = [str(x) for x in ids][:%d]
    rec = {"cands": ids}
    if select_mod:
        chosen = select_mod.select(q["query"], list(ids), assets)
        if chosen is not None and not isinstance(chosen, str):
            raise TypeError("select() returned {} instead of a str or None".format(type(chosen).__name__))
        rec["chosen"] = chosen
    out[q["id"]] = rec
print("@@RESULT@@" + json.dumps(out))
''' % TOP_K


def run_stage(stage, split_path, timeout=TIMEOUT_SEC):
    """Returns (results, error). results maps query id -> {"cands": [...], "chosen": ...}."""
    try:
        p = subprocess.run([sys.executable, "-c", WORKER, stage, ASSETS, split_path],
                           capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
    except subprocess.TimeoutExpired:
        return None, "timeout: {} on {} took more than {} s".format(stage, split_path, timeout)
    marker = "@@RESULT@@"
    for line in p.stdout.splitlines():
        if line.startswith(marker):
            return json.loads(line[len(marker):]), None
    return None, "{} failed on {}: {}".format(stage, split_path, (p.stderr or p.stdout).strip()[-600:])


def recall_metrics(results, queries):
    hits, precisions, missed, low = 0, [], [], []
    for q in queries:
        cands = results.get(q["id"], {}).get("cands", [])
        relevant = set(q["relevant"])
        hit = q["gt"] in cands
        hits += hit
        prec = (sum(1 for c in cands if c in relevant) / len(cands)) if cands else 0.0
        precisions.append(prec)
        if not hit:
            missed.append(q)
        elif prec < 0.5:
            low.append((q, sum(1 for c in cands if c in relevant), len(cands)))
    n = len(queries) or 1
    return {"recall": round(hits / n, 4), "precision": round(sum(precisions) / n, 4),
            "missed": missed, "low_precision": low, "n": len(queries)}


def select_metrics(results, queries):
    hits, in_cands, misses = 0, 0, []
    for q in queries:
        rec = results.get(q["id"], {})
        cands, chosen = rec.get("cands", []), rec.get("chosen")
        if q["gt"] in cands:
            in_cands += 1
        if chosen == q["gt"]:
            hits += 1
        else:
            misses.append((q, chosen, q["gt"] in cands))
    n = len(queries) or 1
    return {"hit": round(hits / n, 4), "ceiling": round(in_cands / n, 4), "misses": misses,
            "n": len(queries)}


def asset_index():
    return dict((a["id"], a) for a in read_jsonl(ASSETS))


def describe(asset_by_id, aid):
    a = asset_by_id.get(aid)
    if not a:
        return "{} (not an asset)".format(aid)
    return "{} {} {} {} {} {} {}px {} v{} {}dl".format(
        a["id"], a["subject"], a["style"], a["color"], a["kind"], a["platform"], a["size"],
        a["format"], a["version"], a["downloads"])
