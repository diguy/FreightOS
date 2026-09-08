"""Storage boundary for conversational session state."""

from __future__ import annotations

from typing import Protocol

from app.agent.session_schema import SessionState


class SessionStore(Protocol):
    """Minimal persistence contract used by ``SessionManager``."""

    def get(self, session_id: str) -> SessionState | None:
        """Return a session snapshot or ``None`` when it does not exist."""

    def save(self, state: SessionState) -> None:
        """Persist a session snapshot."""

    def delete(self, session_id: str) -> None:
        """Delete a session snapshot if it exists."""
