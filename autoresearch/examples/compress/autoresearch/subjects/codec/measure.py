#!/usr/bin/env python3
"""Run the codec on one file in a child process and check the round trip.

Shared by the gate and the scorer; both run from the repository root. The child imports
codec.py from the current directory, so a codec that hangs or crashes cannot take the gate or
the scorer down with it.
"""

import json
import os
import subprocess
import sys

WORKER = r'''
import json, sys, time
sys.path.insert(0, ".")
path = sys.argv[1]
data = open(path, "rb").read()
t0 = time.time()
try:
    import codec
    enc = codec.encode(data)
    if not isinstance(enc, (bytes, bytearray)):
        raise TypeError("encode returned {} instead of bytes".format(type(enc).__name__))
    dec = codec.decode(bytes(enc))
    if not isinstance(dec, (bytes, bytearray)):
        raise TypeError("decode returned {} instead of bytes".format(type(dec).__name__))
    ok = bytes(dec) == data
    out = {"ok": ok, "raw": len(data), "enc": len(enc), "ms": int((time.time() - t0) * 1000)}
    if not ok:
        i = next((k for k in range(min(len(dec), len(data))) if dec[k] != data[k]), min(len(dec), len(data)))
        out["error"] = "round trip differs at byte {} (decoded {} bytes, expected {})".format(i, len(dec), len(data))
except Exception as exc:
    out = {"ok": False, "raw": len(data), "enc": None, "ms": int((time.time() - t0) * 1000),
           "error": "{}: {}".format(type(exc).__name__, str(exc)[:200])}
print(json.dumps(out))
'''

TIMEOUT_SEC = 30


def run_codec(path, timeout=TIMEOUT_SEC):
    try:
        p = subprocess.run([sys.executable, "-c", WORKER, path], capture_output=True, text=True,
                           timeout=timeout, cwd=os.getcwd())
    except subprocess.TimeoutExpired:
        return {"ok": False, "raw": os.path.getsize(path), "enc": None, "ms": timeout * 1000,
                "error": "timeout: encode + decode took more than {} s".format(timeout)}
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "raw": os.path.getsize(path), "enc": None, "ms": None,
                "error": "worker produced no result: {}".format((p.stderr or "").strip()[-300:])}


def files_in(directory):
    return sorted(os.path.join(directory, n) for n in os.listdir(directory)
                  if os.path.isfile(os.path.join(directory, n)))
