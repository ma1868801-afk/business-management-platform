"""Exercises `app/graph/citation_check.py`, in particular the fix for a reproduced false-
rejection bug: the knowledge_base subgraph's no-LLM extractive fallback (see
`app/graph/knowledge_base.py::_llm_answer`) names its own source passage's `title` and
`section_path` when it has no LLM to compose prose ("here is the most relevant excerpt
from <title> (<section>): ..."). Before the fix, `citation_check` only verified claims
against passage *body* text, so a sentence naming its own (correctly retrieved) source
title was wrongly flagged as unsupported and dropped -- the opposite of what the task's
"avoid false rejection of correct information" / "do not weaken factual verification just
to make answers pass" requirements call for (the fix widens what counts as grounded
without touching the number/date/entity checks that catch a genuinely unsupported claim).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.graph.citation_check import citation_check  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


_PASSAGE_BODY = (
    "- Employee ID: EMP-0001\n- Name: Abdulaziz Al-Rashid\n- Title: Chief Executive Officer\n"
    "- Department: Executive Office\n- Location: Head office, Riyadh\n"
    "- Reports to: Board of Directors\n- Hire date: 2015-06-01\n"
    "- Length of service on 2026-10-31: 11 years 4 months\n- Monthly salary: SAR 85,000\n"
    "- Work email: abdulaziz.alrashid@nakhla-retail.example"
)

_PASSAGE = {
    "chunk_id": "EMP-0001#00",
    "doc_id": "EMP-0001",
    "title": "Employee Records: Executive Leadership",
    "section_path": "EMP-0001 Abdulaziz Al-Rashid",
    "text": _PASSAGE_BODY,
}


def main() -> int:
    # The exact fallback-answer shape that exposed the bug (see module docstring).
    draft = (
        'The documents do not provide a composed answer in this environment (no LLM available); '
        f'here is the most relevant excerpt from "{_PASSAGE["title"]}" ({_PASSAGE["section_path"]}): '
        f'{_PASSAGE_BODY}'
    )
    answer, warnings = citation_check(draft, [_PASSAGE])
    check("fallback answer naming its own passage title/section is not rejected", warnings == [], str(warnings))
    check("the full answer text is preserved", answer == draft)

    # A genuinely unsupported fact (a number nowhere in the passage) must still be caught --
    # the fix must not have weakened real grounding checks.
    bad_draft = "The employee's monthly salary is SAR 999,000."
    answer2, warnings2 = citation_check(bad_draft, [_PASSAGE])
    check("an unsupported number is still caught", len(warnings2) == 1, str(warnings2))
    check(
        "the unsupported sentence is dropped, falling back to the no-information message",
        "do not contain the information" in answer2,
        answer2,
    )

    # A supported claim that also happens to mention the document's title should pass too.
    good_draft = f'According to the "{_PASSAGE["title"]}" record, Abdulaziz Al-Rashid is the Chief Executive Officer.'
    answer3, warnings3 = citation_check(good_draft, [_PASSAGE])
    check("a supported claim mentioning the source title passes with no warnings", warnings3 == [], str(warnings3))

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
