#!/usr/bin/env python3
"""Draw this instance's hidden target, so that every generated toy is a different puzzle.
Runs once from the repository root when `ar.py example toy` generates the repository."""
import json
import os
import random

hidden = [round(random.uniform(-5, 5), 2) for _ in range(6)]
for name in ("vec", "polish"):
    with open(os.path.join("autoresearch", "subjects", name, "target.json"), "w") as fh:
        fh.write(json.dumps({"v": hidden}) + "\n")
print(json.dumps({"hidden_target": hidden}))
