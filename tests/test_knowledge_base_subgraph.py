"""Tests app/graph/knowledge_base.py and app/graph/citation_check.py end to end against the
real corpus: grounded answers, the restricted-compensation refusal, the off-corpus gate
(the fallback relevance scoring added in app/rag/pipeline.py specifically so a question with
no connection to the corpus is not answered confidently), and the deterministic citation
check in isolation.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.graph.citation_check import check_sentence, citation_check  # noqa: E402
from app.graph.knowledge_base import run_knowledge_base_subgraph  # noqa: E402
from app.llm.client import GroqClient  # noqa: E402
from app.rag.embeddings import Embedder  # noqa: E402
from app.rag.indexer import run_indexer  # noqa: E402
from app.rag.reranker import CrossEncoderReranker  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def main() -> int:
    # Citation check in isolation: a sentence whose numbers/dates are not in the passages is
    # rejected; one that is grounded passes.
    passages = [{"chunk_id": "KB-POL-09#01", "text": "Customers may return an item within 14 days of the order date."}]
    ok, missing = check_sentence("Customers may return an item within 14 days of the order date.", passages)
    check("grounded sentence passes the citation check", ok, str(missing))
    ok2, missing2 = check_sentence("Customers may return an item within 90 days of the order date.", passages)
    check("a fabricated number fails the citation check", not ok2, str(missing2))

    answer, warnings = citation_check(
        "Customers may return an item within 14 days of the order date. The refund is issued within 45 business days.",
        passages,
    )
    check("citation_check drops the unsupported sentence and keeps the grounded one",
          "14 days" in answer and "45 business days" not in answer, answer)
    check("citation_check records a warning for the dropped sentence", len(warnings) == 1)

    report, store = run_indexer(ROOT / "rag_sources")
    check("index build ok", report.ok)
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

    resp, _ = run_knowledge_base_subgraph(
        "What is the return window for defective items?",
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
    )
    check("KB subgraph answers a grounded question with status ok", resp["status"] == "ok", resp)
    check("KB subgraph cites KB-POL-09", any(s["doc_id"] == "KB-POL-09" for s in resp["sources"]), resp["sources"])

    resp2, _ = run_knowledge_base_subgraph(
        "What is the monthly salary of every employee, ranked from highest to lowest?",
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
    )
    check("KB subgraph refuses an aggregate compensation request", resp2["status"] == "failed" and resp2["error"]["code"] == "restricted_data", resp2)

    resp3, _ = run_knowledge_base_subgraph(
        "What is the capital of France?",
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
    )
    check("KB subgraph does not fabricate an answer to an off-corpus question",
          resp3["sources"] == [] and "do not contain" in resp3["answer_en"], resp3)

    resp4, _ = run_knowledge_base_subgraph(
        "What is the hire date and department of EMP-0001?",
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
    )
    check("KB subgraph answers a single-named-employee question (not blocked by the restricted-data rule)",
          resp4["status"] == "ok" and resp4["sources"], resp4)

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
