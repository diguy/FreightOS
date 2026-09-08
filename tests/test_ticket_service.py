import pytest
from app.database import get_connection
from app.schemas import TicketCreateRequest
from app.services.order_service import init_database
from app.services.ticket_service import create_ticket, get_ticket


def test_create_complaint_ticket(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    request = TicketCreateRequest(
        order_id="ORD1003",
        type="complaint",
        content="物流运输出现异常",
    )

    ticket = create_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["ticket_no"].startswith("T")
    assert ticket["user_id"] == "demo-user-001"
    assert ticket["order_id"] == "ORD1003"
    assert ticket["type"] == "complaint"
    assert ticket["status"] == "pending"


def test_create_human_ticket_without_order_id(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    request = TicketCreateRequest(
        type="human",
        content="我需要人工客服帮助",
    )

    ticket = create_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["order_id"] is None
    assert ticket["type"] == "human"
    assert ticket["status"] == "pending"


def test_address_change_requires_order_id(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    request = TicketCreateRequest(
        type="address_change",
        content="请修改收货地址",
    )

    with pytest.raises(ValueError, match="必须提供订单号"):
        create_ticket(
            request,
            user_id="demo-user-001",
            database_path=database_path,
        )

def test_same_client_request_id_returns_same_ticket(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    request = TicketCreateRequest(
        order_id="ORD1001",
        type="complaint",
        content="物流长时间没有更新",
        client_request_id="req-idempotent-001",
    )

    first_ticket = create_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    second_ticket = create_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert second_ticket["ticket_no"] == first_ticket["ticket_no"]

    connection = get_connection(database_path)
    try:
        count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM tickets
            WHERE client_request_id = ?
            """,
            ("req-idempotent-001",),
        ).fetchone()["count"]
    finally:
        connection.close()

    assert count == 1


def test_same_client_request_id_is_scoped_by_user(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    request = TicketCreateRequest(
        type="human",
        content="需要人工客服",
        client_request_id="req-idempotent-002",
    )

    first_ticket = create_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    second_ticket = create_ticket(
        request,
        user_id="demo-user-002",
        database_path=database_path,
    )

    assert second_ticket["ticket_no"] != first_ticket["ticket_no"]


def test_get_ticket_returns_status_for_owner_and_normalizes_ticket_number(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    created = create_ticket(
        TicketCreateRequest(type="human", content="查询工单状态"),
        user_id="demo-user-001",
        database_path=database_path,
    )

    ticket = get_ticket(
        f"  {created['ticket_no'].lower()} ",
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["ticket_no"] == created["ticket_no"]
    assert ticket["status"] == "pending"


def test_get_ticket_hides_another_users_ticket(tmp_path):
    database_path = tmp_path / "ticket_service.db"
    init_database(database_path)

    created = create_ticket(
        TicketCreateRequest(type="human", content="归属校验"),
        user_id="demo-user-001",
        database_path=database_path,
    )

    with pytest.raises(ValueError, match="不存在或无权访问"):
        get_ticket(
            created["ticket_no"],
            user_id="demo-user-002",
            database_path=database_path,
        )
