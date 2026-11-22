"""Loads the 220 evaluation scenarios of `evaluation/*.md` (06_evaluation_plan.md section 3)
and runs the suite's own self-check (section 13: "Checks that ran when the suite was built
... and that the harness repeats as a unit test of the suite itself"). Pure parsing and
validation, no DB and no LLM, so it runs anywhere.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation"

SUITE_FILES = {
    "router": "01_router_scenarios.md",
    "data_analysis": "02_data_analysis_scenarios.md",
    "inventory": "03_inventory_scenarios.md",
    "knowledge_base": "04_knowledge_base_scenarios.md",
    "cross_subgraph": "05_cross_subgraph_and_language_scenarios.md",
    "guardrails": "06_guardrail_and_robustness_scenarios.md",
}
EXPECTED_SUITE_COUNTS = {
    "router": 40, "data_analysis": 56, "inventory": 46, "knowledge_base": 46,
    "cross_subgraph": 20, "guardrails": 12,
}
VALID_DECISIONS = {"route", "clarify", "direct", "reject"}
VALID_REJECT_REASONS = {"write_request", "restricted_data", "prompt_injection", "off_topic"}
VALID_SUBGRAPHS = {"data_analysis", "inventory", "knowledge_base"}

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.S)
_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿ]")
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


@dataclass
class Scenario:
    id: str
    suite: str
    category: str
    language: str
    difficulty: str
    prompt: str
    prompt_en: str | None
    history: list[dict]
    expected: dict
    basis: dict
    note: str | None
    raw: dict


def _load_suite_file(suite: str, filename: str) -> list[Scenario]:
    text = (EVAL_DIR / filename).read_text(encoding="utf-8")
    scenarios = []
    for block in _YAML_BLOCK_RE.findall(text):
        data = yaml.safe_load(block)
        scenarios.append(Scenario(
            id=data["id"], suite=data.get("suite", suite), category=data.get("category", ""),
            language=data.get("language", "en"), difficulty=data.get("difficulty", "medium"),
            prompt=data["prompt"], prompt_en=data.get("prompt_en"), history=data.get("history") or [],
            expected=data.get("expected") or {}, basis=data.get("basis") or {}, note=data.get("note"), raw=data,
        ))
    return scenarios


def load_all_scenarios() -> list[Scenario]:
    all_scenarios: list[Scenario] = []
    for suite, filename in SUITE_FILES.items():
        all_scenarios.extend(_load_suite_file(suite, filename))
    return all_scenarios


def smoke_set(scenarios: list[Scenario]) -> list[Scenario]:
    """Section 8.1: "every EV-GR scenario, every EV-RT rejection scenario and the first
    scenario of each other category" (53 scenarios)."""
    selected: list[Scenario] = []
    seen_categories: set[tuple[str, str]] = set()
    for s in scenarios:
        if s.suite == "guardrails":
            selected.append(s)
        elif s.suite == "router" and s.category.startswith("reject_"):
            selected.append(s)
        else:
            key = (s.suite, s.category)
            if key not in seen_categories:
                seen_categories.add(key)
                selected.append(s)
    return selected


# --- Section 13 self-check -------------------------------------------------------------------

@dataclass
class SelfCheckReport:
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def self_check(scenarios: list[Scenario]) -> SelfCheckReport:
    errors: list[str] = []

    ids = [s.id for s in scenarios]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        errors.append(f"duplicate scenario ids: {dupes}")

    prompts = [s.prompt for s in scenarios]
    if len(prompts) != len(set(prompts)):
        dupes = {p for p in prompts if prompts.count(p) > 1}
        errors.append(f"duplicate prompts: {len(dupes)} value(s) repeated")

    counts: dict[str, int] = {}
    for s in scenarios:
        counts[s.suite] = counts.get(s.suite, 0) + 1
    for suite, expected_n in EXPECTED_SUITE_COUNTS.items():
        if counts.get(suite, 0) != expected_n:
            errors.append(f"suite {suite!r} has {counts.get(suite, 0)} scenarios, expected {expected_n}")

    for s in scenarios:
        route = s.expected.get("route", {})
        decision = route.get("decision")
        if decision is not None and decision not in VALID_DECISIONS:
            errors.append(f"{s.id}: invalid decision {decision!r}")
        if decision == "route":
            for sg in route.get("subgraphs", []):
                if sg not in VALID_SUBGRAPHS:
                    errors.append(f"{s.id}: invalid subgraph name {sg!r}")
            hints = route.get("hints", {}) or {}
            for sg_name, sg_hints in hints.items():
                hz = (sg_hints or {}).get("horizon_weeks")
                if hz is not None and not (1 <= hz <= 13):
                    errors.append(f"{s.id}: horizon_weeks {hz} out of range 1-13")
        if decision == "reject" and route.get("reject_reason") not in VALID_REJECT_REASONS:
            errors.append(f"{s.id}: invalid reject_reason {route.get('reject_reason')!r}")

        # Section 13 point 3: non-ASCII only in prompt fields.
        for field_name, value in s.raw.items():
            if field_name in ("prompt", "prompt_en"):
                continue
            if isinstance(value, str) and _NON_ASCII_RE.search(value):
                errors.append(f"{s.id}: non-ASCII character found outside a prompt field ({field_name!r})")

        if s.language == "en" and _NON_ASCII_RE.search(s.prompt):
            errors.append(f"{s.id}: English scenario prompt contains non-ASCII text")
        if s.language in ("ar", "mixed") and not _ARABIC_RE.search(s.prompt):
            errors.append(f"{s.id}: {s.language} scenario prompt contains no Arabic script")
        if s.language in ("ar", "mixed") and not s.prompt_en:
            errors.append(f"{s.id}: {s.language} scenario is missing prompt_en")

    return SelfCheckReport(errors=errors)


def check_prompts_not_in_rag_sources(scenarios: list[Scenario], rag_sources_dir: Path, min_len: int = 15) -> list[str]:
    """Section 13 point 3: "No prompt (and no history prompt) of 15 or more characters
    appears verbatim in a RAG source" -- a retrieval question must not be answerable by
    copying the source text back. Returns a list of violation messages (empty if clean)."""
    corpus_text = ""
    for p in sorted(rag_sources_dir.rglob("*.md")):
        corpus_text += unicodedata.normalize("NFKC", p.read_text(encoding="utf-8")) + "\n"
    violations = []
    for s in scenarios:
        candidates = [s.prompt] + [h.get("prompt", "") for h in s.history]
        for text in candidates:
            normalized = unicodedata.normalize("NFKC", text)
            if len(normalized) >= min_len and normalized in corpus_text:
                violations.append(f"{s.id}: prompt text appears verbatim in rag_sources/")
    return violations
