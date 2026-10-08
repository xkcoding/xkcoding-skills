# retrieval

A two-stage pipeline of the shape "recall candidates, then pick the one to use", scored on a
held-out split the agent never trains on:

1. **`recall`** — `recall.py` turns a query into up to 20 candidate asset ids. Scored on
   recall (is the target among them) and precision (how many candidates are even about the
   right thing).
2. **`select`** — `select.py` picks one id out of the candidates that the current `recall.py`
   produces. Scored on how often it picks the target. It can only start once `recall` has
   kept a round, and it cannot do better than recall's ceiling.

Queries are what people type: English or Chinese, synonyms, hex colours, size words, typos,
and sometimes a preference ("latest", "最多人用", "svg") that only matters when several assets
fit. The rules are in `spec/PIPELINE.md`; the surface forms are not, and finding them is the
work.

- `data/assets.jsonl` — the library (550 assets)
- `data/train.jsonl` — 400 public queries with their target and relevant set
- `autoresearch/data/heldout.jsonl` — 400 held-out queries, same generator, different seed.
  Readable, as everything in the repository is; using it is cheating, and the gap between
  public and held-out scores in every report is how it would show.

    ar.py run recall --rounds 20
    ar.py run select --rounds 15

What a run looked like (2026-10-08, Claude Code 2.1.294, `harness.model: sonnet`): `recall`
went 28.2 → 98.7 in its first round and reached 100.0 at round 8, then stopped on 8 discards
in a row (17 checkpoints, $4.17); `select` started at 95.0 on those candidates, reached 99.75
at round 3 and stopped the same way (12 checkpoints, $3.47). The vocabulary here is finite,
so a strong model exhausts it in a round or two; what this example is for is the shape — two
stages, a locked held-out split, the public/held-out gap as the overfitting signal, and the
ceiling the second stage inherits from the first.
