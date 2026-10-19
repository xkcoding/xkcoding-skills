# Subject: cases

## Goal

Build a test suite for a query-string parser, one case per file in `cases/`, that covers the
behaviour listed in `spec/features.json` — including combinations of two features in one input,
which is where parsers usually break.

## What you are working with

- `spec/features.json` — the rules and the twelve features. Read it first, every round.
- `cases/<name>.json` — one case: `{"input": "<query string>", "expected": <parsed value>}`.
  `expected` must be exactly what the rules in `spec/features.json` produce for that input.
- Nothing else. The parser itself is a different subject.

## How you are measured

- +1 for every feature covered by at least one valid case
- +0.05 for every pair of features that appear together in one valid case (66 pairs exist)
- −2 for every case whose feature set is identical to one another case already has
- a case that exercises **more than four features at once counts for nothing**: keep each case
  small enough that a failure points at one rule
- a case whose `expected` does not match the rules counts for nothing and is named in the
  remaining list, so check your expectations against `spec/features.json` by hand
- the gate rejects `cases/` holding anything but valid case JSON

## Ground rules for this subject

- One round, a handful of new cases. Aim at what the remaining list says is missing.
- Combine features, but stay under the ceiling: a case with three or four features is worth far
  more than three cases with one each, and a case with five is worth nothing at all. Note that
  `pair` and `multi_pair` are triggered by almost any query, so they usually take two of the four
  slots.
- Do not open the scorer or anything else under `autoresearch/`. There is a reference parser in
  there; copying from it would make the measurement meaningless.
