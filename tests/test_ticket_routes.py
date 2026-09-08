from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_complaint_ticket_route():
    response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "type": "complaint",
            "order_id": "ORD1003",
            "description": "物流运输出现异常",
            "contact": "138****0001",
            "client_request_id": "route-complaint-001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["type"] == "complaint"
    assert body["data"]["order_id"] == "ORD1003"
    assert body["data"]["status"] == "pending"


def test_create_human_ticket_route():
    response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "type": "human",
            "content": "我需要人工客服协助",
            "contact": "138****0001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["type"] == "human"
    assert body["data"]["order_id"] is None
    assert body["data"]["status"] == "pending"


def test_create_ticket_route_requires_user_id():
    response = client.post(
        "/api/v1/tickets",
        json={
            "type": "human",
            "content": "需要人工帮助",
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"


def test_complaint_route_requires_description():
    response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "type": "complaint",
            "contact": "138****0001",
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"


def test_human_route_requires_content():
    response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "type": "human",
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"

def test_create_ticket_route_is_idempotent():
    payload = {
        "type": "human",
        "content": "重复提交测试",
        "client_request_id": "route-idempotent-001",
    }

    first_response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json=payload,
    )

    second_response = client.post(
        "/api/v1/tickets",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_ticket_no = first_response.json()["data"]["ticket_no"]
    second_ticket_no = second_response.json()["data"]["ticket_no"]

    assert first_ticket_no == second_ticket_no