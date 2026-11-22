"""Writes a harness run's results to `evaluation/reports/<run_id>/`
(06_evaluation_plan.md section 11): `summary.md`, `results.jsonl` and `failures.md`.
`retrieval.md` and `compare.md` (section 11's other two files) are retrieval-ablation and
run-to-run diff reports respectively -- out of scope for a single run's grading, which is
what this module writes.
"""
from __future__ import annotations

import json
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "reports"


def _result_to_jsonable(result) -> dict:
    return {
        "scenario_id": result.scenario_id,
        "suite": result.suite,
        "passed": result.passed,
        "elapsed_s": round(result.elapsed_s, 3),
        "error": result.error,
        "components": {name: {"passed": c.passed, "detail": c.detail} for name, c in result.components.items()},
        "items": [
            {"text": it.text, "kind": it.kind, "verdict": it.verdict, "method": it.method, "detail": it.detail}
            for it in result.item_results
        ],
    }


def pass_rate(results: list, predicate=lambda r: True) -> dict:
    subset = [r for r in results if predicate(r)]
    n = len(subset)
    if n == 0:
        return {"passed": 0, "failed": 0, "ungraded": 0, "total": 0, "rate": None}
    passed = sum(1 for r in subset if r.passed is True)
    failed = sum(1 for r in subset if r.passed is False)
    ungraded = sum(1 for r in subset if r.passed is None)
    return {"passed": passed, "failed": failed, "ungraded": ungraded, "total": n, "rate": round(passed / n, 4)}


def write_report(run_id: str, results: list, meta: dict) -> Path:
    out_dir = REPORTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(_result_to_jsonable(r), ensure_ascii=False) + "\n")

    suites = sorted({r.suite for r in results})
    overall = pass_rate(results)
    lines = [
        f"# Evaluation run `{run_id}`",
        "",
        f"- Mode: {meta.get('mode', 'unknown')}",
        f"- Scenarios run: {len(results)}",
        f"- Corpus/index version: {meta.get('index_version', 'unknown')}",
        f"- LLM model: {meta.get('llm_model', 'unknown')} (judge: {meta.get('judge_model', 'none -- see note below')})",
        f"- Reference date: {meta.get('reference_date', 'unknown')}",
        "",
        "**Note:** scenarios whose `answer` component needed the LLM judge of "
        "06_evaluation_plan.md section 5, and no judge was configured for this run, are "
        "reported as `ungraded` rather than counted as passed or failed -- see "
        "`failures.md` and `results.jsonl` for which scenarios and items that affected.",
        "",
        "## Overall",
        "",
        f"| Passed | Failed | Ungraded | Total | Pass rate (of total) |",
        f"|---|---|---|---|---|",
        f"| {overall['passed']} | {overall['failed']} | {overall['ungraded']} | {overall['total']} | "
        + (f"{overall['rate']*100:.1f}%" if overall["rate"] is not None else "n/a") + " |",
        "",
        "## By suite",
        "",
        "| Suite | Passed | Failed | Ungraded | Total |",
        "|---|---|---|---|---|",
    ]
    for suite in suites:
        pr = pass_rate(results, lambda r, s=suite: r.suite == s)
        lines.append(f"| {suite} | {pr['passed']} | {pr['failed']} | {pr['ungraded']} | {pr['total']} |")

    lines += ["", "## By component", "", "| Component | Passed | Failed | None (n/a or ungraded) | Scenarios |", "|---|---|---|---|---|"]
    component_names = sorted({name for r in results for name in r.components})
    for name in component_names:
        passed = sum(1 for r in results if r.components.get(name) and r.components[name].passed is True)
        failed = sum(1 for r in results if r.components.get(name) and r.components[name].passed is False)
        none_count = sum(1 for r in results if r.components.get(name) and r.components[name].passed is None)
        lines.append(f"| {name} | {passed} | {failed} | {none_count} | {len(results)} |")

    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    failure_lines = ["# Failures", ""]
    for r in results:
        if r.passed is False:
            failure_lines.append(f"## {r.scenario_id} ({r.suite})")
            if r.error:
                failure_lines.append(f"- error: {r.error}")
            for name, c in r.components.items():
                if c.passed is False:
                    failure_lines.append(f"- **{name}** failed: {c.detail}")
            for it in r.item_results:
                if it.verdict == "fail":
                    failure_lines.append(f"  - item ({it.kind}) failed: {it.text!r} -- {it.detail}")
            failure_lines.append("")
    (out_dir / "failures.md").write_text("\n".join(failure_lines) + "\n", encoding="utf-8")

    return out_dir
