"""Data contracts for session state and multi-turn context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.intent_schema import (
    ActionName,
    IntentEntities,
    IntentName,
    IntentResult,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class SessionTurn(BaseModel):
    """A compact record of one user turn and its parsed intent."""

    model_config = ConfigDict(extra="forbid")

    turn_no: int = Field(ge=1)
    user_message: str = Field(min_length=1, max_length=4000)
    intent_result: IntentResult
    created_at: datetime = Field(default_factory=utc_now)


class SessionState(BaseModel):
    """Persisted state for one conversational session.

    ``slots`` contains values accumulated across turns.  It is deliberately
    separate from ``IntentResult.entities``, which only describes one message.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    user_id: str | None = None
    dify_conversation_id: str | None = None
    turn_no: int = Field(default=0, ge=0)
    active_intent: IntentName = "unknown"
    pending_action: ActionName = "clarify"
    slots: dict[str, str | None] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    awaiting_confirmation: bool = False
    last_tool_result: dict[str, Any] | None = None
    recent_turns: list[SessionTurn] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class EffectiveSessionContext(BaseModel):
    """Current intent plus the state-resolved values used by orchestration."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    turn_no: int
    intent_result: IntentResult
    effective_intent: IntentName
    effective_action: ActionName
    effective_entities: IntentEntities
    effective_missing_slots: list[str] = Field(default_factory=list)
    awaiting_confirmation: bool = False
    should_call_tool: bool = False
    slots: dict[str, str | None] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
