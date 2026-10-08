# toy autoresearch

A research that needs no model: the harness is a script that nudges one number, the scorer
measures the distance to a target it hides from the agent. Every keep, discard, revert and
scorer-version switch of the real loop happens here, in seconds and for free.

- `vec.json` — six numbers the agent moves
- `autoresearch/harness.py` — the "agent": reads the prompt on stdin, moves one component
- `autoresearch/subjects/<name>/target.json` — the hidden target, written when the example is
  generated (different every time)

    ar.py run vec --rounds 50
