"""The RAG Guard's passage screen (05_security_and_guardrails.md section 9.2): flags a
retrieved (or, at build time, indexed) passage as `suspicious` when its text, outside code
fences, looks like it is trying to direct the assistant rather than inform it.

A flagged passage is quarantined (section 9.3): removed from the evidence given to the
answering model, with a warning recorded and the passage id written to the trace. This
module only screens; quarantine is the caller's job (`app/rag/pipeline.py`'s selection
stage, and the knowledge_base subgraph's node once it exists).

Two chunks in the real corpus quote attack phrases on purpose, as worked examples for the
router (RT-05's "Rule 1: Prompt Injection" section and one of RT-06's example rows): they
are allow-listed by chunk id, exactly as section 9.2 specifies ("they are on an allow-list
in the indexer configuration").
"""
from __future__ import annotations

import re

ALLOWLISTED_CHUNK_IDS = {"RT-05#03", "RT-06#11"}

_HIGH_CONFIDENCE_PATTERNS: dict[str, re.Pattern] = {
    "override": re.compile(
        r"\b(ignore|disregard|forget)\s+(all\s+|any\s+)?(previous|prior|earlier|above)\s+"
        r"(instructions?|rules?|prompts?|context)\b",
        re.I,
    ),
    "reveal_prompt": re.compile(
        r"\b(reveal|show|print|repeat|output)\s+(me\s+)?your\s+(system\s+prompt|instructions?|"
        r"guidelines?|rules?)\b",
        re.I,
    ),
    "role_change": re.compile(
        r"\byou\s+are\s+now\s+(an?\s+)?(admin|administrator|developer|root|unrestricted)\b"
        r"|\bact\s+as\s+(an?\s+)?(admin|administrator|developer|root|unrestricted|a\s+different\s+ai)\b",
        re.I,
    ),
    "privilege_claim": re.compile(
        r"\b(run|execute)\s+(this\s+)?(sql|query|code)\s+as\s+(superuser|admin|administrator|root)\b"
        r"|\bi\s+am\s+(the\s+)?(developer|admin|administrator|owner)\s+of\s+this\s+(system|assistant|app)\b",
        re.I,
    ),
    "fake_system": re.compile(r"^\s*\[?\s*system\s*\]?\s*:", re.I | re.M),
}

_DIRECTIVE_TO_ASSISTANT_RE = re.compile(
    r"\b(tell\s+the\s+user\s+that|respond\s+with|when\s+answering[, ]|always\s+say|"
    r"you\s+must\s+(say|respond|answer|tell))\b",
    re.I,
)
_MARKUP_RE = re.compile(r"<script\b|javascript:|!\[[^\]]*\]\(https?://", re.I)
_BASE64_RUN_RE = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")

_CODE_FENCE_RE = re.compile(r"```.*?```", re.S)


def _strip_code(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text)


def screen_passage(text: str, chunk_id: str | None = None) -> tuple[bool, list[str]]:
    """Returns (suspicious, reasons). `text` should be the passage's full body (code fences
    are stripped internally, per section 9.2: "matches ... outside code fences")."""
    if chunk_id and chunk_id in ALLOWLISTED_CHUNK_IDS:
        return False, []
    body = _strip_code(text)
    reasons = []
    for name, pattern in _HIGH_CONFIDENCE_PATTERNS.items():
        if pattern.search(body):
            reasons.append(name)
    if _DIRECTIVE_TO_ASSISTANT_RE.search(body):
        reasons.append("directive_to_model")
    if _MARKUP_RE.search(body):
        reasons.append("markup")
    if _BASE64_RUN_RE.search(body):
        reasons.append("base64_run")
    return bool(reasons), reasons
