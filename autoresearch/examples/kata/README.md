# qs-kata

A two-subject research for trying the loop on something small and real: first the cases that
pin down what a query-string parser should do, then the parser that satisfies them.

- `spec/features.json` — the behaviour both subjects are measured against
- `cases/` — written by the `cases` subject
- `src/qs.py` — written by the `impl` subject, which only runs once `cases` has kept a round
- `autoresearch/` — the research definition: scorers, gates, programs. Locked during rounds.

    ar.py doctor
    ar.py run cases --rounds 10
    ar.py run impl --rounds 8
