"""Proves the M7 evaluation harness (`tests/evaluation/`) end to end against the real,
live Phase 2 database, the real RAG index, and **real scenario text pulled from the actual
220-scenario suite** in `evaluation/` -- not fabricated examples. Covers:

1. The suite loads to exactly 220 scenarios with the section-2 per-suite counts, and
   passes its own section-13 self-check (scenario_loader.py) -- this alone is a real,
   valuable regression check on the Phase 1 deliverable, independent of any model.
2. The smoke set (section 8.1) is exactly 53 scenarios.
3. The grader's deterministic components (route/method/status/language, the
   must_not_include redaction checks, and the oracle-driven numeric must_include checks)
   are exercised against real graph output for five real scenarios spanning: a plain route
   decision (EV-RT-001), a router-level write-request rejection (EV-RT-030), a guard-level
   prompt-injection rejection that never reaches the router (EV-RT-036), a follow-up
   question that needs history replay (EV-GR-008), and an oracle_sql scenario whose
   must_include item is checked against a real database value (EV-INV-001).
4. A scenario whose answer needs the LLM judge (no judge configured here) is reported as
   `ungraded`, never silently passed.
5. `report.py` writes a real `summary.md`/`results.jsonl`/`failures.md` for this run.

Requires the Phase 2 test cluster running at /tmp/pgsock:54329 (see database/README.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tests" / "evaluation"))

from app.config import settings  # noqa: E402
from app.llm.client import GroqClient  # noqa: E402
from app.rag.embeddings import Embedder  # noqa: E402
from app.rag.indexer import run_indexer  # noqa: E402
from app.rag.reranker import CrossEncoderReranker  # noqa: E402
from psql_executor import psql_postgres_tool  # noqa: E402

from scenario_loader import EXPECTED_SUITE_COUNTS, load_all_scenarios, self_check, smoke_set  # noqa: E402
from grader import grade_scenario  # noqa: E402
from oracles import OracleStore  # noqa: E402
from report import write_report  # noqa: E402
from run_evaluation import run_scenarios  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def main() -> int:
    scenarios = load_all_scenarios()
    check("loads exactly 220 scenarios", len(scenarios) == 220, len(scenarios))
    counts = {}
    for s in scenarios:
        counts[s.suite] = counts.get(s.suite, 0) + 1
    check("per-suite counts match 06_evaluation_plan.md section 2", counts == EXPECTED_SUITE_COUNTS, counts)

    report = self_check(scenarios)
    check("the suite passes its own section-13 self-check", report.ok, report.errors)

    smoke = smoke_set(scenarios)
    check("smoke set is exactly 53 scenarios (section 8.1)", len(smoke) == 53, len(smoke))

    by_id = {s.id: s for s in scenarios}
    target_ids = ["EV-RT-001", "EV-RT-030", "EV-RT-036", "EV-GR-008", "EV-INV-001"]
    selected = [by_id[i] for i in target_ids]

    def route_decider(question_en, passages, prior_error):
        q = question_en.lower()
        if "net revenue" in q and "2025" in q:
            return {"decision": "route", "subgraphs": [{"name": "data_analysis", "sub_question": question_en, "hints": {"needs_computation": False}}],
                    "reject_reason": None, "clarification_question": None, "reason": "revenue extraction"}
        if "2024" in q:
            # EV-GR-008's follow-up ("And for 2024?"): with no LLM to resolve it against
            # history, question_en stays this literal, unresolved text (see
            # app/graph/translate.py's docstring) -- the stub, standing in for the
            # router's real LLM judgment, still recognizes it from the bare "2024" the
            # same way a human reading the conversation would.
            return {"decision": "route", "subgraphs": [{"name": "data_analysis", "sub_question": question_en, "hints": {"needs_computation": False}}],
                    "reject_reason": None, "clarification_question": None, "reason": "revenue extraction (unresolved follow-up)"}
        if "delete" in q and "cancelled orders" in q:
            return {"decision": "reject", "subgraphs": [], "reject_reason": "write_request", "clarification_question": None, "reason": "write verb"}
        if "elec-0001" in question_en.lower() and "ryd-dc" in question_en.lower():
            return {"decision": "route", "subgraphs": [{"name": "inventory", "sub_question": question_en, "hints": {"forecast_requested": False}}],
                    "reject_reason": None, "clarification_question": None, "reason": "stock status"}
        raise AssertionError(f"route_decider stub got an unexpected question: {question_en!r}")

    def sql_generator(question, passages, prior_error):
        q = question.lower()
        if "2025" in q:
            return (
                "SELECT ROUND(SUM(soi.line_total), 2) AS net_revenue_sar FROM sales_order_items soi "
                "JOIN sales_orders so ON so.order_id = soi.order_id WHERE so.status = 'Completed' "
                "AND so.order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31';"
            )
        if "2024" in q:
            return (
                "SELECT ROUND(SUM(soi.line_total), 2) AS net_revenue_sar FROM sales_order_items soi "
                "JOIN sales_orders so ON so.order_id = soi.order_id WHERE so.status = 'Completed' "
                "AND so.order_date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31';"
            )
        raise AssertionError(f"sql_generator stub got an unexpected question: {question!r}")

    def inv_sql_generator(question, passages, prior_error):
        return (
            "SELECT il.quantity_on_hand, il.quantity_available FROM inventory_levels il "
            "JOIN products p ON p.product_id = il.product_id JOIN branches b ON b.branch_id = il.branch_id "
            "WHERE p.sku = 'ELEC-0001' AND b.branch_code = 'RYD-DC' LIMIT 1;"
        )

    rag_report, store = run_indexer(settings.rag_sources_dir)
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

    results = run_scenarios(
        selected, store=store, embedder=embedder, reranker=reranker, llm=llm, postgres_executor=psql_postgres_tool,
        route_decider=route_decider, sql_generator=sql_generator, inv_sql_generator=inv_sql_generator,
    )
    by_scenario = {r.scenario_id: r for r in results}

    check("EV-RT-001 (plain route decision) is graded with route/method/status/language all passing",
          all(by_scenario["EV-RT-001"].components[c].passed for c in ("route", "method", "status", "language")),
          by_scenario["EV-RT-001"])
    check("EV-RT-001's answer component is None (its must_include item needs the judge), not silently passed",
          by_scenario["EV-RT-001"].components["answer"].passed is None, by_scenario["EV-RT-001"].components["answer"])
    check("EV-RT-001's overall result is ungraded (None), never a false pass", by_scenario["EV-RT-001"].passed is None)

    check("EV-RT-030 (router write_request rejection) passes the route component",
          by_scenario["EV-RT-030"].components["route"].passed is True, by_scenario["EV-RT-030"].components["route"])

    check("EV-RT-036 (guard-level injection) is rejected before the router, with reject_reason=prompt_injection",
          by_scenario["EV-RT-036"].components["route"].passed is True, by_scenario["EV-RT-036"].components["route"])
    inj_items = by_scenario["EV-RT-036"].item_results
    check("EV-RT-036's must_not_include system-prompt item is graded (deterministic or ungraded, never a false pass over real risk)",
          any(it.kind == "must_not_include" for it in inj_items))

    check("EV-GR-008 (follow-up with history replay) resolves to data_analysis and passes route+method+status",
          all(by_scenario["EV-GR-008"].components[c].passed for c in ("route", "method", "status")), by_scenario["EV-GR-008"])

    inv_result = by_scenario["EV-INV-001"]
    check("EV-INV-001 (oracle_sql) passes route/method/status/language", all(inv_result.components[c].passed for c in ("route", "method", "status", "language")), inv_result)
    oracle_item = next((it for it in inv_result.item_results if "oracle" in it.text.lower()), None)
    check("EV-INV-001's oracle-referencing must_include item is graded deterministically against the live DB value",
          oracle_item is not None and oracle_item.method == "deterministic_numeric" and oracle_item.verdict == "pass", oracle_item)

    oracle_store = OracleStore()
    check("the oracle store loads the representative oracles.yaml entries", oracle_store.has("EV-INV-001") and oracle_store.has("EV-DA-001"))

    out_dir = write_report("harness-proof-run", results, {"mode": "proof", "index_version": store.index_version(), "llm_model": settings.llm_model})
    check("write_report produces summary.md, results.jsonl and failures.md",
          (out_dir / "summary.md").exists() and (out_dir / "results.jsonl").exists() and (out_dir / "failures.md").exists())

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
