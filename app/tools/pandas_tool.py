
"""Isolated Pandas execution tool with safe JSON serialization."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time

from datetime import date, datetime, time as datetime_time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import numpy as np
import pandas as pd

from app.config import settings
from app.guards.pandas_validator import validate_pandas_code

_WORKER = Path(__file__).resolve().parent / "_pandas_worker.py"


def _json_serializer(obj: Any) -> Any:
    """Convert common Python, PostgreSQL, NumPy and Pandas values to JSON."""

    # Missing values
    if obj is None or obj is pd.NA or obj is pd.NaT:
        return None

    # Numeric values
    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        if not math.isfinite(value):
            return None
        return value

    # Boolean values (before integer-like types)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)

    # Dates and times
    if isinstance(obj, (datetime, date, datetime_time, pd.Timestamp)):
        return obj.isoformat()

    if isinstance(obj, (timedelta, pd.Timedelta)):
        return obj.total_seconds()

    # Arrays and collections
    if isinstance(obj, np.ndarray):
        return obj.tolist()

    # Identifiers and paths
    if isinstance(obj, (UUID, Path)):
        return str(obj)

    # Enums
    if isinstance(obj, Enum):
        return obj.value

    # Binary data
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")

    raise TypeError(
        f"Unsupported JSON type: {type(obj).__name__}"
    )


def _rows_of(spec: Any) -> int:
    if spec is None:
        return 0
    if isinstance(spec, list):
        return len(spec)
    return 0


def pandas_tool(
    code: str,
    df: Optional[list[dict]] = None,
    dfs: Optional[dict[str, list[dict]]] = None,
    timeout_s: Optional[int] = None,
) -> dict:
    timeout_s = timeout_s or settings.pandas_timeout_s

    validation = validate_pandas_code(code)
    if not validation.ok:
        return {
            "error": {
                "code": validation.code,
                "message": validation.message,
                "hint": validation.hint,
            }
        }

    total_input_rows = _rows_of(df) + sum(
        _rows_of(v) for v in (dfs or {}).values()
    )

    if total_input_rows > settings.pandas_max_input_rows:
        return {
            "error": {
                "code": "input_too_large",
                "message": (
                    f"{total_input_rows} input rows exceeds the "
                    f"{settings.pandas_max_input_rows}-row cap"
                ),
            }
        }

    try:
        request = json.dumps(
            {"code": code, "df": df, "dfs": dfs or {}},
            default=_json_serializer,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        return {
            "error": {
                "code": "input_serialization_error",
                "message": str(exc),
            }
        }

    t0 = time.monotonic()

    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(_WORKER)],
            input=request,
            capture_output=True,
            text=True,
            timeout=timeout_s + 2,
            env={},
        )
    except subprocess.TimeoutExpired:
        return {
            "error": {
                "code": "P-09",
                "message": f"execution exceeded {timeout_s} seconds",
            }
        }

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if proc.returncode != 0 or not proc.stdout.strip():
        detail = proc.stderr.strip()[-2000:] if proc.stderr else ""
        return {
            "error": {
                "code": "P-09",
                "message": (
                    f"worker process exited with code {proc.returncode} "
                    "(resource limit or crash)"
                ),
                "detail": detail,
            }
        }

    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        return {
            "error": {
                "code": "P-10",
                "message": f"worker produced unparsable output: {exc}",
            }
        }

    if "error" in out:
        return out

    out["elapsed_ms"] = elapsed_ms
    return out
