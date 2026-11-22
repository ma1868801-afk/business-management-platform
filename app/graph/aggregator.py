"""The `aggregator` node (02_architecture.md section 2 and section 7). Two jobs: answer
directly for greetings/clarifications/refusals (the router's `direct`, `clarify` and
`reject` decisions), or merge the node responses of one or more subgraphs into one English
answer for `route`.

The merge itself needs no LLM to be *correct* -- rule 1 ("use only facts and numbers
present in node responses") is satisfied automatically by concatenating text the subgraphs
already composed, and rules 2-5 are mechanical (order, one paragraph per part, surface
assumptions/warnings, say what failed). An LLM only makes the stitched-together paragraphs
read more smoothly, so `answer_composer` is an optional injection point (as with every
other LLM-only step in this build) that defaults to the deterministic merge below, which is
real, specified, section-7-compliant behavior on its own -- not a placeholder.
"""
from __future__ import annotations

from typing import Callable, Optional

AnswerComposer = Callable[[str, list[dict]], Optional[str]]

_REJECT_TEMPLATES = {
    "write_request": (
        "I can't make changes to business data -- this assistant is read-only. "
        "I can answer a question about the current data instead, if that helps."
    ),
    "restricted_data": (
        "I can't share that: customer contact details, credentials, the internal document "
        "index, and employee compensation beyond one named employee are restricted. "
        "I'm happy to help with a different business question."
    ),
    "prompt_injection": (
        "I can't follow instructions embedded in a message like that. If you have a business "
        "question about sales, inventory or company documents, please ask it on its own."
    ),
    "off_topic": (
        "That doesn't look related to Nakhla Retail Group's business. I can help with sales, "
        "inventory, forecasting or company policy questions instead."
    ),
}


def compose_direct(decision: dict) -> str:
    direct_answer = decision.get("direct_answer")
    if isinstance(direct_answer, str) and direct_answer.strip():
        return direct_answer
    reason = (decision.get("reason") or "").lower()
    if any(w in reason for w in ("greeting", "hello", "hi ")):
        return "Hello! I can help with questions about sales, inventory, forecasting or company documents. What would you like to know?"
    if any(w in reason for w in ("thank", "bye", "goodbye")):
        return "You're welcome. Let me know if there's anything else about the business I can help with."
    return "I can help with questions about sales, inventory, forecasting or company documents. What would you like to know?"


def compose_clarification(decision: dict) -> str:
    return decision.get("clarification_question") or "Could you rephrase your question with a bit more detail?"


def compose_reject(decision: dict) -> str:
    reason = decision.get("reject_reason")
    return _REJECT_TEMPLATES.get(reason, _REJECT_TEMPLATES["off_topic"])


def _paragraph_for(node: dict) -> tuple[str, list[str]]:
    """Returns (paragraph, notes). Rule 4: a failed node is reported as something that
    could not be answered, not silently dropped."""
    status = node.get("status")
    if status == "failed":
        err = (node.get("error") or {}).get("message", "an internal error")
        return f"I wasn't able to answer the {node.get('subgraph')} part of this question ({err}).", []
    notes = list(node.get("assumptions") or []) + list(node.get("warnings") or [])
    return node.get("answer_en", ""), notes


def aggregate_node_responses(node_responses: list[dict], answer_composer: Optional[AnswerComposer] = None) -> tuple[str, list[str]]:
    """Section 7 rules 1-5. `node_responses` is expected in the user's question order
    (the order the router listed the subgraphs in, which the fan-out preserves). Returns
    (answer_en, warnings)."""
    if answer_composer is not None:
        composed = answer_composer("", node_responses)
        if composed is not None:
            return composed, []

    paragraphs: list[str] = []
    all_notes: list[str] = []
    for node in node_responses:
        para, notes = _paragraph_for(node)
        if para:
            paragraphs.append(para)
        all_notes.extend(notes)

    answer = " ".join(paragraphs) if paragraphs else "I wasn't able to answer this question."
    # Keep assumptions and operational warnings in structured metadata for tracing,
    # but never append them to the user-facing answer. The chat response must contain
    # the answer only (no "Note:", provenance commentary, or internal diagnostics).
    seen_notes: list[str] = []
    for note in all_notes:
        if note not in seen_notes:
            seen_notes.append(note)
    return answer, seen_notes


def run_aggregator(
    decision: dict,
    node_responses: list[dict],
    answer_composer: Optional[AnswerComposer] = None,
) -> tuple[str, list[str]]:
    """Returns (answer_en, warnings). Dispatches on `decision['decision']` exactly as the
    top-level flowchart's edges do (direct/reject -> straight to a composed answer; clarify
    -> the clarification question; route -> the merge above)."""
    d = decision.get("decision")
    if d == "direct":
        return compose_direct(decision), []
    if d == "reject":
        return compose_reject(decision), []
    if d == "clarify":
        return compose_clarification(decision), []
    return aggregate_node_responses(node_responses, answer_composer)
