"""Runs the chunker (app/rag/chunker.py) over the real 105 `rag_sources/**/*.md` files and
compares the result against the published counts in `04_rag_design.md` sections 2 and 13
(105 documents, 1,263 chunks: 76 router / 216 data_analysis / 198 inventory / 773
knowledge_base). This implementation is not the original reference chunker (not available
here), so an exact match is not expected on every document; this test reports the overall
and per-document deltas so the gap is visible rather than assumed away.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.rag.chunker import build_chunk_records, estimate_tokens  # noqa: E402

INDEX_DIRS = {
    "router": ROOT / "rag_sources" / "router",
    "data_analysis": ROOT / "rag_sources" / "data_analysis",
    "inventory": ROOT / "rag_sources" / "inventory",
    "knowledge_base": ROOT / "rag_sources" / "knowledge_base",
}
TARGET_TOTAL = {"router": 76, "data_analysis": 216, "inventory": 198, "knowledge_base": 773}


def main() -> int:
    totals = {}
    errors = []
    max_tokens = 0
    doc_count = 0
    per_doc = []
    for index_name, d in INDEX_DIRS.items():
        count = 0
        for path in sorted(d.rglob("*.md")):
            doc_count += 1
            try:
                title, header, records = build_chunk_records(path, ROOT / "rag_sources", index_name)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{path}: {type(e).__name__}: {e}")
                continue
            count += len(records)
            per_doc.append((header.doc_id, path.name, len(records)))
            for r in records:
                max_tokens = max(max_tokens, r.token_estimate)
                if r.token_estimate > 256:
                    errors.append(f"{r.chunk_id}: {r.token_estimate} tokens (over 256)")
        totals[index_name] = count

    print(f"Documents parsed: {doc_count} (target 105)")
    print("Chunks by index:")
    for k, v in totals.items():
        print(f"  {k}: {v} (target {TARGET_TOTAL[k]}, delta {v - TARGET_TOTAL[k]:+d})")
    total = sum(totals.values())
    print(f"  TOTAL: {total} (target 1263, delta {total - 1263:+d})")
    print(f"Max token_estimate observed: {max_tokens} (spec max is 254, hard cap 256)")
    print(f"Build-time errors: {len(errors)}")
    for e in errors[:30]:
        print("  ", e)

    print("\nPer-document chunk counts (doc_id, file, count):")
    for doc_id, fname, n in per_doc:
        print(f"  {doc_id:14s} {fname:45s} {n}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
