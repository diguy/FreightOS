import json

from fastapi.testclient import TestClient

from app.agent.chat_service import ChatService
from app.agent.business_tool_executor import BusinessToolExecutor
from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.session_manager import SessionManager
from app.main import app
from app.routes.chat import get_chat_service


def _payload():
    return json.dumps(
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
    )


class FakeDify:
    def chat(self, **kwargs):
        return {
            "answer": "正在查询",
            "conversation_id": "conv-route",
            "result_json": _payload(),
        }


def test_chat_route_runs_full_chain_with_injected_service():
    service = ChatService(
        dify_client=FakeDify(),
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=BusinessToolExecutor(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/chat",
            headers={"X-User-Id": "demo-user-001"},
            json={
                "session_id": "route-session",
                "message": "查一下 ORD1001 到哪里了",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["intent_result"]["intent"] == "tracking_query"
    assert body["data"]["tool_result"]["type"] == "tracking"
    assert body["data"]["tool_result"]["data"]["order_no"] == "ORD1001"


def test_chat_route_requires_user_identity():
    response = TestClient(app).post(
        "/api/v1/chat",
        json={"session_id": "s", "message": "你好"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_REQUIRED_FIELD"
