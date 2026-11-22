"""The FastAPI service's request-handling logic, kept free of any FastAPI import.

`fastapi` wasn't installed in this project's main development/test venv (`tests/test_api_core.py`
is written to not need it, so this module has real test coverage independent of that);
`app/main.py` is the real production FastAPI app, and was itself verified for real in this
delivery's RAG-reliability pass -- a live `uvicorn app.main:app` process, hit with real
`/healthz` and `/chat` requests against a live Postgres database and a live Chroma server
(see RAG_REFACTOR_REPORT.md section 8). Every piece of logic that is *not* HTTP plumbing --
sessions, the request-rate and concurrency limits of section 4.4, the request-timeout
watchdog of section 8/14, building the public response shape, mapping internal error codes
to what an HTTP layer would use as a status code -- lives in this plain module, with its own
dedicated test file. `app/main.py` is then a thin, line-for-line translation of this
module's `ChatService` into FastAPI routes.
"""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.config import settings as default_settings
from app.graph.top_level import run_top_level_graph
from app.llm.client import GroqClient
from app.rag.embeddings import Embedder
from app.rag.indexer import run_indexer
from app.rag.reranker import CrossEncoderReranker
from app.rag.store import VectorStore
from app.sessions import SessionStore, now_seconds

# Maps this module's internal error codes to the HTTP status an API layer should use.
HTTP_STATUS_BY_ERROR_CODE = {
    "rate_limited": 429,
    "concurrent_request": 429,
    "timeout": 504,
    "empty_message": 400,
}


@dataclass
class ChatService:
    store: VectorStore
    embedder: Embedder
    reranker: CrossEncoderReranker
    llm: GroqClient
    settings: object
    sessions: SessionStore
    route_decider: Optional[Callable] = None
    sql_generator: Optional[Callable] = None
    pandas_generator: Optional[Callable] = None
    inv_sql_generator: Optional[Callable] = None
    reorder_context_fetcher: Optional[Callable] = None
    _executor: Optional[ThreadPoolExecutor] = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bmp-chat")

    def handle_chat(self, session_id: str, message: str) -> dict:
        """Returns a JSON-ready dict: either `{"error": {"code", "message"}}` (section
        4.4/14's limits, mapped via `HTTP_STATUS_BY_ERROR_CODE` by the HTTP layer) or the
        full chat response shape built by `_build_response`."""
        if not isinstance(message, str) or not message.strip():
            return {"error": {"code": "empty_message", "message": "The message must not be empty."}}

        session = self.sessions.get_or_create(session_id)

        if not session.allow_request(now_seconds(), self.settings.rate_limit_per_minute):
            return {"error": {"code": "rate_limited", "message": f"This session is limited to {self.settings.rate_limit_per_minute} requests per minute. Please wait and try again."}}

        if not session.lock.acquire(blocking=False):
            return {"error": {"code": "concurrent_request", "message": "A previous request for this session is still being processed."}}

        trace_id = uuid.uuid4().hex
        try:
            history = session.history_for_graph()
            previous_language = session.previous_language
            future = self._executor.submit(
                run_top_level_graph, message,
                session_id=session_id, store=self.store, embedder=self.embedder, reranker=self.reranker,
                llm=self.llm, settings=self.settings, history=history, previous_language=previous_language,
                route_decider=self.route_decider, sql_generator=self.sql_generator, pandas_generator=self.pandas_generator,
                inv_sql_generator=self.inv_sql_generator, reorder_context_fetcher=self.reorder_context_fetcher,
            )
            try:
                # Section 8/14: "Total request time budget: 60 seconds; partial answers are
                # returned when one subgraph exceeds its budget." The subgraphs here run as
                # plain synchronous Python (no LangGraph, no per-node cancellation -- see
                # app/graph/state.py), so this watchdog can only act at the whole-request
                # level: it returns a friendly timeout promptly rather than hanging the HTTP
                # response, but it cannot recover a partial answer from a request it gives up
                # on (the thread keeps running to completion in the background and its result
                # is discarded). That per-subgraph partial-answer behavior is real-StateGraph
                # follow-up work, documented here rather than silently approximated.
                state = future.result(timeout=self.settings.max_request_seconds)
            except FutureTimeoutError:
                return {"error": {"code": "timeout", "message": f"This request took longer than {self.settings.max_request_seconds} seconds. Please try a narrower question."}}
            session.record_turn(
                message, state["answer_final"], state["user_language"],
                max_turns=self.settings.max_history_turns, answer_chars=self.settings.history_answer_chars,
            )
            return _build_response(state, trace_id)
        finally:
            session.lock.release()


def _build_response(state: dict, trace_id: str) -> dict:
    """The public response shape: enough for Chainlit to render the answer plus a source
    list and key figures (02_architecture.md section 10: "source display"), and enough for
    the evaluation harness (06_evaluation_plan.md section 8.2) to read the routing decision
    and node responses without exposing the full internal trace (SQL text, retrieved chunk
    ids) to an ordinary client."""
    node_responses = state.get("node_responses") or []
    sources, key_figures, warnings = [], [], []
    for node in node_responses:
        for s in node.get("sources") or []:
            if s not in sources:
                sources.append(s)
        for kf in node.get("key_figures") or []:
            key_figures.append({**kf, "subgraph": node.get("subgraph")})
        warnings.extend(node.get("warnings") or [])

    route = state.get("route") or {}
    return {
        "session_id": state.get("session_id"),
        "trace_id": trace_id,
        "language": state.get("user_language"),
        "answer": state.get("answer_final"),
        "route": {
            "decision": route.get("decision"),
            "subgraphs": [sg.get("name") for sg in (route.get("subgraphs") or [])],
            "reject_reason": route.get("reject_reason"),
        },
        "sources": sources,
        "key_figures": key_figures,
        "warnings": warnings,
        "status": _overall_status(node_responses),
    }


def _overall_status(node_responses: list[dict]) -> str:
    if not node_responses:
        return "ok"
    statuses = {n.get("status") for n in node_responses}
    if statuses == {"ok"}:
        return "ok"
    if "ok" in statuses or "partial" in statuses:
        return "partial"
    return "failed"


def build_default_chat_service(settings=default_settings) -> ChatService:
    """Builds the shared, process-wide `ChatService` the real `app/main.py` constructs once
    at startup (rebuilding the RAG index and the embedder/reranker/LLM per request would be
    far too slow -- the indexer alone touches all 105 corpus documents)."""
    report, store = run_indexer(settings.rag_sources_dir)
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)
    return ChatService(
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings, sessions=SessionStore(),
    )
