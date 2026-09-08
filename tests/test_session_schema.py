from datetime import datetime, timezone

from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.session_schema import SessionState, SessionTurn


def _tracking_result(order_id=None):
    return IntentResult(
        intent="tracking_query",
        confidence=0.95,
        entities=IntentEntities(order_id=order_id),
        missing_slots=[] if order_id else ["order_id"],
        action="query" if order_id else "collect_info",
        should_call_tool=bool(order_id),
    )


def test_session_state_keeps_structured_turns_and_lifecycle_fields():
    now = datetime.now(timezone.utc)
    state = SessionState(
        session_id="session-001",
        turn_no=1,
        active_intent="tracking_query",
        slots={"order_id": "ORD1001"},
        recent_turns=[
            SessionTurn(
                turn_no=1,
                user_message="查一下 ORD1001",
                intent_result=_tracking_result("ORD1001"),
            )
        ],
        created_at=now,
        updated_at=now,
    )

    assert state.recent_turns[0].intent_result.entities.order_id == "ORD1001"
    assert state.session_id == "session-001"
