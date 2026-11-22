
"""Deterministic verification of factual claims against retrieved passages."""
from __future__ import annotations

import re
from datetime import datetime

from app.rag.entities import extract_pattern_entities

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NUMBER_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b"
)
_PROPER_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_CURRENCY_STRIP_RE = re.compile(r"[,$]|SAR\s*", re.I)
_STOPWORD_START = {"The", "This", "These", "A", "An", "It", "They", "We", "Customers", "Items"}


def normalize_token(tok: str) -> str:
    tok = _CURRENCY_STRIP_RE.sub("", tok)
    return re.sub(r"\s+", " ", tok).strip().lower()


def normalize_date(value: str) -> str | None:
    """Normalize supported date formats to ISO YYYY-MM-DD."""
    value = value.strip()

    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _normalized_dates(text: str) -> set[str]:
    dates: set[str] = set()
    for match in _DATE_RE.finditer(text):
        normalized = normalize_date(match.group(0))
        if normalized:
            dates.add(normalized)
    return dates



def extract_checkable_tokens(sentence: str) -> set[str]:
    tokens: set[str] = set()

    # Remove dates before extracting standalone numbers.
    # Dates are validated separately using normalized ISO values.
    sentence_without_dates = _DATE_RE.sub(" ", sentence)

    for match in _NUMBER_RE.finditer(sentence_without_dates):
        cleaned = normalize_token(match.group(0))
        if cleaned and cleaned not in {".", ""}:
            tokens.add(cleaned)

    tokens |= _normalized_dates(sentence)

    tokens |= {
        t.lower()
        for t in extract_pattern_entities(sentence)
        if not re.fullmatch(
            r"(?:KB-[A-Z]+-\d{2}|RT-\d{2}|DA-\d{2}|INV-\d{2})",
            t,
            re.I,
        )
    }

    for match in _PROPER_NAME_RE.finditer(sentence):
        name = match.group(1)
        if name.split()[0] not in _STOPWORD_START:
            tokens.add(name.lower())

    return tokens



def _passage_haystack(passages: list[dict]) -> str:
    """The grounding text a sentence is checked against. Includes each passage's `title`
    and `section_path` alongside its body: those come straight from the retrieved
    document's own metadata (we retrieved that exact chunk), so an answer mentioning its
    source by name -- the document title, a section heading, an extractive fallback
    quoting "here is the excerpt from <title>" -- is trivially grounded, not a claim that
    needs separate verification against the passage body. Without this, any answer that
    names its own source (including the knowledge_base subgraph's no-LLM extractive
    fallback, see `app/graph/knowledge_base.py`) could have that whole sentence wrongly
    rejected as "unsupported" purely because the title text itself doesn't appear in the
    body -- weakening grounding, not strengthening it."""
    parts = []
    for p in passages:
        parts.append(p.get("text", ""))
        if p.get("title"):
            parts.append(p["title"])
        if p.get("section_path"):
            parts.append(p["section_path"])
    return normalize_token(" \n ".join(parts))


def check_sentence(sentence: str, cited_passages: list[dict]) -> tuple[bool, set[str]]:
    """Returns (supported, missing_tokens)."""
    tokens = extract_checkable_tokens(sentence)
    if not tokens:
        return True, set()

    haystack = _passage_haystack(cited_passages)
    missing = {token for token in tokens if token not in haystack}

    # Date formats may differ between the answer and the source.
    source_dates = _normalized_dates(haystack)
    answer_dates = _normalized_dates(sentence)
    missing_dates = answer_dates - source_dates

    missing -= answer_dates
    missing |= missing_dates

    return not missing, missing


def citation_check(
    draft_answer: str,
    cited_passages: list[dict],
    regenerate_sentence=None,
) -> tuple[str, list[str]]:
    """Check every answer sentence and remove unsupported sentences."""
    sentences = [
        sentence
        for sentence in _SENT_SPLIT_RE.split(draft_answer.strip())
        if sentence.strip()
    ]

    kept: list[str] = []
    warnings: list[str] = []

    for sentence in sentences:
        supported, missing = check_sentence(sentence, cited_passages)

        if supported:
            kept.append(sentence)
            continue

        if regenerate_sentence is not None:
            fixed = regenerate_sentence(sentence, missing)
            if fixed:
                supported2, _ = check_sentence(fixed, cited_passages)
                if supported2:
                    kept.append(fixed)
                    continue

        warnings.append(
            "a sentence was removed because it was not supported by a cited passage: "
            f"{sorted(missing)}"
        )

    if not kept:
        return (
            "The company documents available to this assistant do not contain "
            "the information needed to answer this question.",
            warnings,
        )

    return " ".join(kept), warnings
