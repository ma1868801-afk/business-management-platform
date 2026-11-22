"""The `output_guard` node (02_architecture.md section 2; 05_security_and_guardrails.md
section 10). Deterministic code that runs on the final answer, after `translate_back`.

Checks 5 ("number grounding") and 6 ("language") specify a one-time LLM regeneration
before their documented fallback; no LLM is available in this sandbox, so both go straight
to their fallback path every time (rebuild from node responses; return the English answer
with a note, respectively) -- which is itself the documented behavior for a *second*
failure, not a shortcut invented here. `regenerate_answer`/`regenerate_translation`
injection points are provided so a real LLM can be wired in later without changing this
module's control flow, exactly as the subgraphs inject their SQL/Pandas generators.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

_ARABIC_LETTER_RE = re.compile(r"[؀-ۿݐ-ݿ]")
_ANY_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_CODE_RE = re.compile(r"\b[A-Z]{2,6}-[A-Z0-9]{2,6}\b")

# --- 10.3 Redaction patterns ---------------------------------------------------------------
_EMAIL_RE = re.compile(r"\b[\w.+-]+@([\w-]+\.[\w.-]+)\b")
_PHONE_RE = re.compile(r"(?:\+966|00966)[\s\-]?\d(?:[\s\-]?\d){7,8}\b|\b05(?:[\s\-]?\d){8}\b")
_CONN_STRING_RE = re.compile(r"\bpostgres(?:ql)?://\S+", re.I)
_GROQ_KEY_RE = re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9\-_.]{10,}\b")
_SECRET_KV_RE = re.compile(r"\b(?:password|secret|api_key|token)\s*[:=]\s*\S+", re.I)
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)

# --- 10.4 Salary rule -----------------------------------------------------------------------
_EMP_CODE_RE = re.compile(r"\bEMP-\d{4,}\b")
_SALARY_WORD_RE = re.compile(r"\b(salary|salaries|compensation|monthly pay|wage)\b", re.I)
_MONEY_RE = re.compile(r"\bSAR\s?[\d,]+(?:\.\d+)?\b|\b[\d,]+(?:\.\d+)?\s?SAR\b", re.I)
_PROPER_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)\b")

# --- 10.5 Sanitization ----------------------------------------------------------------------
_RAW_HTML_RE = re.compile(r"<(?!/?(b|i|strong|em|code|pre)\b)[^>]+>", re.I)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_JS_DATA_LINK_RE = re.compile(r"\]\((javascript|data):[^)]*\)", re.I)
_EXTERNAL_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]*)\)", re.I)

GENERIC_REFUSAL = "I can't share that. If you have a business question I can help with, please ask it directly."


@dataclass
class GuardResult:
    text: str
    blocked: bool = False
    redactions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _canary_check(text: str, canary_token: str) -> Optional[str]:
    """10.1 check 1. A canary in the output means the system prompt leaked; the whole
    response is replaced, never just the matched span."""
    if canary_token and canary_token in text:
        return GENERIC_REFUSAL
    return None


def _redact_credentials(text: str) -> tuple[str, list[str], bool]:
    """10.1 check 2. A real secret (a Groq key, a private key block, or the canary -- the
    canary is handled separately) blocks the whole answer; the other patterns are merely
    redacted in place, since a password=... fragment is a lower-stakes leak than a live
    key and the rest of the answer is still useful."""
    redactions = []
    if _GROQ_KEY_RE.search(text) or _PRIVATE_KEY_RE.search(text):
        return GENERIC_REFUSAL, ["credential_key"], True
    for pat, name in ((_CONN_STRING_RE, "connection_string"), (_BEARER_RE, "bearer_token"), (_SECRET_KV_RE, "secret_kv")):
        if pat.search(text):
            text = pat.sub("[redacted]", text)
            redactions.append(name)
    return text, redactions, False


def _redact_contact_details(text: str, company_email_domains: tuple[str, ...]) -> tuple[str, list[str]]:
    """10.1 check 3 / 10.3. Employee work emails on a company domain are Internal data and
    may stay; any other email, and any Saudi phone number, is redacted."""
    redactions = []

    def _email_sub(m: re.Match) -> str:
        domain = m.group(1).lower()
        if any(domain == d.strip().lower() or domain.endswith("." + d.strip().lower()) for d in company_email_domains):
            return m.group(0)
        redactions.append("email")
        return "[redacted email]"

    text = _EMAIL_RE.sub(_email_sub, text)
    if _PHONE_RE.search(text):
        redactions.append("phone")
        text = _PHONE_RE.sub("[redacted phone number]", text)
    return text, redactions


def _apply_salary_rule(text: str, sources: list[dict]) -> tuple[str, bool]:
    """10.1 check 4 / 10.4: compensation may be given for one named employee only. Flags a
    violation when the answer is built from an employee record set (`KB-EMP-nn`) *and*
    carries a monetary figure tied to two or more distinct employees (by EMP code, or by
    two or more distinct proper names each co-occurring with a salary word and a monetary
    figure) -- the router and the knowledge_base prompt are the primary enforcement (section
    10.4: "the output guard is the last check"), so this is deliberately a coarse net, not
    a precise NLP judgment."""
    from_employee_records = any(
        isinstance(s, dict) and str(s.get("doc_id", "")).startswith("KB-EMP-") for s in sources
    )
    if not from_employee_records or not _SALARY_WORD_RE.search(text) or not _MONEY_RE.search(text):
        return text, False
    emp_codes = set(_EMP_CODE_RE.findall(text))
    names = set(_PROPER_NAME_RE.findall(text))
    distinct_people = len(emp_codes) if len(emp_codes) >= 2 else len(names)
    if distinct_people < 2:
        return text, False
    replacement = "Compensation is given for one named employee only; this answer cannot list or compare multiple employees' pay."
    text = _MONEY_RE.sub("[redacted]", text)
    return text + " " + replacement, True


def _extract_numbers(text: str) -> set[float]:
    """10.2 point 1/2: pulls amounts, percentages, counts, ratios, dates and years out of
    text, with thousand separators, currency words/symbols and percent signs removed, and
    the unit words 'thousand'/'million'/'billion' applied as a scale factor."""
    out: set[float] = set()
    for m in re.finditer(r"\b(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion)?%?\b", text, re.I):
        raw = m.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        value *= {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}.get(unit, 1)
        out.add(round(value, 6))
    for m in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text):
        for part in m.group(0).split("-"):
            out.add(float(part))
    return out


def _is_supported(value: float, supported: set[float]) -> bool:
    for s in supported:
        if value == s:
            return True
        if s != 0 and abs(value - s) / abs(s) <= 0.005:
            return True
        if abs(value - s) <= 0.5 and value < 1000:
            return True
    return False


def check_number_grounding(
    answer: str, node_responses: list[dict], question_en: str, settings,
    regenerate_answer: Optional[Callable[[list[str]], Optional[str]]] = None,
) -> tuple[str, list[str]]:
    """10.1 check 5 / 10.2. Returns (possibly-rewritten answer, warnings)."""
    supported: set[float] = set()
    supported |= _extract_numbers(question_en or "")
    supported.add(float(settings.forecast_max_horizon_weeks))  # "13 weeks" fixed constant
    for node in node_responses:
        supported |= _extract_numbers(node.get("answer_en", "") or "")
        for kf in node.get("key_figures", []) or []:
            try:
                supported.add(round(float(kf["value"]), 6))
            except (KeyError, TypeError, ValueError):
                pass
        for a in node.get("assumptions", []) or []:
            supported |= _extract_numbers(a)
        for w in node.get("warnings", []) or []:
            supported |= _extract_numbers(w)

    unsupported = [v for v in _extract_numbers(answer) if not _is_supported(v, supported)]
    if not unsupported:
        return answer, []

    if regenerate_answer is not None:
        fixed = regenerate_answer(unsupported)
        if fixed is not None:
            still_unsupported = [v for v in _extract_numbers(fixed) if not _is_supported(v, supported)]
            if not still_unsupported:
                return fixed, []

    # Fallback (10.2 point 5): rebuild from the node responses' own answer_en, in question order.
    rebuilt = " ".join(n.get("answer_en", "") for n in node_responses if n.get("answer_en"))
    warning = (
        f"the drafted answer contained a number not supported by the retrieved evidence "
        f"({unsupported}); the answer was rebuilt from the underlying results"
    )
    return (rebuilt or answer), [warning]


def check_language(text: str, expected_lang: str) -> bool:
    """10.1 check 6, script-ratio form (06_evaluation_plan.md section 4.6): strip codes and
    numbers, then require >=60% Arabic letters for 'ar' or <=5% for 'en'."""
    stripped = _CODE_RE.sub("", text)
    stripped = re.sub(r"\d+", "", stripped)
    letters = _ANY_LETTER_RE.findall(stripped)
    if not letters:
        return True
    ratio = len(_ARABIC_LETTER_RE.findall(stripped)) / len(letters)
    return ratio >= 0.60 if expected_lang == "ar" else ratio <= 0.05


def sanitize_markdown(text: str) -> str:
    """10.1 check 7 / 10.5: keeps headings, paragraphs, lists, tables, bold/italic, inline
    code and code blocks; strips raw HTML, images, scripts, javascript:/data: links, and
    renders any other link as plain text (closing the image/link exfiltration channel)."""
    text = _IMAGE_RE.sub(lambda m: m.group(1), text)
    text = _JS_DATA_LINK_RE.sub("](#)", text)
    text = _EXTERNAL_LINK_RE.sub(lambda m: m.group(1), text)
    text = _RAW_HTML_RE.sub("", text)
    return text


def output_guard(
    answer: str,
    *,
    node_responses: list[dict],
    question_en: str,
    expected_lang: str,
    settings,
    regenerate_answer: Optional[Callable[[list[str]], Optional[str]]] = None,
    regenerate_translation: Optional[Callable[[], Optional[str]]] = None,
    english_fallback: Optional[str] = None,
) -> GuardResult:
    sources = [s for n in node_responses for s in (n.get("sources") or [])]
    warnings: list[str] = []

    blocked = _canary_check(answer, settings.canary_token)
    if blocked is not None:
        return GuardResult(blocked, blocked=True, warnings=["canary token detected in the drafted answer"])

    text, cred_redactions, hard_block = _redact_credentials(answer)
    if hard_block:
        return GuardResult(text, blocked=True, warnings=["a credential pattern was detected in the drafted answer"])
    if cred_redactions:
        warnings.append(f"credential-like text was redacted: {cred_redactions}")

    text, contact_redactions = _redact_contact_details(text, settings.company_email_domains)
    if contact_redactions:
        warnings.append(f"contact details were redacted: {contact_redactions}")

    text, salary_triggered = _apply_salary_rule(text, sources)
    if salary_triggered:
        warnings.append("compensation figures for more than one employee were redacted (salary rule)")

    text, grounding_warnings = check_number_grounding(text, node_responses, question_en, settings, regenerate_answer)
    warnings.extend(grounding_warnings)

    if not check_language(text, expected_lang):
        fixed = regenerate_translation() if regenerate_translation else None
        if fixed is not None and check_language(fixed, expected_lang):
            text = fixed
        elif english_fallback is not None:
            text = english_fallback
            warnings.append("the translation did not pass the language check; the English answer was returned instead")

    text = sanitize_markdown(text)
    return GuardResult(text, blocked=False, redactions=cred_redactions + contact_redactions, warnings=warnings)
