from datetime import datetime, timedelta, timezone

from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.session_schema import SessionState


def test_store_returns_defensive_copies():
    store = InMemorySessionStore()
    state = SessionState(session_id="session-001", slots={"order_id": "ORD1001"})
    store.save(state)

    loaded = store.get("session-001")
    loaded.slots["order_id"] = "ORD9999"

    assert store.get("session-001").slots["order_id"] == "ORD1001"


def test_expired_sessions_are_not_returned():
    store = InMemorySessionStore()
    state = SessionState(
        session_id="expired",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    store.save(state)

    assert store.get("expired") is None
