"""Starting point: rank assets by how many query tokens appear in their name, tags and
description. Case-insensitive, split on anything that is not a letter or digit."""

import re

TOP_K = 20
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text):
    return set(_TOKEN.findall(text.lower()))


def recall(query, assets):
    q = _tokens(query)
    scored = []
    for a in assets:
        hay = _tokens(" ".join([a["name"], a["desc"]] + a["tags"]))
        overlap = len(q & hay)
        if overlap:
            scored.append((-overlap, a["id"]))
    scored.sort()
    return [aid for _s, aid in scored[:TOP_K]]
