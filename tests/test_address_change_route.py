from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_address_change_route_creates_ticket():
    response = client.post(
        "/api/v1/orders/ORD1001/address-change-requests",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "order_id": "ORD1001",
            "new_address": "上海市浦东新区世纪大道100号",
            "confirmed": True,
            "client_request_id": "route-address-001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["type"] == "address_change"
    assert body["data"]["order_id"] == "ORD1001"
    assert body["data"]["status"] == "pending"


def test_address_change_route_requires_user_id():
    response = client.post(
        "/api/v1/orders/ORD1001/address-change-requests",
        json={
            "order_id": "ORD1001",
            "new_address": "上海市浦东新区世纪大道100号",
            "confirmed": True,
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"


def test_address_change_route_rejects_delivered_order():
    response = client.post(
        "/api/v1/orders/ORD1002/address-change-requests",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "order_id": "ORD1002",
            "new_address": "上海市静安区南京西路200号",
            "confirmed": True,
        },
    )

    assert response.status_code == 409

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "ORDER_ALREADY_DELIVERED"


def test_address_change_route_requires_confirmation():
    response = client.post(
        "/api/v1/orders/ORD1001/address-change-requests",
        headers={
            "X-User-Id": "demo-user-001",
        },
        json={
            "order_id": "ORD1001",
            "new_address": "上海市浦东新区世纪大道100号",
            "confirmed": False,
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"