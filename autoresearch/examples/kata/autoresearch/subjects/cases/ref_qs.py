#!/usr/bin/env python3
"""The reference parser and the feature detectors: what this kata counts as the truth.

Both scorers import this. It lives under the locked directory, so no round can change it —
and `program.md` tells the agent not to read it, because a round that copies the answer
teaches the loop nothing. The loop cannot enforce that; the scorer design has to survive it,
which is why `cases` is scored on coverage rather than on agreement with a single answer.

Standard library only; runs on Python 3.9.
"""

import re
from urllib.parse import unquote_plus

FEATURES = [
    "pair", "multi_pair", "repeat_key", "empty_value", "bare_key", "percent_encoded",
    "plus_as_space", "leading_question_mark", "array_suffix", "nested_key", "blank_segment",
    "equals_in_value",
]


def segments(query):
    if query.startswith("?"):
        query = query[1:]
    return query.split("&")


def parse(query):
    """Parse a query string into a dict. Deterministic for any input; see spec/features.json."""
    out = {}
    for seg in segments(query):
        if not seg:
            continue                                   # blank segment: &&, leading &, trailing &
        key, _eq, value = seg.partition("=")           # only the first = splits
        key, value = unquote_plus(key), unquote_plus(value)
        m = re.match(r"^(.*?)\[(.*)\]$", key)
        if m and m.group(2) == "":                     # a[]=1 -> always a list
            name = m.group(1)
            if not isinstance(out.get(name), list):
                out[name] = []
            out[name].append(value)
        elif m:                                        # a[b]=1 -> a dict under a
            name, inner = m.group(1), m.group(2)
            if not isinstance(out.get(name), dict):
                out[name] = {}
            out[name][inner] = value
        elif key in out:                               # a=1&a=2 -> a list, in order
            if isinstance(out[key], list):
                out[key].append(value)
            elif isinstance(out[key], dict):
                out[key] = value                       # shape conflict: the last form wins
            else:
                out[key] = [out[key], value]
        else:
            out[key] = value
    return out


def detect(query):
    """Which features this input exercises. The scorer trusts this, never the case's claim."""
    found = set()
    body = query[1:] if query.startswith("?") else query
    segs = segments(query)
    real = [s for s in segs if s]
    if query.startswith("?"):
        found.add("leading_question_mark")
    if len(segs) != len(real) and real:
        found.add("blank_segment")
    seen = {}
    for seg in real:
        key, eq, value = seg.partition("=")
        if eq and value:
            found.add("pair")
        if eq and not value:
            found.add("empty_value")
        if not eq:
            found.add("bare_key")
        if "=" in value:
            found.add("equals_in_value")
        if re.search(r"%[0-9A-Fa-f]{2}", seg):
            found.add("percent_encoded")
        if "+" in seg:
            found.add("plus_as_space")
        if key.endswith("[]"):
            found.add("array_suffix")
        elif re.match(r"^.*\[.+\]$", key):
            found.add("nested_key")
        literal = unquote_plus(key)        # a[b] and a[c] are different keys; a[] twice is not
        seen[literal] = seen.get(literal, 0) + 1
    if len(real) > 1:
        found.add("multi_pair")
    if any(n > 1 for n in seen.values()):
        found.add("repeat_key")
    if not body.strip():
        found.discard("pair")
    return found
