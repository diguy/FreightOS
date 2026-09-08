from fastapi.testclient import TestClient
from app.services.order_service import get_order_tracking
from app.main import app
from app.database import get_connection
from app.services.order_service import init_database
from app.database import get_connection
from app.services.order_service import init_database


def test_health_check_returns_success():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_dependency_health_check_returns_dependency_status(monkeypatch):
    monkeypatch.setenv("APP_DATABASE", "sqlite")
    monkeypatch.setenv("SESSION_STORE", "memory")

    with TestClient(app) as client:
        response = client.get("/health/dependencies")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["database_backend"] == "sqlite"
    assert body["mysql"]["skipped"] is True
    assert body["redis"]["ok"] is True


def test_query_existing_order_returns_tracking_events():
    with TestClient(app) as client:
        response = client.get("/api/orders/ORD1001/tracking")

    assert response.status_code == 200
    body = response.json()
    assert body["order_no"] == "ORD1001"
    assert body["carrier"] == "顺丰速运"
    assert body["tracking_events"][0]["event_time"] == "2026-08-29 12:10:00"


def test_query_order_number_is_case_insensitive():
    with TestClient(app) as client:
        response = client.get("/api/orders/ord1001/tracking")

    assert response.status_code == 200
    assert response.json()["order_no"] == "ORD1001"


def test_query_missing_order_returns_not_found():
    with TestClient(app) as client:
        response = client.get("/api/orders/ORD9999/tracking")

    assert response.status_code == 404
    assert "没有找到订单" in response.json()["detail"]


def test_database_initialization_is_idempotent():
    init_database()
    init_database()

    connection = get_connection()
    try:
        order_count = connection.execute(
            "SELECT COUNT(*) AS count FROM orders"
        ).fetchone()["count"]
        event_count = connection.execute(
            "SELECT COUNT(*) AS count FROM tracking_events"
        ).fetchone()["count"]
    finally:
        connection.close()

    assert order_count == 3
    assert event_count == 5

def test_service_can_use_independent_database(tmp_path):
    test_database_path = tmp_path / "test.db"

    init_database(test_database_path)
    result = get_order_tracking("ORD1001", test_database_path)

    assert result is not None
    assert result["order_no"] == "ORD1001"

def test_v1_query_existing_order_uses_unified_response():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/orders/ORD1001/tracking",
            headers={"X-User-Id": "demo-user-001"},
        )


def test_v1_query_missing_order_uses_unified_error_response():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/orders/ORD9999/tracking",
            headers={"X-User-Id": "demo-user-001"},
        )

    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "ORDER_NOT_FOUND"
    assert body["error"]["message"] == "订单不存在或无权访问"

def test_v1_query_order_with_wrong_user_returns_access_denied():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/orders/ORD1001/tracking",
            headers={"X-User-Id": "demo-user-002"},
        )

    assert response.status_code == 403

    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "ORDER_ACCESS_DENIED"
    assert body["error"]["message"] == "订单不存在或无权访问"


def test_v1_query_order_without_user_id_returns_missing_field():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/orders/ORD1001/tracking",
        )

    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELD"


def test_v1_missing_order_with_user_id_returns_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/orders/ORD9999/tracking",
            headers={"X-User-Id": "demo-user-001"},
        )

    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "ORDER_NOT_FOUND"

def test_order_status_uses_stable_internal_code():
    from app.repositories.order_repository import find_order_tracking

    result = find_order_tracking("ORD1001")

    assert result is not None
    assert result["status"] == "in_transit"

def test_delivered_order_uses_delivered_status_code():
    from app.repositories.order_repository import find_order_tracking

    result = find_order_tracking("ORD1002")

    assert result is not None
    assert result["status"] == "delivered"

def test_tickets_table_is_initialized():
    init_database()

    connection = get_connection()
    try:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'tickets'
            """
        ).fetchone()
    finally:
        connection.close()

    assert table is not None
    assert table["name"] == "tickets"

def test_tickets_table_has_expected_columns():
    init_database()

    connection = get_connection()
    try:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(tickets)"
            ).fetchall()
        }
    finally:
        connection.close()

    assert {
        "ticket_no",
        "user_id",
        "order_id",
        "type",
        "content",
        "status",
        "client_request_id",
        "created_at",
    }.issubset(columns)
