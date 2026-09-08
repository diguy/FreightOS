import pytest

from app.schemas import ComplaintRequest, HumanRequest
from app.services.order_service import init_database
from app.services.ticket_service import (
    create_complaint_ticket,
    create_human_ticket,
)


def test_create_complaint_ticket_with_order(tmp_path):
    database_path = tmp_path / "complaint.db"
    init_database(database_path)

    request = ComplaintRequest(
        order_id="ord1003",
        description="物流运输出现异常",
        contact="138****0001",
    )

    ticket = create_complaint_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["order_id"] == "ORD1003"
    assert ticket["type"] == "complaint"
    assert ticket["status"] == "pending"
    assert "物流运输出现异常" in ticket["content"]
    assert "138****0001" in ticket["content"]


def test_create_complaint_ticket_without_order(tmp_path):
    database_path = tmp_path / "complaint.db"
    init_database(database_path)

    request = ComplaintRequest(
        description="客服态度不好",
        contact="138****0001",
    )

    ticket = create_complaint_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["order_id"] is None
    assert ticket["type"] == "complaint"


def test_complaint_rejects_order_of_another_user(tmp_path):
    database_path = tmp_path / "complaint.db"
    init_database(database_path)

    request = ComplaintRequest(
        order_id="ORD1001",
        description="我要投诉",
        contact="138****0001",
    )

    with pytest.raises(ValueError, match="订单不存在或无权访问"):
        create_complaint_ticket(
            request,
            user_id="demo-user-002",
            database_path=database_path,
        )


def test_create_human_ticket_with_contact(tmp_path):
    database_path = tmp_path / "human.db"
    init_database(database_path)

    request = HumanRequest(
        content="我需要人工客服协助处理问题",
        contact="138****0001",
    )

    ticket = create_human_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["order_id"] is None
    assert ticket["type"] == "human"
    assert ticket["status"] == "pending"
    assert "人工客服协助" in ticket["content"]


def test_create_human_ticket_without_contact(tmp_path):
    database_path = tmp_path / "human.db"
    init_database(database_path)

    request = HumanRequest(
        content="请人工帮我查询这个问题",
    )

    ticket = create_human_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["type"] == "human"
    assert ticket["status"] == "pending"