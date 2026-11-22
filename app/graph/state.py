"""Shared state and the common node response (02_architecture.md sections 2 and 5).

`GraphState` is written as a `TypedDict` exactly as specified. `langgraph` is in fact
installable (confirmed directly in this development sandbox -- see
RAG_REFACTOR_REPORT.md section 8), so its absence isn't why the subgraphs in this package
run their control flow as plain Python functions over this same state shape rather than a
compiled `StateGraph`: no `app/graph/runtime.py` doing that wiring exists in this delivery
either way, and building one is a separate, substantial piece of work -- replacing this
package's working, tested control flow with a compiled `StateGraph` -- that nothing in this
delivery's scope asked for or depends on (the node functions would not need to change, only
how they're composed). `RAG_REFACTOR_REPORT.md` section 7 lists this as a known gap between
the architecture docs' original intent and what's actually implemented, left as-is rather
than taken on opportunistically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict

Status = Literal["ok", "partial", "failed"]


class GraphState(TypedDict, total=False):
    session_id: str
    user_text: str
    user_language: str
    question_en: str
    guard: dict
    route: dict
    node_responses: list[dict]
    answer_en: str
    answer_final: str
    trace: list[dict]


@dataclass
class KeyFigure:
    label: str
    value: float
    unit: Optional[str] = None


@dataclass
class Method:
    tools_used: list[str] = field(default_factory=list)
    bypassed: list[str] = field(default_factory=list)
    queries: int = 0


@dataclass
class Source:
    type: str  # "table" | "document"
    name: str
    doc_id: Optional[str] = None
    section: Optional[str] = None


@dataclass
class NodeResponse:
    """02_architecture.md section 5. `to_dict()` is the exact wire shape the aggregator
    consumes."""
    subgraph: str
    status: Status
    answer_en: str
    key_figures: list[KeyFigure] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    method: Method = field(default_factory=Method)
    sources: list[Source] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "subgraph": self.subgraph,
            "status": self.status,
            "answer_en": self.answer_en,
            "key_figures": [vars(k) for k in self.key_figures],
            "assumptions": self.assumptions,
            "method": vars(self.method),
            "sources": [vars(s) for s in self.sources],
            "warnings": self.warnings,
            "error": self.error,
        }


def trace_event(node: str, **fields: Any) -> dict:
    """One entry for `GraphState["trace"]` (section 9: "node timings, retrieved document
    ids, validated SQL, tool errors and retry counts")."""
    return {"node": node, **fields}
