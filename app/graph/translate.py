"""`detect_and_translate` and `translate_back` (02_architecture.md section 2). Three
genuinely separate jobs live here:

1. **Language detection** for `GraphState.user_language` -- implements the deterministic
   word-count convention of `06_evaluation_plan.md` section 7 (explicit request, majority
   script by word count excluding codes/numbers/URLs, tie -> Arabic, no countable words ->
   previous message's language). This needs no LLM and is fully implemented.
2. **Follow-up resolution + standalone-English-question production.** This is an open-ended
   rewriting judgment (resolving "and last month?" against prior turns) that genuinely
   needs the LLM in production, so it is injected as `Translator`, following the same
   pattern as every other LLM-only step in this build. Section 7's own note says "a
   deterministic word count produces a hint, and the model confirms it" -- i.e. even the
   real system treats the word-count result as a hint for the model, not a final answer by
   itself, which is exactly how it is used below.
3. **Translating the merged answer back to Arabic** (`translate_back`), same pattern.

An English message with *no history* needs neither translation nor follow-up resolution
(`question_en` is just the normalized text), so that path is fully real with no
degradation. Any message with history -- English or Arabic -- is handed to the translator,
because an English follow-up ("And for 2024?") needs the same reference-resolution the
spec describes just as much as an Arabic one does; conflating "needs translation" with
"needs resolution" here was an earlier bug in this module, caught by
`tests/test_evaluation_harness.py` replaying a real follow-up scenario
(`EV-GR-008`) without an LLM available. Without an LLM, an Arabic message cannot be turned
into `question_en` at all -- there is no deterministic substitute -- so
`run_detect_and_translate` says so plainly via a `None` result (mirroring the
`llm_unavailable` failure path already used in `data_analysis.py`/`inventory.py`); an
English follow-up degrades more gracefully, keeping the literal, unresolved text with a
warning, since answering the literal message is still better than refusing it outright.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from app.llm.client import GroqClient
from app.rag.entities import extract_pattern_entities

Translator = Callable[[str, list[dict]], Optional[str]]
BackTranslator = Callable[[str], Optional[str]]

_ARABIC_LETTER_RE = re.compile(r"[؀-ۿݐ-ݿ]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
_URL_RE = re.compile(r"https?://\S+")
_NUMBER_RE = re.compile(r"\d[\d,.:]*")

_EXPLICIT_REQUEST_RE = re.compile(
    r"\banswer\s+in\s+(english|arabic)\b|\brespond\s+in\s+(english|arabic)\b"
    r"|\bبال(?:عربي[ةه]?|إنجليزي[ةه]?|انجليزي[ةه]?)\b|\bأجب\s+بال",
    re.I,
)


def detect_explicit_language_request(text: str) -> Optional[str]:
    """06_evaluation_plan.md section 7 rule 1."""
    m = re.search(r"\banswer\s+in\s+(english|arabic)\b|\brespond\s+in\s+(english|arabic)\b", text, re.I)
    if m:
        word = (m.group(1) or m.group(2)).lower()
        return "en" if word == "english" else "ar"
    if re.search(r"بالعربي[ةه]?\b|أجب\s+بالعربي", text):
        return "ar"
    if re.search(r"بال(?:إنجليزي|انجليزي)[ةه]?\b|أجب\s+بالإنجليزي", text):
        return "en"
    return None


def _countable_words(text: str) -> tuple[int, int]:
    """Rule 2: majority by word count, excluding identifiers, numbers, URLs and entity
    names. Entity names are approximated here by the same pattern-based codes used
    elsewhere (SKU/branch/supplier/etc.); the full title-derived lexicon of
    `04_rag_design.md` section 8.2 is index-specific and is not available at this early,
    pre-routing stage, so a plain code-pattern strip is used instead -- documented as a
    smaller, strictly-code-only version of the exclusion the spec describes."""
    stripped = _URL_RE.sub(" ", text)
    for code in extract_pattern_entities(stripped):
        stripped = stripped.replace(code, " ")
    stripped = _NUMBER_RE.sub(" ", stripped)
    words = [w for w in re.split(r"\s+", stripped) if w.strip(".,!?؟،؛:;\"'()")]
    arabic = sum(1 for w in words if _ARABIC_LETTER_RE.search(w))
    english = sum(1 for w in words if _LATIN_LETTER_RE.search(w) and not _ARABIC_LETTER_RE.search(w))
    return arabic, english


def detect_message_language(text: str, previous_language: Optional[str] = None) -> str:
    """06_evaluation_plan.md section 7, rules 1-5, decided per message (rule 5)."""
    explicit = detect_explicit_language_request(text)
    if explicit:
        return explicit
    arabic, english = _countable_words(text)
    if arabic == 0 and english == 0:
        return previous_language or "en"  # rule 4
    if arabic == english:
        return "ar"  # rule 3 (tie)
    return "ar" if arabic > english else "en"


def _default_translator(llm: GroqClient) -> Translator:
    def translate(user_text: str, history: list[dict]) -> Optional[str]:
        system = (
            "Resolve this user message into a standalone English business question. If it "
            "refers to an earlier turn (\"and last month?\", \"what about branch RYD-OLY?\"), "
            "use the conversation history to fill in what is missing, including the prior "
            "metric, entity, comparison baseline, branch, and domain. For a follow-up such as "
            "'And November 2025?' or 'Was November 2024 higher?', rewrite it as a complete "
            "standalone question that preserves the original comparison and metric. Never "
            "invent a missing entity or metric; if context truly does not provide it, keep "
            "the ambiguity explicit. Keep every code, number and proper name exactly as given; "
            "do not answer the question yourself. "
            'Respond as JSON: {"question_en": "..."}.'
        )
        history_text = "\n".join(f"- {h.get('role', 'user')}: {h.get('text', '')[:500]}" for h in history[-6:])
        user = f"History:\n{history_text}\n\nMessage: {user_text}"
        result = llm.complete_json(system, user, call_name="translate.resolve_english_question")
        return result.data.get("question_en") if result.data else None
    return translate


def run_detect_and_translate(
    user_text: str,
    *,
    llm: GroqClient,
    history: Optional[list[dict]] = None,
    previous_language: Optional[str] = None,
    translator: Optional[Translator] = None,
) -> tuple[str, Optional[str], list[str]]:
    """Returns (user_language, question_en_or_None, warnings). `question_en` is `None` only
    when translation into English genuinely could not be produced (Arabic input, no LLM).
    An English message with no history needs no model call at all; any message with
    history, or any Arabic message, is handed to `translator` (see the module docstring)."""
    history = history or []
    language = detect_message_language(user_text, previous_language)
    if language == "en" and not history:
        return language, user_text, []

    translator = translator or _default_translator(llm)
    question_en = translator(user_text, history)
    if question_en is None:
        if language == "en":
            return language, user_text, ["could not resolve follow-up references (LLM client unavailable); the message was used as written"]
        return language, None, ["could not translate the Arabic message to English (LLM client unavailable)"]
    return language, question_en, []


def _default_back_translator(llm: GroqClient) -> BackTranslator:
    def translate(answer_en: str) -> Optional[str]:
        system = (
            "Translate this answer into Arabic. Keep every SKU/branch/supplier/customer/employee "
            "code, every number (Western digits, decision D-6), and every product, person and "
            "company name exactly as written in English. "
            'Respond as JSON: {"answer_ar": "..."}.'
        )
        result = llm.complete_json(system, answer_en, call_name="translate.back_translate")
        return result.data.get("answer_ar") if result.data else None
    return translate


def run_translate_back(
    answer_en: str,
    user_language: str,
    *,
    llm: GroqClient,
    back_translator: Optional[BackTranslator] = None,
) -> tuple[str, list[str]]:
    """Returns (answer_final, warnings). Aggregator rule 6: "translate to Arabic only at
    the end"."""
    if user_language != "ar":
        return answer_en, []
    back_translator = back_translator or _default_back_translator(llm)
    translated = back_translator(answer_en)
    if translated is None:
        return answer_en, ["could not translate the answer to Arabic (LLM client unavailable); returning the English answer"]
    return translated, []
