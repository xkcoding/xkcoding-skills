# Codec contract

`codec.py` at the repository root must define two functions:

```python
def encode(data: bytes) -> bytes: ...
def decode(blob: bytes) -> bytes: ...
```

`decode(encode(x)) == x` for every `bytes` value `x`, including the empty one. Both must be
deterministic. `codec.py` is the whole codec: it is loaded as a single module from the
repository root and may not read any other file.

## What the gate rejects

- Any import of `zlib`, `bz2`, `lzma`, `gzip`, `zipfile`, `tarfile`, `zipimport`, `ctypes`,
  `subprocess`, `multiprocessing`, `socket`, `urllib`, `http`, `ftplib`, `importlib`, `os`,
  `sys`, `pathlib`, `shutil`, `glob`, `pickle`, `marshal`, `shelve`, `codecs`.
- Any call to the builtins `open`, `__import__`, `exec`, `eval` or `compile`, or to any `.open()`, anywhere in `codec.py` (`re.compile` is fine).
- A working tree that changes anything other than `codec.py` (new files included).
- A round trip that fails or takes longer than 30 seconds on any single file, in `sample/` or in
  the corpus.

## What the score is

    total = sum(len(encode(f)) for f in corpus) + len(codec.py as bytes)

Lower is better. The corpus is seven files of different kinds (English prose, Python source,
JSON lines, CSV, Chinese text, structured repetition, random bytes); `random bytes` cannot be
compressed and exists to catch a codec that only looks like it works.
