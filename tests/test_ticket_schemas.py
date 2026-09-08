import pytest
from pydantic import ValidationError

from app.schemas import TicketCreateRequest, TicketResponse


def test_ticket_create_request_accepts_valid_data():
    request = TicketCreateRequest(
        order_id="ORD1001",
        type="complaint",
        content="物流长时间没有更新",
        client_request_id="req-001",
    )

    assert request.order_id == "ORD1001"
    assert request.type == "complaint"
    assert request.content == "物流长时间没有更新"


def test_ticket_create_request_allows_missing_order_id():
    request = TicketCreateRequest(
        type="human",
        content="需要人工客服协助",
    )

    assert request.order_id is None
    assert request.client_request_id is None


def test_ticket_create_request_rejects_unknown_type():
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            type="refund",
            content="申请退款",
        )


def test_ticket_create_request_rejects_empty_content():
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            type="complaint",
            content="",
        )


def test_ticket_response_contains_persisted_fields():
    response = TicketResponse(
        ticket_no="T202608300001",
        user_id="demo-user-001",
        order_id="ORD1001",
        type="complaint",
        content="物流异常",
        status="pending",
        client_request_id="req-001",
        created_at="2026-08-30 21:00:00",
    )

    assert response.ticket_no == "T202608300001"
    assert response.status == "pending"