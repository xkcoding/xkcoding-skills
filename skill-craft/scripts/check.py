#!/usr/bin/env python3
"""check.py - measurable facts about a skill directory.

    check.py <skill-dir> [<skill-dir> ...]        one JSON object per skill
    check.py <skill-dir> --table                  one line per skill, for a human

It measures; it does not judge. Nothing here is a verdict: a long SKILL.md may be
right for a taste-driven skill, and a skill with no scripts may have nothing
deterministic to automate. The numbers are material for that judgement, and the
`flags` are the few things that are wrong regardless of the skill's kind:
broken frontmatter, links that leave the directory, dead or orphaned files,
scripts that do not parse, absolute paths from the author's machine.

Standard library only. Never raises: a skill that cannot be read is reported,
not crashed on.
"""

import json
import os
import re
import subprocess
import sys

# A skill's own directory is its world: anything it links to must live inside it.
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s#]+)")
FENCE_RE = re.compile(r"```.*?```", re.S)
PATHISH_RE = re.compile(r"[/.]")  # a real link has a slash or an extension
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
STEP_RE = re.compile(r"^\s*(?:\d+[.)]|[-*]\s*\[\s?\])\s+\S", re.M)
MUST_RE = re.compile(r"\bMUST\b|\bSHALL\b|\bNEVER\b|必须|禁止|永不", re.I)
HOME_PATH_RE = re.compile(r"(?<![\w.])/(?:Users|home)/[A-Za-z][\w.-]*/")
# Identifiers that belong to how the skill was developed, not to using it.
LEAK_RE = re.compile(r"\b[DFV]\d+\b|design\.md|proposal\.md|tasks\.md 的第|openspec/changes/")


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        return None if not os.path.exists(path) else "�" + str(exc)


def split_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    return text[3:end].strip("\n"), text[end + 4:]


def parse_frontmatter(raw):
    """Top-level keys only. Tries PyYAML, falls back to a scanner that handles
    plain, folded (>-, |) and quoted scalars - enough to check name/description."""
    if raw is None:
        return None, "no frontmatter"
    try:
        import yaml
        data = yaml.safe_load(raw)
        return (data, None) if isinstance(data, dict) else (None, "frontmatter is not a mapping")
    except ImportError:
        pass
    except Exception as exc:
        return None, "frontmatter does not parse: {}".format(str(exc).splitlines()[0])
    data, key, buf = {}, None, []
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            if key:
                data[key] = "\n".join(buf).strip()
            key, rest = m.group(1), m.group(2).strip()
            buf = [] if rest in ("", ">", ">-", "|", "|-") else [rest]
        elif key and (line.startswith((" ", "\t")) or not line.strip()):
            buf.append(line.strip())
    if key:
        data[key] = "\n".join(buf).strip()
    return data, None


def script_syntax(path):
    if path.endswith(".py"):
        cmd = [sys.executable, "-c", "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())", path]
    elif path.endswith((".sh", ".bash")):
        cmd = ["bash", "-n", path]
    else:
        return None  # not a language we can check here
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return True if p.returncode == 0 else (p.stderr or p.stdout).strip().splitlines()[-1][:160]
    except Exception as exc:
        return str(exc)[:160]


def walk(root, sub):
    out = []
    base = os.path.join(root, sub)
    for dirpath, _dirs, files in os.walk(base):
        for f in sorted(files):
            if f.startswith(".") or f.endswith((".pyc",)):
                continue
            out.append(os.path.relpath(os.path.join(dirpath, f), root))
    return sorted(out)


def inspect(skill_dir):
    root = os.path.abspath(skill_dir)
    name = os.path.basename(root)
    out = {"skill": name, "path": root, "flags": []}
    flag = out["flags"].append

    md_path = os.path.join(root, "SKILL.md")
    text = read(md_path)
    if text is None:
        flag("no SKILL.md")
        return out
    raw_fm, body = split_frontmatter(text)
    fm, fm_err = parse_frontmatter(raw_fm)

    # --- frontmatter ---
    desc = (fm or {}).get("description") or ""
    info = {"parsed": fm is not None, "keys": sorted(fm) if fm else [],
            "name": (fm or {}).get("name"), "description_chars": len(desc)}
    if fm_err:
        info["error"] = fm_err
        flag(fm_err)
    else:
        if not info["name"]:
            flag("frontmatter has no name")
        elif info["name"] != name:
            flag("frontmatter name '{}' does not match directory '{}'".format(info["name"], name))
        if not desc:
            flag("frontmatter has no description")
        elif len(desc) > 1024:
            flag("description is {} chars (limit 1024)".format(len(desc)))
        if re.match(r"^\s*(I |I'|我(?!们的)|I,)", desc):
            flag("description reads first person; skill descriptions are third person")
    out["frontmatter"] = info

    # --- size ---
    refs, scripts = walk(root, "references"), walk(root, "scripts")
    other = [f for f in walk(root, "") if f != "SKILL.md" and f not in refs and f not in scripts]
    out["size"] = {
        "skill_md_lines": body.count("\n") + 1,
        "references": {f: (read(os.path.join(root, f)) or "").count("\n") + 1 for f in refs},
        "scripts": {f: (read(os.path.join(root, f)) or "").count("\n") + 1 for f in scripts},
        "other_files": other,
    }

    # --- structure: everything the skill points at must live inside it ---
    all_text = text + "".join(read(os.path.join(root, f)) or "" for f in refs)
    prose = FENCE_RE.sub("", all_text)  # examples inside fences are not links
    outside, dead = [], []
    for target in LINK_RE.findall(prose):
        if re.match(r"^[a-z]+:", target) or target.startswith("#") or not PATHISH_RE.search(target):
            continue
        if re.search(r"[{<*]", target):
            continue  # a pattern like references/site-patterns/{domain}.md
        resolved = os.path.abspath(os.path.join(root, target))
        if os.path.commonpath([resolved, root]) != root:
            outside.append(target)
        elif not os.path.exists(resolved):
            dead.append(target)
    # A directory of interchangeable files (site patterns, presets, styles) is loaded by
    # pattern, not linked one by one: naming the directory is enough.
    grouped = set()
    for f in refs:
        d = os.path.dirname(f)
        if d.count(os.sep) >= 1 and sum(1 for r in refs if os.path.dirname(r) == d) >= 3 and d in all_text:
            grouped.add(f)
    mentioned = lambda f: os.path.basename(f) in all_text or f in all_text or f in grouped
    orphan_refs = [f for f in refs if not mentioned(f)]
    # A helper imported by another script, or a manifest, is not an orphan.
    script_text = "".join(read(os.path.join(root, f)) or "" for f in scripts)
    orphan_scripts = [f for f in scripts if not mentioned(f)
                      and os.path.basename(f) not in script_text
                      and not re.match(r"^(package(-lock)?\.json|bun\.lockb?|requirements\.txt|tsconfig\.json|"
                                       r"go\.(mod|sum)|Cargo\.(toml|lock)|\.env\.example)$", os.path.basename(f))]
    # The antipattern is a chain - a reference that sends the reader to another reference.
    chains = sorted({f for f in refs
                     for t in LINK_RE.findall(FENCE_RE.sub("", read(os.path.join(root, f)) or ""))
                     if t.startswith("references/") or (os.path.dirname(f) and not t.startswith(("http", "#"))
                     and os.path.normpath(os.path.join(os.path.dirname(f), t)).startswith("references" + os.sep))})
    out["structure"] = {
        "headings": [h[1] for h in HEADING_RE.findall(body) if len(h[0]) <= 2],
        "links_outside_skill": sorted(set(outside)),
        "dead_links": sorted(set(dead)),
        "unreferenced_files": sorted(orphan_refs + orphan_scripts),
        "reference_chains": chains,
        "pattern_loaded_groups": sorted({os.path.dirname(f) for f in grouped}),
    }
    for t in sorted(set(outside)):
        flag("links outside the skill directory: " + t)
    for t in sorted(set(dead)):
        flag("dead link: " + t)
    for f in orphan_refs + orphan_scripts:
        flag("never mentioned in SKILL.md: " + f)
    for f in chains:
        flag("reference links to another reference (load it from SKILL.md instead): " + f)

    # --- scripts ---
    sc = {}
    for f in scripts:
        p = os.path.join(root, f)
        syn = script_syntax(p)
        sc[f] = {"syntax": syn, "executable": os.access(p, os.X_OK),
                 "shebang": (read(p) or "").startswith("#!")}
        if syn not in (True, None):
            flag("{} does not parse: {}".format(f, syn))
    out["scripts"] = sc

    # --- portability and leakage ---
    hard, leaks = {}, {}
    for f in ["SKILL.md"] + refs + scripts:
        t = read(os.path.join(root, f)) or ""
        h = sorted(set(HOME_PATH_RE.findall(t)))
        l = sorted(set(LEAK_RE.findall(t)))
        if h:
            hard[f] = h
            flag("absolute path from the author's machine in " + f)
        if l:
            leaks[f] = l
    out["portability"] = {"absolute_home_paths": hard}
    out["leakage"] = {"development_identifiers": leaks}

    # --- text signals: material for judgement, never a verdict ---
    out["signals"] = {
        "step_lines": len(STEP_RE.findall(body)),
        "tables": body.count("\n|"),
        "code_blocks": body.count("```") // 2,
        "hard_constraints": len(MUST_RE.findall(body)),
        "has_reference_index": bool(refs) and bool(re.search(r"何时加载|when to load|References? 索引|References? index", body, re.I)),
    }
    if refs and not out["signals"]["has_reference_index"]:
        flag("has references/ but no index saying when to load each one")
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    table = "--table" in argv[1:]
    if not args:
        print(__doc__.strip())
        return 2
    results = []
    for d in args:
        try:
            results.append(inspect(d))
        except Exception as exc:
            results.append({"skill": os.path.basename(os.path.abspath(d)),
                            "flags": ["check.py failed: {}: {}".format(type(exc).__name__, exc)]})
    if table:
        print("{:<26} {:>6} {:>5} {:>5}  {:>5} {:>6}  {}".format(
            "SKILL", "LINES", "REFS", "SCR", "STEPS", "MUSTS", "FLAGS"))
        for r in results:
            s, g = r.get("size", {}), r.get("signals", {})
            print("{:<26} {:>6} {:>5} {:>5}  {:>5} {:>6}  {}".format(
                r["skill"][:26], s.get("skill_md_lines", "-"), len(s.get("references", {})),
                len(s.get("scripts", {})), g.get("step_lines", "-"), g.get("hard_constraints", "-"),
                len(r["flags"]) or "-"))
            for f in r["flags"]:
                print("    ! " + f)
        return 0
    print(json.dumps(results[0] if len(results) == 1 else results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
