# Subject: select

## Goal

Make `select.py` pick, out of the candidates `recall.py` hands it, the one asset the query
means. The score is `100 × hit rate` on a held-out split you do not see.

## What you are working with

- `select.py` — the only file you change. `select(query, candidates, assets) -> str | None`.
  Standard library only, no file or network access.
- `recall.py` — locked. It is the recall stage as the other subject left it; its candidates
  are your input, and the share of held-out queries whose target is among them is your
  ceiling. The scorer prints that ceiling.
- `spec/PIPELINE.md` — the selection rules: attribute match, format preference, latest, most
  downloads, lower id on ties. The rules are fixed; what varies is how queries say things.
- `data/assets.jsonl`, `data/train.jsonl` — the library and 400 public queries with `gt`.
- `./autoresearch/subjects/select/gate` and `./autoresearch/subjects/select/score` — run them
  as often as you like; the score lists the public queries you get wrong and what you chose.

## How you are measured

- A hit is `select(...) == gt`. Picking a candidate that matches every mentioned attribute but
  loses on the preference rule is still a miss.
- The gate crashes the round if `select.py` imports a file, network or process module, calls
  `open` / `exec` / `eval`, if anything other than `select.py` changed, or if a 400-query split
  takes more than 90 s. Equal score is a discard.

## Ground rules for this subject

- One improvement per round: parsing one more way of saying an attribute, one preference word,
  one rule. The remaining list shows the misses with what was chosen and what was meant.
- Candidates that do not match the query's attributes are recall's noise; verify every
  mentioned attribute yourself rather than trusting candidate order.
- Never map a query or a query id to an asset id.
