import pytest

from app.database import get_connection
from app.schemas import TicketCreateRequest
from app.services.order_service import init_database
from app.services.ticket_service import (
    create_ticket,
    update_ticket_status_by_service,
)


def create_pending_ticket(tmp_path):
    database_path = tmp_path / "ticket_status.db"
    init_database(database_path)

    ticket = create_ticket(
        TicketCreateRequest(
            type="human",
            content="需要人工客服协助",
        ),
        user_id="demo-user-001",
        database_path=database_path,
    )

    return database_path, ticket


def test_pending_ticket_can_move_to_processing(tmp_path):
    database_path, ticket = create_pending_ticket(tmp_path)

    updated_ticket = update_ticket_status_by_service(
        ticket["ticket_no"],
        "processing",
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert updated_ticket["status"] == "processing"


def test_processing_ticket_can_move_to_completed(tmp_path):
    database_path, ticket = create_pending_ticket(tmp_path)

    update_ticket_status_by_service(
        ticket["ticket_no"],
        "processing",
        user_id="demo-user-001",
        database_path=database_path,
    )

    updated_ticket = update_ticket_status_by_service(
        ticket["ticket_no"],
        "completed",
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert updated_ticket["status"] == "completed"


def test_pending_ticket_cannot_move_directly_to_completed(tmp_path):
    database_path, ticket = create_pending_ticket(tmp_path)

    with pytest.raises(ValueError, match="不允许"):
        update_ticket_status_by_service(
            ticket["ticket_no"],
            "completed",
            user_id="demo-user-001",
            database_path=database_path,
        )


def test_completed_ticket_cannot_move_again(tmp_path):
    database_path, ticket = create_pending_ticket(tmp_path)

    update_ticket_status_by_service(
        ticket["ticket_no"],
        "processing",
        user_id="demo-user-001",
        database_path=database_path,
    )

    update_ticket_status_by_service(
        ticket["ticket_no"],
        "completed",
        user_id="demo-user-001",
        database_path=database_path,
    )

    with pytest.raises(ValueError, match="不允许"):
        update_ticket_status_by_service(
            ticket["ticket_no"],
            "processing",
            user_id="demo-user-001",
            database_path=database_path,
        )


def test_user_cannot_update_another_users_ticket(tmp_path):
    database_path, ticket = create_pending_ticket(tmp_path)

    with pytest.raises(ValueError, match="无权访问"):
        update_ticket_status_by_service(
            ticket["ticket_no"],
            "processing",
            user_id="demo-user-002",
            database_path=database_path,
        )


def test_missing_ticket_cannot_be_updated(tmp_path):
    database_path, _ = create_pending_ticket(tmp_path)

    with pytest.raises(ValueError, match="工单不存在"):
        update_ticket_status_by_service(
            "T-NOT-EXIST",
            "processing",
            user_id="demo-user-001",
            database_path=database_path,
        )