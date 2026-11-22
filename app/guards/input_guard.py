"""The `input_guard` node (02_architecture.md section 2; 05_security_and_guardrails.md
section 4). Deterministic code, run before any model call, so a blocked request never
costs an LLM call and an attacker can never influence a blocked response's wording (the
response templates below are fixed strings, in English and Arabic).

Two parts of the specified check set need resources this sandbox does not have and are
honestly degraded, both documented at their point of use below:
- "a small-model check" for medium-confidence cases (section 4.1 point 4 / section 4.3
  "if the small-model check is enabled, it classifies medium cases as attack or benign") --
  no small model is available here, so medium cases always pass flagged, exactly as section
  4.3 describes for when the check is *not* enabled.
- the language check's "Latin-script text that a language detector identifies as another
  language with confidence >= 0.8 is unsupported" (section 4.1 point 3) -- no language
  detector library is installed in this sandbox; the script-ratio part of the check (the
  part that needs no such library) is fully implemented, and this one sub-case is skipped
  with a note in the module rather than silently pretending to run it.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.guards.injection_patterns import screen_text

# Section 4.1.1: zero-width and bidi control characters, plus the Arabic tatweel.
_ZERO_WIDTH_BIDI_RE = re.compile(
    "[​-‏‪-‮⁦-⁩﻿ـ]"
)
# Arabic combining diacritics (tashkeel: fatha/damma/kasra/shadda/sukun/tanween and the
# Quranic marks) are optional in written Arabic and do not change which word is written --
# the same way the guard does not care about English capitalization. Left in place, they
# silently break substring/regex matching in the injection screen (section 4.3) whenever an
# attacker, or simply a more formally-typed message, includes them (e.g. "فصاعدًا" with a
# tanween mark fails to match the undiacritized "فصاعدا" used in the pattern file). Found
# via the M8 injection-corpus test (tests/test_injection_corpus.py) replaying a diacritized
# real-world phrasing; not part of section 4.1.1's original list, but the same kind of
# normalization it already does for zero-width/bidi characters and tatweel.
_ARABIC_DIACRITIC_RE = re.compile("[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]")
_WHITESPACE_RE = re.compile(r"\s+")

# Arabic-Indic (U+0660-0669) and Eastern Arabic-Indic / Extended Arabic-Indic (U+06F0-06F9)
# digits -> Western digits (decision D-6: answers keep Western digits; inputs are
# normalized to the same convention so every later stage sees one digit system).
_DIGIT_MAP = {}
for _i in range(10):
    _DIGIT_MAP[chr(0x0660 + _i)] = str(_i)
    _DIGIT_MAP[chr(0x06F0 + _i)] = str(_i)
_DIGIT_TRANSLATE = str.maketrans(_DIGIT_MAP)

_ARABIC_LETTER_RE = re.compile(r"[؀-ۿݐ-ݿ]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
_ANY_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
# "Short or code-like text (for example 'ELEC-0001 stock') is treated as English."
_CODE_LIKE_RE = re.compile(r"^[A-Z0-9\-_. ]+$")

MAX_INPUT_CHARS_DEFAULT = 2000
_OTHER_SCRIPT_THRESHOLD = 0.30  # section 4.1.3: ">30 percent" other-script letters

_MESSAGES = {
    "empty": {
        "en": "Please type a question.",
        "ar": "يرجى كتابة سؤال.",
    },
    "too_long": {
        "en": "Messages are limited to {limit} characters. Please shorten your message and try again.",
        "ar": "الرسائل محدودة بـ {limit} حرفًا. يرجى تقصير رسالتك والمحاولة مرة أخرى.",
    },
    "unsupported_language": {
        "en": "This assistant supports English and Arabic only.",
        "ar": "يدعم هذا المساعد اللغتين العربية والإنجليزية فقط.",
    },
    "injection_high": {
        "en": "I can't follow instructions embedded in a message like that. If you have a business "
        "question about Nakhla Retail Group's sales, inventory or documents, please ask it on its own.",
        "ar": "لا يمكنني تنفيذ تعليمات مضمّنة في رسالة كهذه. إذا كان لديك سؤال عن مبيعات أو مخزون أو "
        "وثائق نخلة للتجزئة، يرجى طرحه بمفرده.",
    },
}


def normalize(text: str) -> str:
    """Section 4.1.1. The normalized text is the only text later stages see."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_BIDI_RE.sub("", text)
    text = _ARABIC_DIACRITIC_RE.sub("", text)
    text = text.translate(_DIGIT_TRANSLATE)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _detect_language(text: str) -> tuple[str | None, float, float]:
    """Script-ratio part of section 4.1.3. Returns (language_or_None, arabic_ratio,
    latin_ratio) measured over letters only. `language` is "en"/"ar" when one script
    clearly dominates or the text is short/code-like (treated as English); None means the
    other-script share exceeds the 30% threshold and the message is unsupported."""
    letters = _ANY_LETTER_RE.findall(text)
    if not letters or _CODE_LIKE_RE.match(text.strip()):
        return "en", 0.0, 0.0
    total = len(letters)
    arabic = len(_ARABIC_LETTER_RE.findall(text))
    latin = len(_LATIN_LETTER_RE.findall(text))
    other = total - arabic - latin
    if other / total > _OTHER_SCRIPT_THRESHOLD:
        return None, arabic / total, latin / total
    return ("ar" if arabic >= latin else "en"), arabic / total, latin / total


@dataclass
class GuardVerdict:
    allowed: bool
    outcome: str
    language: str | None
    flags: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    normalized_chars: int = 0
    normalized_text: str = ""
    response: dict[str, str] | None = None  # {"en": ..., "ar": ...}, set only when blocked

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "outcome": self.outcome,
            "language": self.language,
            "flags": self.flags,
            "matched_rules": self.matched_rules,
            "normalized_chars": self.normalized_chars,
        }


def _content_flags(text: str) -> list[str]:
    """Section 4.1.5: flags that do not block; the router decides on them."""
    flags = []
    if re.search(r"\b(select|insert|update|delete|drop|truncate|alter|create)\b.{0,80}?\b(from|into|table|set)\b", text, re.I):
        flags.append("contains_sql")
    if "```" in text or re.search(r"\b(def |function\s*\(|import \w|=>|;\s*$)", text, re.M):
        flags.append("contains_code")
    if re.search(r"\b(password|api\s*key|credentials?|connection\s+string|secret)\b", text, re.I):
        flags.append("mentions_credentials")
    return flags


def input_guard(text: str, *, max_chars: int = MAX_INPUT_CHARS_DEFAULT) -> GuardVerdict:
    normalized = normalize(text)

    if not normalized:
        return GuardVerdict(False, "empty", None, normalized_chars=0, normalized_text="", response=_MESSAGES["empty"])

    if len(normalized) > max_chars:
        msg = {k: v.format(limit=max_chars) for k, v in _MESSAGES["too_long"].items()}
        return GuardVerdict(False, "too_long", None, normalized_chars=len(normalized), normalized_text=normalized, response=msg)

    language, _ar_ratio, _lat_ratio = _detect_language(normalized)
    if language is None:
        return GuardVerdict(
            False, "unsupported_language", None, normalized_chars=len(normalized),
            normalized_text=normalized, response=_MESSAGES["unsupported_language"],
        )

    level, high_matches, medium_matches = screen_text(normalized)
    flags = _content_flags(normalized)

    if level == "high":
        return GuardVerdict(
            False, "injection_high", language, flags=flags, matched_rules=high_matches,
            normalized_chars=len(normalized), normalized_text=normalized, response=_MESSAGES["injection_high"],
        )

    if level == "medium" or flags:
        return GuardVerdict(
            True, "pass_flagged", language, flags=flags, matched_rules=medium_matches,
            normalized_chars=len(normalized), normalized_text=normalized,
        )

    return GuardVerdict(True, "pass", language, normalized_chars=len(normalized), normalized_text=normalized)


def rescreen_english(question_en: str) -> tuple[bool, list[str]]:
    """Section 4.3's second pass: "the same patterns run a second time on question_en ...
    this catches instructions that only become visible after translation." Returns
    (blocked, high_matches)."""
    level, high_matches, _medium = screen_text(question_en)
    return level == "high", high_matches
