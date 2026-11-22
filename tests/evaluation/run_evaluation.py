"""The M7 harness runner (06_evaluation_plan.md section 8.2): for each selected scenario,
open a fresh session, replay `history`, send `prompt` through the graph, grade it
(`grader.py`), and write a report (`report.py`).

Every scenario is sent through `run_top_level_graph` exactly as `app/main.py`'s `/chat`
endpoint would (section 8.2 point 3 literally says "through the FastAPI endpoint"; this
calls the same underlying graph function `ChatService.handle_chat` calls, which is the
part that is actually testable here -- see `app/api_core.py`'s docstring for why the HTTP
layer itself isn't). Without a real Groq key, the router and the SQL/Pandas generators
cannot run their real, open-ended judgment, so a scenario run this way will mostly fail or
come back `llm_unavailable` -- an honest consequence of the sandbox, not a harness defect;
`route_decider`/`sql_generator`/... can be supplied (as this module's own
`tests/test_evaluation_harness.py` does, with stubs reproducing a handful of real scenarios'
expected routing) to prove the grading machinery end to end on real scenario text.
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grader import grade_scenario  # noqa: E402
from oracles import OracleStore  # noqa: E402
from report import write_report  # noqa: E402
from scenario_loader import load_all_scenarios, smoke_set  # noqa: E402

from app.config import settings  # noqa: E402
from app.graph.top_level import run_top_level_graph  # noqa: E402


def run_scenarios(scenarios, *, store, embedder, reranker, llm, postgres_executor, route_decider=None,
                   sql_generator=None, inv_sql_generator=None, judge=None) -> list:
    oracle_store = OracleStore()
    results = []
    for scenario in scenarios:
        session_id = f"eval-{uuid.uuid4().hex[:12]}"
        previous_language = None
        conversation_history: list[dict] = []  # what app/sessions.py's SessionState.history_for_graph() would hold
        final_state = None
        t0 = time.monotonic()
        try:
            for turn in scenario.history:
                turn_prompt = turn.get("prompt", "")
                final_state = run_top_level_graph(
                    turn_prompt, session_id=session_id, store=store, embedder=embedder, reranker=reranker,
                    llm=llm, settings=settings, previous_language=previous_language, history=conversation_history,
                    route_decider=route_decider, sql_generator=sql_generator, inv_sql_generator=inv_sql_generator,
                    postgres_executor=postgres_executor,
                )
                previous_language = final_state.get("user_language")
                conversation_history.append({"role": "user", "text": turn_prompt})
                conversation_history.append({"role": "assistant", "text": (final_state.get("answer_final") or "")[:settings.history_answer_chars]})
            final_state = run_top_level_graph(
                scenario.prompt, session_id=session_id, store=store, embedder=embedder, reranker=reranker, llm=llm,
                settings=settings, previous_language=previous_language, history=conversation_history,
                route_decider=route_decider, sql_generator=sql_generator, inv_sql_generator=inv_sql_generator,
                postgres_executor=postgres_executor,
            )
            elapsed = time.monotonic() - t0
            result = grade_scenario(scenario, final_state, elapsed, oracle_store=oracle_store, postgres_executor=postgres_executor, judge=judge)
        except Exception as exc:  # the harness must keep going even if one scenario errors
            elapsed = time.monotonic() - t0
            from grader import ScenarioResult
            result = ScenarioResult(scenario_id=scenario.id, suite=scenario.suite, elapsed_s=elapsed, error=f"{type(exc).__name__}: {exc}")
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the M7 evaluation harness.")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    from app.llm.client import GroqClient
    from app.rag.embeddings import Embedder
    from app.rag.indexer import run_indexer
    from app.rag.reranker import CrossEncoderReranker
    from psql_executor import psql_postgres_tool

    report, store = run_indexer(settings.rag_sources_dir)
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

    scenarios = load_all_scenarios()
    if args.mode == "smoke":
        scenarios = smoke_set(scenarios)

    results = run_scenarios(scenarios, store=store, embedder=embedder, reranker=reranker, llm=llm, postgres_executor=psql_postgres_tool)

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = write_report(run_id, results, {
        "mode": args.mode, "index_version": store.index_version(), "llm_model": settings.llm_model,
        "judge_model": None, "reference_date": str(settings.reference_date),
    })
    print(f"Wrote report to {out_dir}")
    passed = sum(1 for r in results if r.passed is True)
    print(f"{passed}/{len(results)} scenarios passed ({sum(1 for r in results if r.passed is None)} ungraded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
