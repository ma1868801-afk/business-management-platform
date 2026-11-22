#!/usr/bin/env python3
"""The isolated worker process for `pandas_tool` (05_security_and_guardrails.md section 7.2).

Invoked as a fresh subprocess with a fully scrubbed environment (no GROQ_API_KEY, no
database URLs -- `pandas_tool.py` builds that environment and never passes its own), reads
one JSON request on stdin, and writes one JSON response on stdout. It never touches the
network or the filesystem beyond stdin/stdout, and it does not need to (the AST validator
already ran in the parent process before this script is started at all; this script repeats
the resource/isolation side only, per section 7.3: "the validator reduces risk; the process
boundary provides the protection").

Run as: `python3 -I app/tools/_pandas_worker.py` (the `-I` isolated-mode flag ignores
PYTHONPATH/PYTHONHOME and the per-user site directory, hardening against environment-based
injection while still loading the regular site-packages so pandas/numpy/scipy import).
"""
from __future__ import annotations

import json
import math
import resource
import sys

# ---- resource limits, applied before anything else in this process -------------------------
_CPU_SECONDS = 5
_ADDRESS_SPACE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB
_MAX_OPEN_FILES = 16

try:
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_SECONDS, _CPU_SECONDS))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_AS, (_ADDRESS_SPACE_BYTES, _ADDRESS_SPACE_BYTES))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (_MAX_OPEN_FILES, _MAX_OPEN_FILES))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))  # no forking / subprocesses from here
except (ValueError, OSError):
    pass

import os  # noqa: E402  (imported only to clear the environment; never exposed to user code)

os.environ.clear()
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import builtins  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

MAX_OUTPUT_ROWS = 200

ALLOWED_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max",
        "min", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    )
}


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return True  # not a number at all (string, bool, None) -- fine, only numbers must be finite


def _to_jsonable(obj, _depth: int = 0):
    """Convert a pandas/numpy result into plain JSON-safe Python values (P-11): only tables,
    series, dictionaries and scalars with finite numbers are accepted."""
    if _depth > 6:
        raise ValueError("result is nested too deeply to serialize")
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, (int,)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("a non-finite number (NaN/Infinity) cannot be returned")
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if not math.isfinite(v):
            raise ValueError("a non-finite number (NaN/Infinity) cannot be returned")
        return v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        if len(obj) > MAX_OUTPUT_ROWS:
            raise ValueError(f"result has {len(obj)} rows, over the {MAX_OUTPUT_ROWS}-row output cap")
        records = obj.replace({np.nan: None}).to_dict(orient="records")
        return _to_jsonable(records, _depth + 1)
    if isinstance(obj, pd.Series):
        if len(obj) > MAX_OUTPUT_ROWS:
            raise ValueError(f"result has {len(obj)} rows, over the {MAX_OUTPUT_ROWS}-row output cap")
        d = obj.replace({np.nan: None}).to_dict()
        return _to_jsonable(d, _depth + 1)
    if isinstance(obj, dict):
        if len(obj) > MAX_OUTPUT_ROWS:
            raise ValueError(f"result has {len(obj)} entries, over the {MAX_OUTPUT_ROWS}-row output cap")
        return {str(k): _to_jsonable(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        if len(obj) > MAX_OUTPUT_ROWS:
            raise ValueError(f"result has {len(obj)} items, over the {MAX_OUTPUT_ROWS}-row output cap")
        return [_to_jsonable(v, _depth + 1) for v in obj]
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist(), _depth + 1)
    raise ValueError(f"result of type {type(obj).__name__} cannot be serialized")


def _build_frame(spec):
    if spec is None:
        return pd.DataFrame()
    return pd.DataFrame.from_records(spec)


def main() -> int:
    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": {"code": "P-10", "message": f"invalid request JSON: {e}"}}))
        return 0

    code = request.get("code", "")
    df = _build_frame(request.get("df"))
    dfs_spec = request.get("dfs") or {}
    dfs = {k: _build_frame(v) for k, v in dfs_spec.items()}

    namespace = {
        "__builtins__": ALLOWED_BUILTINS,
        "df": df,
        "dfs": dfs,
        "pd": pd,
        "np": np,
        "stats": stats,
        "math": math,
    }

    try:
        compiled = compile(code, "<pandas_tool>", "exec")
    except SyntaxError as e:
        print(json.dumps({"error": {"code": "P-01", "message": str(e)}}))
        return 0

    try:
        exec(compiled, namespace)  # noqa: S102 -- this is the sandboxed worker itself
    except MemoryError:
        print(json.dumps({"error": {"code": "P-09", "message": "memory limit exceeded"}}))
        return 0
    except Exception as e:  # noqa: BLE001 -- any runtime error is reported, not crashed on
        print(json.dumps({"error": {"code": "P-10", "message": f"{type(e).__name__}: {e}"}}))
        return 0

    if "result" not in namespace:
        print(json.dumps({"error": {"code": "P-08", "message": "the code did not assign `result`"}}))
        return 0

    try:
        result_json = _to_jsonable(namespace["result"])
        facts_json = _to_jsonable(namespace.get("facts")) if "facts" in namespace else None
    except ValueError as e:
        print(json.dumps({"error": {"code": "P-11", "message": str(e)}}))
        return 0

    out = {"result": result_json, "elapsed_ms": None}
    if facts_json is not None:
        out["facts"] = facts_json
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
