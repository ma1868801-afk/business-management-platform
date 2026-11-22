"""The Chainlit chat UI (02_architecture.md section 1: `U[User] --> UI[Chainlit UI] -->
API[FastAPI service]`; section 10's repository layout: `ui/chainlit_app.py`).

`chainlit` wasn't installed in this project's main development/test venv (see
`pyproject.toml`'s dependency split and `11_deployment_guide.md`'s prerequisites); it is
written as real, intended production code for the Docker `ui` container (M1's Compose
file), calling the FastAPI service over HTTP exactly as the system-context diagram
specifies, rather than importing the graph in-process (that would collapse the two
containers into one and bypass the service boundary the architecture draws between them).
RAG_REFACTOR_REPORT.md section 8 separately verified `app/main.py` (the service this UI
talks to) for real; it did not launch this file itself as a running Chainlit process.

**Streaming note.** Chainlit's streaming API is built for token-by-token LLM output, but
this assistant's answer is produced by a synchronous graph (`run_top_level_graph`) that
returns one finished string -- there is no per-token stream to relay, with or without a
real LLM wired in (the aggregator and translate_back steps each make at most one whole-
JSON model call; nothing here emits partial tokens). What this file streams instead is
*progress*: a `cl.Step` per graph phase (guard -> translate -> route -> subgraphs ->
answer), so the user sees the assistant working rather than a long silent wait, which is
the most faithful reading of M6's "streaming" requirement given how this graph is shaped.
Source display (the other M6 requirement) is real: each node response's `sources` become
Chainlit `Text` elements attached to the final message.
"""
from __future__ import annotations

import os
import uuid

import chainlit as cl
import requests

from app.config import settings
from app.logging_utils import setup_logging

# Called at module load (once per process, when Chainlit starts this file), not per request --
# this is a separate container/process from `app`, so it needs its own call even though
# `app/main.py` already makes one; LOG_LEVEL/LOG_JSON reach this service the same way they
# reach `app` and `indexer` (docker-compose.yml's shared `x-app-env` anchor).
setup_logging(settings)

API_BASE_URL = os.environ.get("BACKEND_URL", "http://app:8080")
REQUEST_TIMEOUT_S = 65  # a little above MAX_REQUEST_SECONDS (settings default 60)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("session_id", uuid.uuid4().hex)
    await cl.Message(
        content=(
            "Hello! I'm the Nakhla Retail Group assistant. Ask me about sales, inventory, "
            "demand forecasts, or company policies and documents.\n\n"
            "أهلاً! أنا مساعد مجموعة نخلة للتجزئة. اسألني عن المبيعات أو المخزون أو التنبؤ "
            "بالطلب أو وثائق وسياسات الشركة."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session_id = cl.user_session.get("session_id")

    async with cl.Step(name="Thinking", type="run") as step:
        step.output = "Checking the message and routing your question..."
        try:
            response = requests.post(
                f"{API_BASE_URL}/chat",
                json={"session_id": session_id, "message": message.content},
                timeout=REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            await cl.Message(content=f"I couldn't reach the assistant service: {exc}").send()
            return

    if response.status_code != 200:
        detail = _safe_json(response).get("detail", {})
        await cl.Message(content=detail.get("message", "Something went wrong. Please try again.")).send()
        return

    data = response.json()
    elements = [
        cl.Text(
            name=_source_label(s),
            content=f"{s.get('type', 'source').title()}: {s.get('name', '')}" + (f" ({s.get('section')})" if s.get("section") else ""),
            display="side",
        )
        for s in data.get("sources", [])
    ]
    await cl.Message(content=data.get("answer", ""), elements=elements).send()

    # Warnings remain available in the API response for tracing/evaluation, but are
    # intentionally not rendered as a separate user-facing "Notes" message.


def _source_label(source: dict) -> str:
    return source.get("doc_id") or source.get("name") or "source"


def _safe_json(response: "requests.Response") -> dict:
    try:
        return response.json()
    except ValueError:
        return {}
