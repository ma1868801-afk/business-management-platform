"""The top-level graph (02_architecture.md section 2): wires together everything already
built in M2-M5 into the full request flow --

    input_guard -> detect_and_translate -> router -> fan-out -> aggregator
        -> translate_back -> output_guard

See `app/graph/state.py`'s docstring for why this is a plain Python function over
`GraphState`, exactly like the M4 subgraphs, rather than a compiled `StateGraph` (it isn't
a `langgraph` installability issue -- that was checked directly, see
`RAG_REFACTOR_REPORT.md` section 8). A real `StateGraph` wiring would call these same node
functions as its nodes without changing them, and this module was itself verified for real
against a live Postgres database, a live Chroma server, and a real `uvicorn` process (same
section) -- just not through that alternative composition.

Every step that genuinely needs the LLM (the router's classification, translation, and the
subgraphs' SQL/Pandas generation) is dependency-injected, following the one pattern used
throughout this build: production wires a real `GroqClient`-backed closure (the module-level
defaults below, or each node module's own default), and callers that have no LLM -- or
tests -- inject a stub or omit it and get the documented degraded-but-honest fallback.

Guard-blocked requests (`input_guard` outcomes `empty`/`too_long`/`unsupported_language`/
`injection_high`) are answered directly from the guard's own fixed bilingual templates and
never reach `translate_back` or `output_guard`: section 4.2 is explicit that "no model is
called, so an attacker cannot influence the wording of a guard response," and those two
later nodes exist to check *model output*, which a fixed string was never at risk of being.
"""
from __future__ import annotations

from typing import Callable, Optional

from app.config import settings as default_settings
from app.graph.aggregator import run_aggregator
from app.graph.data_analysis import run_data_analysis_subgraph
from app.graph.inventory import run_inventory_subgraph
from app.graph.knowledge_base import run_knowledge_base_subgraph
from app.graph.router import run_router
from app.graph.state import GraphState, trace_event
from app.graph.translate import run_detect_and_translate, run_translate_back
from app.guards.input_guard import input_guard, rescreen_english
from app.guards.output_guard import output_guard
from app.llm.client import GroqClient
from app.rag.embeddings import Embedder
from app.rag.entities import extract_pattern_entities
from app.rag.reranker import CrossEncoderReranker
from app.rag.store import VectorStore
from app.tools.postgres_tool import postgres_tool


def _default_reorder_context_fetcher(postgres_executor: Callable[[str, int], dict]):
    """A reasonable default for the forecast path's reorder-advice SQL (INV-04/INV-05's
    "stock/supplier facts" join), built from the same tables and shape used throughout
    `04_regression_input_guidelines.md`'s worked examples and `tests/test_inventory_subgraph.py`.
    Only fires when the router's hints ask for reorder advice and the caller supplies no
    override; it needs `entity["sku"]` and is skipped (with a warning) for any entity shape
    that doesn't carry one, e.g. a line- or company-level forecast."""
    def fetch(entity: dict) -> Optional[dict]:
        sku = entity.get("sku")
        if not sku:
            return None
        safe_sku = sku.replace("'", "")
        sql = (
            "SELECT il.quantity_available, il.reorder_point, il.safety_stock, il.reorder_quantity, "
            "s.lead_time_days, "
            "COALESCE((SELECT SUM(poi.quantity_ordered - poi.quantity_received) "
            "FROM purchase_order_items poi JOIN purchase_orders po ON po.po_id = poi.po_id "
            "WHERE poi.product_id = p.product_id AND po.status IN ('Open','In Transit')), 0) AS qty_on_order, "
            "p.lifecycle_status, p.shelf_life_days "
            "FROM products p "
            "JOIN inventory_levels il ON il.product_id = p.product_id "
            "AND il.branch_id = (SELECT branch_id FROM branches WHERE branch_code='RYD-DC') "
            "JOIN suppliers s ON s.supplier_id = p.supplier_id "
            f"WHERE p.sku = '{safe_sku}' LIMIT 1;"
        )
        out = postgres_executor(sql, 10)
        if "error" in out or not out["rows"]:
            return None
        row = dict(zip(out["columns"], out["rows"][0]))
        try:
            return {
                "available_stock": float(row["quantity_available"]),
                "reorder_point": float(row["reorder_point"]),
                "safety_stock": float(row["safety_stock"]),
                "min_order_quantity": float(row["reorder_quantity"]),
                "lead_time_days": float(row["lead_time_days"]),
                "quantity_on_order": float(row["qty_on_order"]),
                "lifecycle_status": row["lifecycle_status"],
                "shelf_life_days": int(row["shelf_life_days"]) if row["shelf_life_days"] else None,
            }
        except (KeyError, TypeError, ValueError):
            return None
    return fetch


def _resolve_entity_default(sub_question: str, hints: dict) -> dict:
    """A deterministic fallback entity resolver: `hints["entity"]` (the router's own
    schema, extended per `router.py`'s docstring) wins when present; otherwise a SKU/
    category code pattern-matched out of the sub-question text stands in for the LLM-driven
    entity resolution plan step that `inventory.py`'s own docstring says production needs.
    This covers the common case (a question that names a SKU); anything subtler (a product
    name with no code at all) needs the real plan step and is out of scope here."""
    if isinstance(hints.get("entity"), dict):
        explicit = {k: v for k, v in hints["entity"].items() if v is not None and str(v).strip()}
        if explicit:
            return explicit
    codes = extract_pattern_entities(sub_question)
    skus = [c for c in codes if "-" in c and c.split("-")[0].isalpha() and c.split("-")[0].isupper() and len(c.split("-")[0]) <= 6 and c.split("-")[-1].isdigit()]
    if skus:
        return {"sku": skus[0]}
    return {}


def _guard_blocked_state(session_id: str, user_text: str, guard, settings) -> GraphState:
    language = guard.language or "en"
    outcome_to_route = {
        "empty": {"decision": "direct", "reason": "input guard outcome=empty"},
        "too_long": {"decision": "direct", "reason": "input guard outcome=too_long"},
        "unsupported_language": {"decision": "direct", "reason": "input guard outcome=unsupported_language"},
        "injection_high": {"decision": "reject", "reject_reason": "prompt_injection", "reason": "input guard high-confidence injection match"},
    }
    route = dict(outcome_to_route[guard.outcome])
    route.setdefault("subgraphs", [])
    route.setdefault("reject_reason", None)
    route.setdefault("clarification_question", None)

    if guard.outcome == "unsupported_language":
        answer_final = guard.response["en"] + " / " + guard.response["ar"]
    else:
        answer_final = guard.response["ar"] if language == "ar" else guard.response["en"]

    return GraphState(
        session_id=session_id, user_text=user_text, user_language=language, question_en="",
        guard=guard.to_dict(), route=route, node_responses=[],
        answer_en=guard.response["en"], answer_final=answer_final,
        trace=[trace_event("input_guard", outcome=guard.outcome, allowed=False, matched_rules=guard.matched_rules)],
    )


def run_top_level_graph(
    user_text: str,
    *,
    session_id: str,
    store: VectorStore,
    embedder: Embedder,
    reranker: CrossEncoderReranker,
    llm: GroqClient,
    settings=default_settings,
    history: Optional[list[dict]] = None,
    previous_language: Optional[str] = None,
    translator=None,
    back_translator=None,
    route_decider=None,
    sql_generator=None,
    pandas_generator=None,
    answer_composer_da=None,
    inv_sql_generator=None,
    reorder_context_fetcher=None,
    answer_composer_agg=None,
    postgres_executor: Callable[[str, int], dict] = postgres_tool,
) -> GraphState:
    trace: list[dict] = []

    guard = input_guard(user_text, max_chars=settings.max_input_chars)
    if not guard.allowed:
        return _guard_blocked_state(session_id, user_text, guard, settings)
    trace.append(trace_event("input_guard", outcome=guard.outcome, allowed=True, flags=guard.flags))

    language, question_en, translate_warnings = run_detect_and_translate(
        guard.normalized_text, llm=llm, history=history, previous_language=previous_language, translator=translator,
    )
    trace.append(trace_event("detect_and_translate", language=language, translated=question_en is not None, warnings=translate_warnings))

    node_responses: list[dict] = []
    if question_en is None:
        decision = {
            "decision": "direct", "subgraphs": [], "reject_reason": None, "clarification_question": None,
            "direct_answer": (
                "I can't process Arabic messages right now because translation is unavailable. "
                "Please ask in English, or try again later."
            ),
            "reason": "translation unavailable (no LLM client)",
        }
    else:
        blocked_second, high_matches = rescreen_english(question_en)
        if blocked_second:
            decision = {
                "decision": "reject", "subgraphs": [], "reject_reason": "prompt_injection",
                "clarification_question": None,
                "reason": f"second-pass injection screen on question_en matched {high_matches}",
            }
            trace.append(trace_event("input_guard.second_pass", blocked=True, matched_rules=high_matches))
        else:
            decision, router_trace = run_router(
                question_en, store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
                flags=guard.flags, injection_level=("medium" if guard.outcome == "pass_flagged" else "low"),
                route_decider=route_decider,
            )
            trace.extend(router_trace)

            if decision.get("decision") == "route":
                for sg in decision.get("subgraphs", []):
                    name, sub_q, hints = sg["name"], sg["sub_question"], (sg.get("hints") or {})
                    if name == "data_analysis":
                        da_kwargs = {}
                        if answer_composer_da is not None:
                            da_kwargs["answer_composer"] = answer_composer_da
                        resp, sub_trace = run_data_analysis_subgraph(
                            sub_q, hints, store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
                            sql_generator=sql_generator, pandas_generator=pandas_generator,
                            postgres_executor=postgres_executor, **da_kwargs,
                        )
                    elif name == "inventory":
                        entity = _resolve_entity_default(sub_q, hints)
                        rc_fetcher = reorder_context_fetcher or _default_reorder_context_fetcher(postgres_executor)
                        resp, sub_trace = run_inventory_subgraph(
                            sub_q, hints, entity, store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
                            sql_generator=inv_sql_generator, postgres_executor=postgres_executor,
                            reorder_context_fetcher=rc_fetcher,
                        )
                    elif name == "knowledge_base":
                        resp, sub_trace = run_knowledge_base_subgraph(
                            sub_q, store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
                        )
                    else:  # pragma: no cover - validate_route_decision already rejects unknown names
                        continue
                    node_responses.append(resp)
                    trace.extend(sub_trace)

    answer_en, agg_warnings = run_aggregator(decision, node_responses, answer_composer=answer_composer_agg)
    trace.append(trace_event("aggregator", decision=decision.get("decision"), warnings=agg_warnings))

    answer_final, tb_warnings = run_translate_back(answer_en, language, llm=llm, back_translator=back_translator)
    trace.append(trace_event("translate_back", warnings=tb_warnings))

    guard_result = output_guard(
        answer_final, node_responses=node_responses, question_en=question_en or "", expected_lang=language,
        settings=settings, english_fallback=answer_en,
    )
    trace.append(trace_event("output_guard", blocked=guard_result.blocked, warnings=guard_result.warnings))

    return GraphState(
        session_id=session_id, user_text=user_text, user_language=language, question_en=question_en or "",
        guard=guard.to_dict(), route=decision, node_responses=node_responses,
        answer_en=answer_en, answer_final=guard_result.text, trace=trace,
    )
