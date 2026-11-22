"""Per-session state for the FastAPI service (02_architecture.md section 10's
`app/main.py`; limits from 05_security_and_guardrails.md sections 4.4 and 14): the last
`MAX_HISTORY_TURNS` turns for follow-up resolution, the language of the previous turn
(for `detect_and_translate`'s rule 4, 06_evaluation_plan.md section 7), a sliding-window
request-rate counter (20 per minute per session), and a per-session lock enforcing "1
concurrent request at a time" -- a session that is still processing a request rejects a
second one immediately rather than queuing it, exactly as the fixed limit specifies.

Sessions do not share memory (section 4.4), so this is a plain in-process dict; a real
multi-worker deployment would move it to Redis or the database, which is why every method
here is written against a small, swappable interface rather than assuming in-process
dict semantics anywhere else in the codebase.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionState:
    history: list[dict] = field(default_factory=list)  # [{"role": "user"|"assistant", "text": ...}]
    previous_language: Optional[str] = None
    _request_times: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def allow_request(self, now: float, limit_per_minute: int) -> bool:
        """Sliding-window rate check (section 4.4: 20 requests per session per minute)."""
        cutoff = now - 60.0
        self._request_times = [t for t in self._request_times if t >= cutoff]
        if len(self._request_times) >= limit_per_minute:
            return False
        self._request_times.append(now)
        return True

    def history_for_graph(self) -> list[dict]:
        return list(self.history)

    def record_turn(self, user_text: str, answer_text: str, language: str, *, max_turns: int, answer_chars: int) -> None:
        self.history.append({"role": "user", "text": user_text})
        self.history.append({"role": "assistant", "text": answer_text[:answer_chars]})
        # Keep the last `max_turns` user turns (and their paired assistant replies).
        max_entries = max_turns * 2
        if len(self.history) > max_entries:
            self.history = self.history[-max_entries:]
        self.previous_language = language


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._store_lock = threading.Lock()

    def get_or_create(self, session_id: str) -> SessionState:
        with self._store_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState()
            return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        with self._store_lock:
            self._sessions.pop(session_id, None)


def now_seconds() -> float:
    return time.monotonic()
