"""The FastAPI service (02_architecture.md section 10's repository layout, section 1's
system context: `UI[Chainlit UI] --> API[FastAPI service] --> G[LangGraph application]`).

This module is a thin translation of `app/api_core.py`'s `ChatService` into HTTP routes:
every piece of actual logic (sessions, rate limiting, the request timeout, the response
shape) lives there and is unit-tested in `tests/test_api_core.py`. `fastapi` wasn't
installed in this project's main development/test venv (see `pyproject.toml`'s dependency
split and `11_deployment_guide.md`'s prerequisites); RAG_REFACTOR_REPORT.md section 8
separately verified this module for real -- a live `uvicorn app.main:app` process, a real
`/healthz` check, and a real `/chat` call against the actual LangGraph pipeline, real
Postgres, and a real Chroma server with real indexed data (no Groq key in that run, so it
exercised the documented degraded-LLM path rather than real generation -- see that
section for what a real Groq key would additionally verify).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.api_core import HTTP_STATUS_BY_ERROR_CODE, ChatService, build_default_chat_service
from app.config import settings
from app.logging_utils import setup_logging

_service: ChatService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service
    setup_logging(settings)
    _service = build_default_chat_service(settings)
    yield
    _service = None


app = FastAPI(
    title="Nakhla Retail Group Assistant",
    description="Business analytics, forecasting and company knowledge-base assistant.",
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class SourceOut(BaseModel):
    type: str
    name: str
    doc_id: str | None = None
    section: str | None = None


class KeyFigureOut(BaseModel):
    label: str
    value: float
    unit: str | None = None
    subgraph: str | None = None


class RouteOut(BaseModel):
    decision: str | None
    subgraphs: list[str]
    reject_reason: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    trace_id: str
    language: str
    answer: str
    route: RouteOut
    sources: list[SourceOut]
    key_figures: list[KeyFigureOut]
    warnings: list[str]
    status: str


@app.get("/healthz")
def healthz() -> dict:
    """Liveness/readiness probe (Docker Compose health check, M1)."""
    return {"status": "ok", "ready": _service is not None}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> dict:
    if _service is None:
        raise HTTPException(status_code=503, detail={"code": "not_ready", "message": "The assistant is still starting up."})
    result = _service.handle_chat(req.session_id, req.message)
    if "error" in result:
        code = result["error"]["code"]
        status_code = HTTP_STATUS_BY_ERROR_CODE.get(code, 400)
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@app.post("/sessions/{session_id}/reset")
def reset_session(session_id: str) -> dict:
    if _service is not None:
        _service.sessions.reset(session_id)
    return {"status": "ok"}
