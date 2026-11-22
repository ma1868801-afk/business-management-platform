"""Grades one scenario's graph output against its `expected` block
(06_evaluation_plan.md section 4: route, method, status, answer, language).

A component's `passed` is `True`/`False` when it could be checked, and `None` ("ungraded")
when it fundamentally needs something this sandbox does not have -- chiefly the LLM judge
of section 5 for `must_include` items that state a meaning or behavior rather than a number
("months with Ramadan, Eid and White Friday days rank high" has no deterministic check).
`None` is never silently counted as a pass: `ScenarioResult.passed` returns `None` whenever
any applicable component is ungraded, so a report built from this harness can never claim a
pass rate it did not actually verify. A real `Judge` callable (an LLM call matching section
5's prompt) plugs in via the `judge` parameter without changing anything else here --
exactly the dependency-injection pattern used for every other LLM-only step in this build.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.guards.output_guard import (
    _BEARER_RE, _CONN_STRING_RE, _EMAIL_RE, _GROQ_KEY_RE, _PHONE_RE, _SECRET_KV_RE,
    _extract_numbers, _is_supported, check_language,
)

Judge = Callable[..., tuple[str, str]]  # (scenario, answer, item_text, kind, final_state, oracle) -> (verdict, detail)

TOOL_NAME_MAP = {"rag": "rag_tool", "postgres": "postgres_tool", "pandas": "pandas_tool", "regression": "regression_tool"}


@dataclass
class ComponentResult:
    name: str
    passed: Optional[bool]  # None = ungraded
    detail: str = ""


@dataclass
class ItemResult:
    text: str
    kind: str  # "must_include" | "must_not_include"
    verdict: str  # "pass" | "fail" | "ungraded"
    method: str
    detail: str = ""


@dataclass
class ScenarioResult:
    scenario_id: str
    suite: str
    components: dict = field(default_factory=dict)
    item_results: list = field(default_factory=list)
    elapsed_s: float = 0.0
    error: Optional[str] = None

    @property
    def passed(self) -> Optional[bool]:
        if self.error is not None:
            return False
        values = [c.passed for c in self.components.values()]
        if any(v is False for v in values):
            return False
        if any(v is None for v in values):
            return None
        return True


def grade_route(scenario, final_state) -> ComponentResult:
    expected = scenario.expected.get("route")
    if not expected:
        return ComponentResult("route", None, "scenario has no expected.route")
    actual = final_state.get("route") or {}
    exp_decision, act_decision = expected.get("decision"), actual.get("decision")
    if exp_decision != act_decision:
        return ComponentResult("route", False, f"expected decision={exp_decision!r}, got {act_decision!r}")

    if exp_decision == "route":
        exp_names = expected.get("subgraphs", [])
        act_subgraphs = actual.get("subgraphs") or []
        act_names = [sg.get("name") for sg in act_subgraphs]
        if act_names != exp_names:
            return ComponentResult("route", False, f"expected subgraphs {exp_names}, got {act_names}")
        act_by_name = {sg.get("name"): sg for sg in act_subgraphs}
        for sg_name, hint_dict in (expected.get("hints") or {}).items():
            act_hints = (act_by_name.get(sg_name) or {}).get("hints") or {}
            for key, value in (hint_dict or {}).items():
                if act_hints.get(key) != value:
                    return ComponentResult("route", False, f"{sg_name}.hints.{key}: expected {value!r}, got {act_hints.get(key)!r}")
        return ComponentResult("route", True)

    if exp_decision == "reject":
        if expected.get("reject_reason") != actual.get("reject_reason"):
            return ComponentResult("route", False, f"expected reject_reason={expected.get('reject_reason')!r}, got {actual.get('reject_reason')!r}")
        return ComponentResult("route", True)

    return ComponentResult("route", True)  # clarify/direct: decision equality already checked


def grade_method(scenario, final_state) -> ComponentResult:
    expected = scenario.expected.get("method")
    if not expected:
        return ComponentResult("method", None, "not applicable (decision != route, or no expected.method)")

    node_by_name = {n["subgraph"]: n for n in final_state.get("node_responses", [])}
    # rag_tool isn't recorded in data_analysis/inventory's own `method.tools_used` (only
    # knowledge_base's is) because it always runs as the first node of every subgraph; its
    # use is confirmed from the trace instead, so the comparison stays faithful to the
    # already-tested M4 modules rather than needing them changed for this harness.
    rag_ran = {
        name for name in node_by_name
        if any(e["node"] in (f"{name}.rag_retrieve", f"{name}.retrieve_rerank") for e in final_state.get("trace", []))
    }

    for sg_name, spec in expected.items():
        node = node_by_name.get(sg_name)
        if node is None:
            return ComponentResult("method", False, f"subgraph {sg_name!r} did not run")
        method = node.get("method") or {}
        tools_used = set(method.get("tools_used") or [])
        bypassed = set(method.get("bypassed") or [])
        for t in spec.get("tools_used", []):
            if t == "rag":
                if sg_name not in rag_ran and "rag_tool" not in tools_used:
                    return ComponentResult("method", False, f"{sg_name}: expected rag to be used")
                continue
            real = TOOL_NAME_MAP.get(t, t)
            if real not in tools_used:
                return ComponentResult("method", False, f"{sg_name}: expected tool {t!r} to be used")
        for t in spec.get("bypassed", []):
            real = TOOL_NAME_MAP.get(t, t)
            if real in tools_used:
                return ComponentResult("method", False, f"{sg_name}: expected tool {t!r} to be bypassed but it ran")
    return ComponentResult("method", True)


def grade_status(scenario, final_state) -> ComponentResult:
    expected = scenario.expected.get("status")
    if expected is None:
        return ComponentResult("status", None, "not applicable")
    from app.api_core import _overall_status
    actual = _overall_status(final_state.get("node_responses") or [])
    return ComponentResult("status", actual == expected, f"expected {expected}, got {actual}")


def grade_language(scenario, final_state) -> ComponentResult:
    expected_lang = (scenario.expected.get("answer") or {}).get("language")
    if expected_lang is None:
        return ComponentResult("language", None, "not applicable")
    ok = check_language(final_state.get("answer_final", ""), expected_lang)
    return ComponentResult("language", ok, f"expected {expected_lang}")


_MUST_NOT_PATTERNS = [
    (re.compile(r"\bemail\b", re.I), lambda t: _EMAIL_RE.search(t) is not None),
    (re.compile(r"\bphone\b", re.I), lambda t: _PHONE_RE.search(t) is not None),
    (
        re.compile(r"password|credential|api\s*key|connection string|secret", re.I),
        lambda t: bool(_CONN_STRING_RE.search(t) or _GROQ_KEY_RE.search(t) or _SECRET_KV_RE.search(t) or _BEARER_RE.search(t)),
    ),
]


def _check_must_not_include(item_text: str, actual_text: str) -> tuple[str, str]:
    for pattern, checker in _MUST_NOT_PATTERNS:
        if pattern.search(item_text):
            return ("fail" if checker(actual_text) else "pass"), "deterministic redaction-pattern check (05_security section 10.3)"
    return "ungraded", "no deterministic redaction rule matches this item; needs the judge"


_WORD_RE = re.compile(r"[A-Za-z؀-ۿ]+")


def _is_short_literal_item(item_text: str) -> bool:
    """A conservative guard against over-matching: `_extract_numbers` finds a digit in
    *any* sentence that happens to mention a date or count, including purely descriptive
    claims about the sub-question ("sub_question is standalone and mentions net revenue
    for 2025-01-01 to 2025-12-31") where the figure to check is not actually in the final
    answer at all. Those need the judge. A short item that is essentially just the figure
    itself ("2024-01-01", "30 days") is safe to compare directly -- at most a handful of
    words beside the number(s)."""
    return len(_WORD_RE.findall(item_text)) <= 4


def _check_numeric_item(item_text: str, actual_text: str, oracle) -> Optional[tuple[str, str]]:
    mentions_oracle = "oracle" in item_text.lower()
    if mentions_oracle:
        if oracle is None:
            return "ungraded", "item references the oracle but no oracle entry (or no DB access) was available"
        target_numbers = oracle.numbers()
    else:
        if not _is_short_literal_item(item_text):
            return None  # a longer semantic claim that happens to contain a number; defer to the judge
        target_numbers = _extract_numbers(item_text)
        if not target_numbers:
            return None  # not a numeric claim; defer to the judge
    actual_numbers = _extract_numbers(actual_text)
    if not actual_numbers:
        return "fail", "the answer contains no number to compare"
    matched = any(_is_supported(n, target_numbers) for n in actual_numbers) or any(_is_supported(t, actual_numbers) for t in target_numbers)
    return ("pass" if matched else "fail"), f"target numbers {sorted(target_numbers)} vs. answer numbers {sorted(actual_numbers)}"


def grade_answer(scenario, final_state, *, oracle_store=None, postgres_executor=None, judge: Optional[Judge] = None) -> tuple[ComponentResult, list[ItemResult]]:
    answer_block = scenario.expected.get("answer") or {}
    must_include = list(answer_block.get("must_include") or [])

    # Section 3's note: a clarify/direct decision's prose description is graded as part of
    # the answer, not the route.
    route = scenario.expected.get("route") or {}
    if route.get("decision") == "clarify" and route.get("clarification"):
        must_include.append(route["clarification"])
    if route.get("decision") == "direct" and route.get("direct_answer"):
        must_include.append(route["direct_answer"])
    must_not_include = list(answer_block.get("must_not_include") or [])

    actual_text = final_state.get("answer_final", "") or ""
    items: list[ItemResult] = [
        ItemResult(text=t, kind="must_not_include", verdict=v, method="deterministic_redaction", detail=d)
        for t in must_not_include for v, d in [_check_must_not_include(t, actual_text)]
    ]

    oracle = None
    if oracle_store is not None and postgres_executor is not None and oracle_store.has(scenario.id):
        oracle = oracle_store.run(scenario.id, postgres_executor)

    for text in must_include:
        numeric = _check_numeric_item(text, actual_text, oracle)
        if numeric is not None:
            verdict, detail = numeric
            items.append(ItemResult(text=text, kind="must_include", verdict=verdict, method="deterministic_numeric", detail=detail))
            continue
        if judge is not None:
            verdict, detail = judge(scenario, actual_text, text, "must_include", final_state, oracle)
            items.append(ItemResult(text=text, kind="must_include", verdict=verdict, method="judge", detail=detail))
        else:
            items.append(ItemResult(text=text, kind="must_include", verdict="ungraded", method="no_judge", detail="no LLM judge available"))

    # Grounding (section 4.5 point 3 / 05_security section 10.2): every number in the
    # answer must be supported by the node responses, regardless of item-level verdicts.
    supported: set[float] = set()
    for node in final_state.get("node_responses", []):
        supported |= _extract_numbers(node.get("answer_en", "") or "")
        for kf in node.get("key_figures") or []:
            try:
                supported.add(round(float(kf["value"]), 6))
            except (KeyError, TypeError, ValueError):
                pass
    unsupported = [v for v in _extract_numbers(actual_text) if not _is_supported(v, supported)]

    verdicts = [it.verdict for it in items]
    if any(v == "fail" for v in verdicts) or unsupported:
        passed = False
    elif any(v == "ungraded" for v in verdicts):
        passed = None
    else:
        passed = True
    detail = f"{len(items)} item(s) graded" + (f"; unsupported numbers in answer: {unsupported}" if unsupported else "")
    return ComponentResult("answer", passed, detail), items


def grade_scenario(scenario, final_state, elapsed_s: float = 0.0, *, oracle_store=None, postgres_executor=None, judge: Optional[Judge] = None) -> ScenarioResult:
    answer_component, item_results = grade_answer(scenario, final_state, oracle_store=oracle_store, postgres_executor=postgres_executor, judge=judge)
    components = {
        "route": grade_route(scenario, final_state),
        "method": grade_method(scenario, final_state),
        "status": grade_status(scenario, final_state),
        "language": grade_language(scenario, final_state),
        "answer": answer_component,
    }
    return ScenarioResult(scenario_id=scenario.id, suite=scenario.suite, components=components, item_results=item_results, elapsed_s=elapsed_s)
