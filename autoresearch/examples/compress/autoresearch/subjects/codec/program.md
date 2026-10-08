# Subject: codec

## Goal

Shrink the corpus. The score is the total number of bytes after encoding every file under
`autoresearch/subjects/codec/corpus/`, plus the byte size of `codec.py` itself. Lower is better.
There is no finish line: each round should remove bytes the previous codec left on the table.

## What you are working with

- `codec.py` — the only file you change. `encode(bytes) -> bytes`, `decode(bytes) -> bytes`,
  exact inverses, deterministic, standard library only, no file access.
- `spec/CONTRACT.md` — the exact rules the gate enforces and the banned modules. Read it first.
- `sample/` — small public files of each kind in the corpus; use them for quick round-trip
  checks while you work.
- `autoresearch/subjects/codec/corpus/` — the seven files you are scored on. You may read them
  to understand the data. One of them is random bytes: a good codec leaves it alone.
- `./autoresearch/subjects/codec/gate` — run it as often as you like; it is exactly what runs
  before scoring. `./autoresearch/subjects/codec/score` prints the score and the per-file sizes.

## How you are measured

- score = encoded corpus bytes + `len(codec.py)`. Every byte of source counts, comments and
  docstrings included, so keep the decoder lean: a 3 KB model that saves 2 KB is a loss.
- The gate crashes the round if `codec.py` imports a banned module, calls `open` / `exec` /
  `eval` / `__import__`, if anything other than `codec.py` changed, or if any file fails to
  round-trip or takes more than 30 s to encode and decode. A crashed round is reverted
  without being scored.
- Equal bytes is a discard. Only a strictly smaller total is kept.

## Ground rules for this subject

- One technique per round: run-length, LZ77/LZSS, Huffman, LZW, BWT + MTF, arithmetic or
  range coding, context modelling, a tuned static dictionary - each is one round, so that the
  score tells you what each one was worth. Do not rewrite everything at once.
- Pure Python is slow. Keep encode + decode under a few seconds per file; the hard limit is 30 s
  each, and the corpus is about 100 KB in total.
- Run the gate before you stop. A round that fails the gate is worth nothing.
