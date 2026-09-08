"""Thread-safe in-memory session storage for local development and tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock

from app.agent.session_schema import SessionState


class InMemorySessionStore:
    """Small TTL-aware store implementing the session persistence boundary."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            self._purge_expired()
            state = self._sessions.get(session_id)
            return deepcopy(state) if state is not None else None

    def save(self, state: SessionState) -> None:
        with self._lock:
            self._purge_expired()
            self._sessions[state.session_id] = deepcopy(state)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear(self) -> None:
        """Clear all state; useful for tests and local development."""

        with self._lock:
            self._sessions.clear()

    def _purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired_ids = [
            session_id
            for session_id, state in self._sessions.items()
            if state.expires_at is not None and state.expires_at <= now
        ]
        for session_id in expired_ids:
            del self._sessions[session_id]
