#!/usr/bin/env python3
"""Generate this instance's asset library, the public query split and the held-out split.
Runs once, from the repository root, when `ar.py example retrieval` generates the repository."""
import json
import os
import sys

sys.path.insert(0, os.path.join("autoresearch", "lib"))
import gen  # noqa: E402

assets, train, heldout = gen.generate(library_seed=20261008, train_seed=1, heldout_seed=2,
                                      n_train=400, n_heldout=400)
os.makedirs("data", exist_ok=True)
os.makedirs(os.path.join("autoresearch", "data"), exist_ok=True)
gen.write_jsonl(os.path.join("data", "assets.jsonl"), assets)
gen.write_jsonl(os.path.join("data", "train.jsonl"), train)
gen.write_jsonl(os.path.join("autoresearch", "data", "heldout.jsonl"), heldout)
print(json.dumps({"assets": len(assets), "train_queries": len(train),
                  "heldout_queries": len(heldout),
                  "sample_queries": [q["query"] for q in train[:5]]}, ensure_ascii=False))
