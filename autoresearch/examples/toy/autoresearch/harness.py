#!/usr/bin/env python3
"""The toy's agent: read the prompt on stdin, nudge one component of vec.json.

It is deliberately stupid - it only knows the component named in the prompt's "Still
missing" list, and it moves it by a random step. That is enough to exercise every path
of the loop (keep, discard, empty round) without spending a cent on a model.
"""

import json
import random
import re
import sys

prompt = sys.stdin.read()
vec = json.load(open("vec.json"))
want = re.findall(r"component (\d+) is off by ([-0-9.]+)", prompt)
i = int(want[0][0]) if want else random.randrange(len(vec["v"]))
hint = float(want[0][1]) if want else random.uniform(-1, 1)
# Never exactly right: undershoot, overshoot and sometimes move the wrong way, so that keeps,
# discards and reverts all happen the way they do with a real agent.
step = round(hint * random.uniform(-0.4, 1.9), 4)
vec["v"][i] = round(vec["v"][i] + step, 4)
json.dump(vec, open("vec.json", "w"), indent=2)
print("Moved component {} by {} (the gap was {}); expecting the distance to shrink.".format(
    i, step, hint))
