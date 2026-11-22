"""Exercises `app/api_core.py`'s `ChatService` against the real, live Phase 2 database and
the real RAG index -- the FastAPI-free core of M6's service layer (see that module's
docstring for why `app/main.py` itself can't be imported or tested here: `fastapi` is not
installable in this sandbox). Covers a normal chat turn end to end (including that history
is recorded and fed back on the next turn), the rate limit (section 4.4: 20/minute), the
concurrency limit (1 at a time per session), and the request-timeout watchdog (section 8:
60 seconds, here exercised with a deliberately slow stubbed route_decider and a tiny
`MAX_REQUEST_SECONDS` override).

Requires the Phase 2 test cluster running at /tmp/pgsock:54329 (see database/README.md).
"""
from __future__ import annotations

import dataclasses
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.api_core import ChatService, _build_response  # noqa: E402
from app.config import settings  # noqa: E402
from app.llm.client import GroqClient  # noqa: E402
from app.rag.embeddings import Embedder  # noqa: E402
from app.rag.indexer import run_indexer  # noqa: E402
from app.rag.reranker import CrossEncoderReranker  # noqa: E402
from app.sessions import SessionStore  # noqa: E402
from psql_executor import psql_postgres_tool  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def _route_to_da(question_en, passages, prior_error):
    return {
        "decision": "route",
        "subgraphs": [{"name": "data_analysis", "sub_question": question_en, "hints": {"needs_computation": False}}],
        "reject_reason": None, "clarification_question": None, "reason": "revenue question",
    }


def _monthly_revenue_sql(question, passages, prior_error):
    return (
        "SELECT date_trunc('month', order_date)::date AS order_month, "
        "ROUND(SUM(line_total), 2) AS net_revenue_sar FROM v_sales_detail "
        "WHERE status = 'Completed' AND order_date BETWEEN DATE '2024-01-01' AND DATE '2026-10-31' "
        "GROUP BY 1 ORDER BY 1 LIMIT 500;"
    )


def main() -> int:
    report, store = run_indexer(ROOT / "rag_sources")
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

    def build_service(**overrides):
        return ChatService(
            store=store, embedder=embedder, reranker=reranker, llm=llm, settings=overrides.pop("settings", settings),
            sessions=SessionStore(), route_decider=_route_to_da, sql_generator=_monthly_revenue_sql, **overrides,
        )

    # ChatService doesn't expose `postgres_executor` (psycopg isn't installable here, so
    # `postgres_tool`'s real default would always fail with driver_unavailable); shim
    # `run_top_level_graph` as api_core calls it so every subgraph call goes through the
    # `psql`-based stand-in instead, exactly as every other integration test in this suite does.
    import app.api_core as api_core_mod
    import app.graph.top_level as top_level_mod

    def _patched_run_top_level_graph(message, **kwargs):
        kwargs["postgres_executor"] = psql_postgres_tool
        return top_level_mod.run_top_level_graph(message, **kwargs)

    api_core_mod.run_top_level_graph = _patched_run_top_level_graph

    service = build_service()

    # 1. A normal chat turn.
    result = service.handle_chat("session-A", "What is the monthly net revenue trend?")
    check("a normal chat turn returns no error", "error" not in result, result)
    check("the response carries a session id, trace id and English language", result.get("session_id") == "session-A" and result.get("trace_id") and result.get("language") == "en")
    check("the response status reflects the one ok subgraph", result.get("status") == "ok", result)

    # 2. History is recorded and fed back on the next turn.
    session_state = service.sessions.get_or_create("session-A")
    check("the turn was recorded into session history", len(session_state.history) == 2 and session_state.history[0]["role"] == "user")
    check("the assistant's stored answer is truncated to history_answer_chars", len(session_state.history[1]["text"]) <= settings.history_answer_chars)

    # 3. Empty message is rejected before touching the graph.
    empty_result = service.handle_chat("session-A", "   ")
    check("an empty message is rejected with empty_message", empty_result.get("error", {}).get("code") == "empty_message")

    # 4. Rate limiting (20/minute, section 4.4): hammer a fresh session past the limit.
    fast_settings = dataclasses.replace(settings, rate_limit_per_minute=3)
    limited_service = build_service(settings=fast_settings)
    codes = []
    for _ in range(5):
        r = limited_service.handle_chat("session-C", "What is the monthly net revenue trend?")
        codes.append(r.get("error", {}).get("code"))
    check("the 4th and 5th calls within a minute are rate-limited", codes[3] == "rate_limited" and codes[4] == "rate_limited", codes)
    check("the first 3 calls within the limit succeed", codes[0] is None and codes[1] is None and codes[2] is None, codes)

    # 5. Concurrency limit: a second call for the same session while the first is "in
    #    flight" is rejected immediately. Simulated by holding the session lock directly
    #    (holding it via a slow stub would need a real thread race; the lock itself is the
    #    unit under test, and handle_chat's own acquire/release around it is exercised by
    #    every other case above succeeding).
    conc_service = build_service()
    session_c = conc_service.sessions.get_or_create("session-D")
    session_c.lock.acquire()
    try:
        r = conc_service.handle_chat("session-D", "What is the monthly net revenue trend?")
        check("a concurrent request for a locked session is rejected", r.get("error", {}).get("code") == "concurrent_request", r)
    finally:
        session_c.lock.release()

    # 6. Request timeout watchdog (section 8/14): a stub route_decider that sleeps past a
    #    tiny MAX_REQUEST_SECONDS override triggers the timeout path, not a hang.
    def _slow_decider(question_en, passages, prior_error):
        time.sleep(1.5)
        return _route_to_da(question_en, passages, prior_error)

    timeout_settings = dataclasses.replace(settings, max_request_seconds=1)
    timeout_service = ChatService(
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=timeout_settings,
        sessions=SessionStore(), route_decider=_slow_decider, sql_generator=_monthly_revenue_sql,
    )
    t0 = time.monotonic()
    r = timeout_service.handle_chat("session-E", "What is the monthly net revenue trend?")
    elapsed = time.monotonic() - t0
    check("a slow request is stopped at MAX_REQUEST_SECONDS with a timeout error, not a hang",
          r.get("error", {}).get("code") == "timeout" and elapsed < 1.4, (r, elapsed))

    # 7. _build_response shape, directly, against a hand-built minimal state.
    sample_state = {
        "session_id": "x", "user_language": "en", "answer_final": "Net revenue was SAR 100.",
        "route": {"decision": "route", "subgraphs": [{"name": "data_analysis"}]},
        "node_responses": [{
            "subgraph": "data_analysis", "status": "ok", "answer_en": "Net revenue was SAR 100.",
            "key_figures": [{"label": "net_revenue", "value": 100.0, "unit": "SAR"}],
            "sources": [{"type": "table", "name": "v_sales_detail"}], "warnings": ["a note"],
        }],
    }
    built = _build_response(sample_state, "trace-1")
    check("_build_response surfaces sources, key_figures and warnings", built["sources"] and built["key_figures"] and built["warnings"] == ["a note"], built)
    check("_build_response's route summary lists subgraph names only", built["route"]["subgraphs"] == ["data_analysis"])

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
