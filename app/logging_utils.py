"""Observability (adapted from the TechNova reference's `src/logging_utils.py`).

BMP already has a per-request structured trace (`app/graph/state.py`'s `trace_event`,
threaded through every subgraph into `node_responses`/`trace`) that records *what* each
node did -- passage ids, timings, warnings -- for a single conversation turn. That stays
as-is; it is a richer per-turn record than a log line and nothing here replaces it.

What was missing, and what this module adds, is process-level observability that the trace
can't carry: structured log lines (to stdout, JSON by default) for things that happen
*around* a request -- LLM transport failures and retries (see `app/llm/client.py`), startup,
and anything else a node wants to record outside the trace. `setup_logging()` configures the
root "bmp" logger once at process startup (see `app/main.py` / `ui/chainlit_app.py`);
`log_event` and `stage_timer` are convenience helpers for structured, leveled log lines.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def setup_logging(settings=None) -> None:
    """Idempotent: safe to call from more than one entry point (API, UI, CLI)."""
    global _configured
    if _configured:
        return
    if settings is None:
        from app.config import settings as _settings

        settings = _settings

    root = logging.getLogger("bmp")
    root.setLevel(settings.log_level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra={"extra_fields": fields})


@contextmanager
def stage_timer(logger: logging.Logger, stage: str, **fields: Any) -> Iterator[dict]:
    """Usage:

        with stage_timer(logger, "rag_tool", session_id=session_id) as ctx:
            ...
            ctx["passage_count"] = len(passages)   # add fields mid-stage

    Logs one structured "stage_complete" event on exit with duration_ms and every field
    collected, or "stage_failed" (still with duration_ms) if the block raises -- the
    exception is re-raised unchanged either way.
    """
    ctx: dict[str, Any] = {}
    start = time.perf_counter()
    try:
        yield ctx
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        log_event(logger, "stage_failed", stage=stage, duration_ms=duration_ms, error=str(exc), **fields, **ctx)
        raise
    else:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        log_event(logger, "stage_complete", stage=stage, duration_ms=duration_ms, **fields, **ctx)
