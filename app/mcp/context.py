"""Resolve an MCP session id to the effective stateful tool context."""

from __future__ import annotations

from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.session_manager import SessionManager
from app.agent.session_schema import EffectiveSessionContext


class McpContextError(ValueError):
    """Raised when a session cannot be safely used for an MCP call."""


def context_from_session(
    session_manager: SessionManager,
    *,
    session_id: str,
    user_id: str,
) -> EffectiveSessionContext:
    if not session_id.strip():
        raise McpContextError("缺少 session_id")
    if not user_id.strip():
        raise McpContextError("缺少可信用户身份")

    state = session_manager.get_state(session_id)
    if state is None:
        raise McpContextError("会话不存在或已过期")
    if state.user_id != user_id:
        raise McpContextError("会话不属于当前用户")

    entities = IntentEntities(
        order_id=state.slots.get("order_id"),
        ticket_no=state.slots.get("ticket_no"),
        new_address=state.slots.get("new_address"),
        complaint_content=state.slots.get("complaint_content"),
        contact=state.slots.get("contact"),
    )
    intent_result = IntentResult(
        intent=state.active_intent,
        confidence=0.95,
        entities=entities,
        missing_slots=list(state.missing_slots),
        action=state.pending_action,
        should_call_tool=not state.missing_slots and not state.awaiting_confirmation,
    )
    return EffectiveSessionContext(
        session_id=state.session_id,
        turn_no=state.turn_no,
        intent_result=intent_result,
        effective_intent=state.active_intent,
        effective_action=state.pending_action,
        effective_entities=entities,
        effective_missing_slots=list(state.missing_slots),
        awaiting_confirmation=state.awaiting_confirmation,
        should_call_tool=intent_result.should_call_tool,
        slots=dict(state.slots),
        context={
            "session_id": state.session_id,
            "turn_no": state.turn_no,
            "active_intent": state.active_intent,
        },
    )
