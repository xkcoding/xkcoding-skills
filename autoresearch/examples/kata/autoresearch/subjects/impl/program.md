# Subject: impl

## Goal

Write `src/qs.py` so that it parses every case in `cases/` the way `spec/features.json` says.

## What you are working with

- `src/qs.py` — must define `parse(query: str) -> dict`. It is the only file you change.
- `spec/features.json` — the rules. They are the specification; the cases are examples of them.
- `cases/*.json` — the inputs you are scored on. They are read-only for you: deleting a case
  you cannot pass would raise the score without fixing anything, so the runner treats a change
  under `cases/` as a failed round.

## How you are measured

- score = the number of cases your parser gets exactly right, compared against the rules
- each case runs in its own process with a two second limit; a hang or a crash fails that case
- the gate rejects a `src/qs.py` that does not compile
- the remaining list names every failing case with what was expected and what came out

## Ground rules for this subject

- Fix a class of failures per round, not one case at a time, and never special-case an input.
- Only the standard library.
- Do not open anything under `autoresearch/`: the reference parser is in there, and copying it
  would make the measurement meaningless.
