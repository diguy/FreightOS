from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_query_ticket_returns_ticket_status():
    create_response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "type": "human",
            "content": "查询工单状态测试",
            "client_request_id": "query-ticket-001",
        },
    )

    assert create_response.status_code == 200

    ticket_no = create_response.json()["data"]["ticket_no"]

    response = client.get(
        f"/api/v1/tickets/{ticket_no}",
        headers={
            "X-User-Id": "demo-user-001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["ticket_no"] == ticket_no
    assert body["data"]["type"] == "human"
    assert body["data"]["status"] == "pending"


def test_query_ticket_requires_user_id():
    response = client.get(
        "/api/v1/tickets/T-NOT-EXIST",
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"


def test_query_missing_ticket_returns_unified_error():
    response = client.get(
        "/api/v1/tickets/T-NOT-EXIST",
        headers={
            "X-User-Id": "demo-user-001",
        },
    )

    assert response.status_code == 404

    body = response.json()

    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "TICKET_NOT_FOUND"
    assert body["error"]["message"] == "工单不存在或无权访问"


def test_user_cannot_query_another_users_ticket():
    create_response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "type": "human",
            "content": "归属校验测试",
            "client_request_id": "query-ticket-002",
        },
    )

    assert create_response.status_code == 200

    ticket_no = create_response.json()["data"]["ticket_no"]

    response = client.get(
        f"/api/v1/tickets/{ticket_no}",
        headers={
            "X-User-Id": "demo-user-002",
        },
    )

    assert response.status_code == 404

    body = response.json()

    assert body["error"]["code"] == "TICKET_NOT_FOUND"
    assert body["error"]["message"] == "工单不存在或无权访问"