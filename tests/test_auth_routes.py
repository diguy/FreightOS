from fastapi.testclient import TestClient

from app.main import app


def test_demo_phone_can_request_verification_code():
    response = TestClient(app).post(
        "/api/v1/auth/send-code",
        json={"phone": "13800000001"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["dev_code"] == "123456"


def test_demo_phone_can_login_with_fixed_code():
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"phone": "13800000001", "code": "123456"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["user_id"] == "demo-user-001"


def test_login_rejects_invalid_verification_code():
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"phone": "13800000001", "code": "000000"},
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == "INVALID_CODE"
