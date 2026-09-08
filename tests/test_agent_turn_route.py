import json

from fastapi.testclient import TestClient

from app.agent.chat_service import ChatService
from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.session_manager import SessionManager
from app.main import app
from app.routes.chat import get_chat_service


class FakeToolExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"type": "tracking", "data": {"order_no": "ORD1001"}}


class ResultJsonOnlyService(ChatService):
    pass


def test_agent_turn_route_returns_python_state_without_dify_call():
    service = ChatService(
        dify_client=type(
            "NoDify",
            (),
            {"chat": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("should not call Dify"))},
        )(),
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=FakeToolExecutor(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/agent/turn",
            headers={"X-User-Id": "demo-user-001"},
            json={
                "session_id": "agent-session-1",
                "message": "查一下 ORD1001 到哪里了",
                "result_json": json.dumps(
                    {
                        "intent": "tracking_query",
                        "confidence": 0.95,
                        "entities": {
                            "order_id": "ORD1001",
                            "ticket_no": None,
                            "new_address": None,
                            "complaint_content": None,
                            "contact": None,
                        },
                        "missing_slots": [],
                        "action": "query",
                        "should_call_tool": True,
                    }
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["intent_result"]["intent"] == "tracking_query"
    assert body["data"]["tool_result"]["type"] == "tracking"
    assert body["data"]["context"]["should_call_tool"] is True
    assert body["data"]["answer_context"]["effective_session_context"]["session_id"] == (
        "agent-session-1"
    )
