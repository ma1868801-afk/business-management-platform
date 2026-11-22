"""Exercises `app/llm/client.py`'s GroqClient reliability wrapper (retries, per-attempt
timeout, the empty-response guard, and "never raises out of the LLM boundary") -- adapted
from the TechNova reference's `src/llm_utils.py safe_invoke`, see that module's docstring.

The real `groq` package and network access aren't available in this sandbox (see
README.md), so these checks drive the retry/timeout machinery directly against a mocked
Groq client that fails on purpose, rather than against the real provider. This is the same
reasoning `tests/test_chroma_store.py` documents for testing `ChromaStore` against a faithful
fake of the real client instead of the real one.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.llm.client import GroqClient  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def _client(max_attempts: int = 4, timeout: float = 1.0) -> GroqClient:
    c = GroqClient(api_key="", model="m")
    c.is_available = True  # bypass the "no groq package" gate so the retry path actually runs
    c._client = MagicMock()
    c.max_attempts = max_attempts
    c.retry_min_wait = 0.01
    c.retry_max_wait = 0.02
    c.timeout_seconds = timeout
    return c


def _ok_response(text: str = '{"ok": true}'):
    resp = MagicMock()
    resp.choices[0].message.content = text
    return resp


def main() -> int:
    # Recovers after transient failures, within max_attempts.
    c = _client(max_attempts=4)
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("simulated transient network failure")
        return _ok_response()

    c._client.chat.completions.create.side_effect = flaky
    result = c.complete_json("sys", "user", call_name="test.flaky")
    check("recovers after 2 transient failures", result.data == {"ok": True})
    check("made exactly 3 attempts (2 failed + 1 success)", calls["n"] == 3, str(calls["n"]))

    # Never raises on permanent failure; exhausts max_attempts; returns a descriptive error.
    c2 = _client(max_attempts=3)
    calls2 = {"n": 0}

    def always_fail(*a, **kw):
        calls2["n"] += 1
        raise ConnectionError("permanent failure")

    c2._client.chat.completions.create.side_effect = always_fail
    result2 = c2.complete_json("sys", "user", call_name="test.always_fail")
    check("permanent failure never raises out of complete_json", result2.data is None)
    check("error names the underlying exception", "ConnectionError" in (result2.error or ""), str(result2.error))
    check("exhausted exactly max_attempts tries", calls2["n"] == 3, str(calls2["n"]))

    # Empty response is treated as a retryable failure, never returned as a successful blank answer.
    c3 = _client(max_attempts=3)
    calls3 = {"n": 0}

    def empty(*a, **kw):
        calls3["n"] += 1
        return _ok_response("   ")

    c3._client.chat.completions.create.side_effect = empty
    result3 = c3.complete_json("sys", "user", call_name="test.empty")
    check("empty response is not returned as data", result3.data is None)
    check("empty response was retried like a transient failure", calls3["n"] == 3, str(calls3["n"]))

    # A per-attempt timeout bounds a hung call instead of letting it block forever.
    c4 = _client(max_attempts=2, timeout=0.05)

    def hangs(*a, **kw):
        time.sleep(5)

    c4._client.chat.completions.create.side_effect = hangs
    t0 = time.monotonic()
    result4 = c4.complete_json("sys", "user", call_name="test.timeout")
    elapsed = time.monotonic() - t0
    check("hung call is bounded by the timeout, not left to run", elapsed < 2.0, f"{elapsed:.2f}s")
    check("timeout failure is reported as an error, not raised", "Timeout" in (result4.error or ""), str(result4.error))

    # Invalid JSON is NOT retried (it's a schema problem, not a transport problem): exactly
    # one call is made, and a caller gets `.error` back to apply its own regeneration logic.
    c5 = _client(max_attempts=5)
    calls5 = {"n": 0}

    def bad_json(*a, **kw):
        calls5["n"] += 1
        return _ok_response("not json at all")

    c5._client.chat.completions.create.side_effect = bad_json
    result5 = c5.complete_json("sys", "user", call_name="test.bad_json")
    check("invalid JSON is reported as data=None", result5.data is None)
    check("invalid JSON is NOT retried (exactly one call)", calls5["n"] == 1, str(calls5["n"]))
    check("invalid JSON error is labeled as such", "invalid_json" in (result5.error or ""), str(result5.error))

    # Unavailable client (no groq package / no api key): no attempts at all, immediate error.
    c6 = GroqClient(api_key="", model="m")
    result6 = c6.complete_json("sys", "user")
    check("unavailable client makes no call and reports llm_unavailable", result6.error == "llm_unavailable")

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
