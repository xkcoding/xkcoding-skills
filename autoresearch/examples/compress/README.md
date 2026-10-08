# compress

A research with a far ceiling and no noise: write a single-file, pure-Python codec and make a
fixed corpus as small as possible. The score is **bytes**, lower is better:

    score = sum(len(encode(file)) for file in corpus) + len(codec.py)

The codec's own source counts, so a decoder that carries the corpus inside it gains nothing;
what wins is modelling the data. Standard-library compression modules are banned by the gate,
otherwise round one would be `zlib.compress`.

- `codec.py` — the only file the agent edits; starts as the identity codec
- `spec/CONTRACT.md` — the interface, the banned modules, how the score is computed
- `sample/` — small public files of the same kinds as the corpus, for quick checks
- `autoresearch/subjects/codec/corpus/` — the scoring corpus, generated when the example is
  created; readable, never editable

    ar.py run codec --rounds 30

Cost is the thing to know before starting: one round here is real work (write, run the gate,
tune, measure). On 2026-10-08 with Claude Code 2.1.294, an opus round took 18 turns, 7 minutes
and $3.20; with `harness.model: sonnet` a round took 50–110 seconds and about $0.31. Set the
model in `autoresearch/research.json` before the first `run`.

What 31 rounds looked like (2026-10-08, sonnet after the first round): 105,248 → 38,694 (order-2
context model + arithmetic coding) → 29,719 (logistic mixing of orders 0–4) → 28,275 at round 8
→ 27,869 at round 29, a 4.04× ratio with the codec at 1,834 bytes; 21 keeps, 11 discards, no
crash, no stop condition reached, $11.76 in total. Discards start around round 9 and come in
runs after round 20, with each keep worth single-digit bytes by then - a research in its late
stage.
