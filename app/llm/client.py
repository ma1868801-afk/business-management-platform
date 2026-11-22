"""Thin wrapper around the Groq client (02_architecture.md section 11: `openai/gpt-oss-120b`
via `GROQ_API_KEY`/`LLM_MODEL`). Every stage that calls the LLM (query rewrite, query
expansion, the LLM re-rank fallback, and the router/subgraph/aggregator nodes) goes through
`complete_json`, which asks for a JSON object back, or `complete_sql`, which requests plain
SQL without provider JSON mode. Both return an `LLMResult` rather than leaking provider
errors to callers, so a caller can apply the documented
degraded-path behavior ("if the LLM call fails or returns invalid JSON, the original query is
used and a warning is added to the trace", 04_rag_design.md section 6.1) instead of crashing
the request.

Reliability (adapted from the TechNova reference's `src/llm_utils.py` `safe_invoke`, which is
the one thing every LLM call in that project goes through): the raw network call is wrapped in
a per-attempt timeout (a hung request can't stall a request indefinitely) and retried with
exponential backoff only on transient failures -- network errors, provider 5xx, timeouts,
or a "successful" call that comes back with empty content. HTTP 4xx and 429 rate-limit
responses are not retried inside the same request. This only covers the
transport: it is a different, lower-level concern than a node's own semantic retry (e.g.
`app/graph/router.py`'s "ask the model to fix its JSON, once"), which still runs on top of
whatever `complete_json` returns -- a transient-retry layer underneath a semantic-retry layer,
not a replacement for it. Retries never apply to a JSON-decode failure: the response came back
fine, it just wasn't the schema asked for, and retrying the identical request is a job for the
caller's own regeneration logic (if any), not for this transport layer.

The `groq` package itself is installable here (confirmed: `pip install groq` succeeds, see
RAG_REFACTOR_REPORT.md section 8) -- it's this sandbox's network egress, not PyPI access,
that's the real constraint: it's allow-listed to a specific set of domains that doesn't
include `api.groq.com` (confirmed directly: `getent hosts api.groq.com` fails to resolve,
the same failure mode as this sandbox's Docker registry access). Without `GROQ_API_KEY` set
at all, `GroqClient.is_available` is `False` and `complete_json` returns the
`llm_unavailable` error immediately (no retries -- there is nothing to retry), which
exercises exactly the pipeline's own documented failure path rather than a special
test-only branch -- the same pattern as `app/tools/postgres_tool.py`'s `driver_unavailable`
fallback. The retry path itself (`tests/test_llm_reliability.py`) is exercised against a
fake client that raises on purpose, standing in for the real network/provider failures
(timeouts, rate limits, 5xx) it targets, since those can't be reproduced against the real
Groq endpoint from here. A real end-to-end call -- a real API key *and* a network path to
`api.groq.com` -- needs an environment without this sandbox's egress restriction; see
RAG_REFACTOR_REPORT.md section 6 for exactly what that would additionally verify.
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Optional

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

try:
    from groq import Groq

    _HAVE_GROQ = True
except ImportError:
    _HAVE_GROQ = False

logger = logging.getLogger("bmp.llm")

# A small shared thread pool just for enforcing a per-attempt timeout around the
# (synchronous) groq SDK call -- mirrors the TechNova reference's `llm_utils._executor`.
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm-call")


class SQLFormatError(ValueError):
    """Raised when an LLM response is not a single plain PostgreSQL query."""


class LLMCallError(RuntimeError):
    """Raised by default graph generators when the provider call itself failed."""


_SQL_FENCE_RE = re.compile(r"^\s*```(?:sql|postgresql)?\s*\n?(.*?)\n?```\s*$", re.I | re.S)


def extract_plain_sql(raw_text: str) -> str:
    """Remove one optional SQL fence and reject JSON/prose before SQL validation.

    The SQL validator remains the security boundary; this helper only enforces the
    generation contract and does not attempt to parse or authorize SQL.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise SQLFormatError("empty SQL response")
    candidate = raw_text.strip()
    if candidate.startswith(("{", "[")):
        raise SQLFormatError("JSON-wrapped SQL is not accepted")
    match = _SQL_FENCE_RE.fullmatch(candidate)
    if match:
        candidate = match.group(1).strip()
    first = re.match(r"^(SELECT|WITH)\b", candidate, re.I)
    if not first:
        raise SQLFormatError("response must start with SELECT or WITH")
    return candidate


class _EmptyLLMResponse(Exception):
    """Raised internally when a call "succeeds" but returns blank content -- treated as a
    transient failure so it goes through the same retry path as a network error, rather than
    silently propagating an empty string as if it were a real answer."""


@dataclass
class LLMResult:
    data: Optional[dict]
    raw_text: Optional[str]
    elapsed_ms: int
    error: Optional[str] = None


# Groq's JSON-object mode is unreliable with GPT-OSS. Use strict JSON Schema
# contracts for every structured production call. All object properties are required
# and nullable where the application treats a value as optional (Groq strict-mode rule).
_STRING_OR_NULL = {"type": ["string", "null"]}
_NUMBER_OR_NULL = {"type": ["number", "null"]}
_INTEGER_OR_NULL = {"type": ["integer", "null"]}
_BOOL_OR_NULL = {"type": ["boolean", "null"]}


def _object_schema(properties: dict, required: Optional[list[str]] = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


_HINTS_SCHEMA = _object_schema({
    "needs_computation": _BOOL_OR_NULL,
    "hypothesis_test": _BOOL_OR_NULL,
    "forecast_requested": _BOOL_OR_NULL,
    "horizon_weeks": _INTEGER_OR_NULL,
    "interval": _NUMBER_OR_NULL,
    "series_level": {"type": ["string", "null"], "enum": ["sku_total", "line_total", None]},
    "with_reorder_advice": _BOOL_OR_NULL,
    "entity": {
        "type": ["object", "null"],
        "properties": {
            "sku": _STRING_OR_NULL,
            "category_name": _STRING_OR_NULL,
            "branch_code": _STRING_OR_NULL,
        },
        "required": ["sku", "category_name", "branch_code"],
        "additionalProperties": False,
    },
    "date_range": _STRING_OR_NULL,
    "metric": _STRING_OR_NULL,
    "assumptions": {
        "type": ["object", "null"],
        "properties": {"promo": _STRING_OR_NULL, "price": _STRING_OR_NULL},
        "required": ["promo", "price"],
        "additionalProperties": False,
    },
})

_JSON_SCHEMAS = {
    "data_analysis.generate_pandas_code": _object_schema({"code": {"type": "string"}}),
    "data_analysis.compose_answer": _object_schema({"answer": {"type": "string"}}),
    "inventory.compose_answer": _object_schema({"answer": {"type": "string"}}),
    "router.decide": _object_schema({
        "decision": {"type": "string", "enum": ["route", "clarify", "direct", "reject"]},
        "subgraphs": {"type": "array", "items": _object_schema({
            "name": {"type": "string", "enum": ["data_analysis", "inventory", "knowledge_base"]},
            "sub_question": {"type": "string"},
            "hints": _HINTS_SCHEMA,
        })},
        "clarification_question": _STRING_OR_NULL,
        "direct_answer": _STRING_OR_NULL,
        "reject_reason": {"type": ["string", "null"], "enum": ["write_request", "restricted_data", "prompt_injection", "off_topic", None]},
        "reason": {"type": "string"},
    }),
    "translate.resolve_english_question": _object_schema({"question_en": {"type": "string"}}),
    "translate.back_translate": _object_schema({"answer_ar": {"type": "string"}}),
}


def _retryable_llm_error(exc: BaseException) -> bool:
    """Retry only transient transport/provider failures, never 4xx or rate limits.

    A 429 is returned immediately: retrying inside the same request burns more time
    while the organization-level TPM window is still exhausted.
    """
    if isinstance(exc, (_EmptyLLMResponse, TimeoutError, ConnectionError, OSError)):
        return True
    if exc.__class__.__name__ in {"APIConnectionError", "APITimeoutError"}:
        return True
    status = getattr(exc, "status_code", None)
    if status == 429:
        return False
    return isinstance(status, int) and status >= 500


class GroqClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        max_attempts: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        retry_min_wait: Optional[float] = None,
        retry_max_wait: Optional[float] = None,
    ):
        self.model = model
        self.is_available = _HAVE_GROQ and bool(api_key)
        self._client = Groq(api_key=api_key) if self.is_available else None  # pragma: no cover

        # Defaults come from app/config.py's Settings so every caller stays in sync without
        # importing settings itself; a test can override any of them directly.
        from app.config import settings as _settings

        self.max_attempts = (max_attempts if max_attempts is not None else _settings.llm_retry_limit) + 1
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _settings.llm_timeout_seconds
        self.retry_min_wait = retry_min_wait if retry_min_wait is not None else _settings.llm_retry_min_wait
        self.retry_max_wait = retry_max_wait if retry_max_wait is not None else _settings.llm_retry_max_wait

    def _call_once(self, system: str, user: str, temperature: float, max_tokens: int, json_mode: bool = True, call_name: str = "llm_call") -> tuple[str, int]:
        """One attempt: submit the blocking SDK call to the thread pool and enforce
        `self.timeout_seconds` around it. Raises on any failure, including an empty
        response -- the retry wrapper around this decides what to do with that."""
        t0 = time.monotonic()
        future = self._executor_submit(system, user, temperature, max_tokens, json_mode, call_name)
        try:
            resp = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"LLM call exceeded {self.timeout_seconds}s timeout") from exc
        text = resp.choices[0].message.content
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if text is None or not str(text).strip():
            raise _EmptyLLMResponse("LLM returned an empty response")
        return text, elapsed_ms

    def _executor_submit(
        self, system: str, user: str, temperature: float, max_tokens: int,
        json_mode: bool = True, call_name: str = "llm_call",
    ):
        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        # GPT-OSS uses max_completion_tokens and low reasoning effort. The smaller
        # reasoning budget leaves more of the completion budget for the requested
        # SQL/code/JSON and materially reduces TPM consumption.
        if self.model.startswith("openai/gpt-oss"):
            kwargs["max_completion_tokens"] = max_tokens
            kwargs["reasoning_effort"] = "low"
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature
        if json_mode:
            schema = _JSON_SCHEMAS.get(call_name)
            if schema is None:
                # Internal/test callers should provide a named contract; this small
                # fallback keeps the boundary strict rather than reverting to JSON mode.
                schema = _object_schema({"response": {"type": "string"}})
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": re.sub(r"[^a-zA-Z0-9_]", "_", call_name)[:64],
                    "strict": True,
                    "schema": schema,
                },
            }
        return _executor.submit(self._client.chat.completions.create, **kwargs)

    def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
        call_name: str = "llm_call",
    ) -> LLMResult:
        """Requests a strict JSON-Schema completion. Returns `LLMResult.data = None` (with `.error`
        set) on anything that goes wrong, rather than raising, so callers can apply the
        spec's documented fallback behavior uniformly. `call_name` identifies the calling
        stage (e.g. "rag.rewrite_query", "router.decide") in retry/failure log lines."""
        t0 = time.monotonic()
        if not self.is_available:
            return LLMResult(data=None, raw_text=None, elapsed_ms=0, error="llm_unavailable")

        retrying_call = retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=1, min=self.retry_min_wait, max=self.retry_max_wait),
            retry=retry_if_exception(_retryable_llm_error),
            reraise=True,
            before_sleep=self._log_retry(call_name),
        )(self._call_once)

        try:  # pragma: no cover - needs network + the groq package
            text, _inner_elapsed_ms = retrying_call(system, user, temperature, max_tokens, True, call_name)
        except Exception as e:  # noqa: BLE001 - never raise out of the LLM boundary
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "%s failed after %d attempt(s): %s",
                call_name,
                self.max_attempts,
                e,
                extra={"extra_fields": {"call_name": call_name, "attempts": self.max_attempts, "elapsed_ms": elapsed_ms}},
            )
            return LLMResult(data=None, raw_text=None, elapsed_ms=elapsed_ms, error=f"{type(e).__name__}: {e}")

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return LLMResult(
                    data=None, raw_text=text, elapsed_ms=elapsed_ms,
                    error="invalid_json_shape: expected a JSON object",
                )
            return LLMResult(data=parsed, raw_text=text, elapsed_ms=elapsed_ms)
        except json.JSONDecodeError as e:
            # Not retried here (see module docstring): the call succeeded, the response just
            # wasn't valid JSON. A caller with its own regeneration logic (e.g. the router's
            # "ask the model to fix its JSON, once") handles this; one that doesn't falls back
            # to its documented default, which is also the right behavior for this case.
            logger.warning(
                "%s returned invalid JSON: %s",
                call_name,
                e,
                extra={"extra_fields": {"call_name": call_name, "elapsed_ms": elapsed_ms}},
            )
            return LLMResult(data=None, raw_text=text, elapsed_ms=elapsed_ms, error=f"invalid_json: {e}")

    def complete_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 700,
        call_name: str = "llm_call",
    ) -> LLMResult:
        """TechNova-style plain-text completion, with the same timeout/retry boundary.

        RAG rewrite, expansion and grounded answer generation must not force the
        provider into JSON-object mode; their output contracts are plain text (the
        expansion stage contains a JSON array that the caller parses locally).
        """
        t0 = time.monotonic()
        if not self.is_available:
            return LLMResult(data=None, raw_text=None, elapsed_ms=0, error="llm_unavailable")
        retrying_call = retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=1, min=self.retry_min_wait, max=self.retry_max_wait),
            retry=retry_if_exception(_retryable_llm_error),
            reraise=True,
            before_sleep=self._log_retry(call_name),
        )(self._call_once)
        try:
            text, _ = retrying_call(system, user, temperature, max_tokens, False, call_name)
        except Exception as e:  # noqa: BLE001 - keep failures inside the LLM boundary
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "%s failed after %d attempt(s): %s",
                call_name, self.max_attempts, e,
                extra={"extra_fields": {"call_name": call_name, "attempts": self.max_attempts, "elapsed_ms": elapsed_ms}},
            )
            return LLMResult(data=None, raw_text=None, elapsed_ms=elapsed_ms, error=f"{type(e).__name__}: {e}")
        return LLMResult(data=None, raw_text=text.strip(), elapsed_ms=int((time.monotonic() - t0) * 1000))

    def complete_sql(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        call_name: str = "sql_generation",
    ) -> LLMResult:
        """Generate plain SQL without enabling the provider's JSON response mode.

        Invalid format is returned as an error plus the original text so the caller's
        existing SQL validator/re-generation loop can reject it and request a correction.
        """
        result = self.complete_text(
            system, user, temperature=temperature, max_tokens=max_tokens, call_name=call_name
        )
        if result.raw_text is None:
            return result
        try:
            cleaned = extract_plain_sql(result.raw_text)
        except SQLFormatError as exc:
            # Do not log the model's raw output: it may contain sensitive query content.
            logger.warning(
                "%s returned invalid SQL format: %s",
                call_name, exc,
                extra={"extra_fields": {
                    "call_name": call_name,
                    "error_code": "invalid_sql_format",
                    "elapsed_ms": result.elapsed_ms,
                }},
            )
            return LLMResult(
                data=None, raw_text=result.raw_text, elapsed_ms=result.elapsed_ms,
                error=f"invalid_sql_format: {exc}",
            )
        return LLMResult(data=None, raw_text=cleaned, elapsed_ms=result.elapsed_ms)

    @staticmethod
    def _log_retry(call_name: str):
        def _before_sleep(retry_state: Any) -> None:
            exc = retry_state.outcome.exception()
            logger.warning(
                "%s attempt %d failed, retrying: %s",
                call_name,
                retry_state.attempt_number,
                exc,
                extra={"extra_fields": {"call_name": call_name, "attempt": retry_state.attempt_number}},
            )

        return _before_sleep
