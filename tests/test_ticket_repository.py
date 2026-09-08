import sqlite3
from typing import Literal

from pydantic import BaseModel, Field
import pytest

from app.database import get_connection
from app.repositories.ticket_repository import (
    find_ticket_by_client_request_id,
    find_ticket_by_ticket_no,
    insert_ticket,
)
from app.services.order_service import init_database


def create_test_connection(tmp_path) -> sqlite3.Connection:
    database_path = tmp_path / "ticket_repository.db"
    init_database(database_path)
    return get_connection(database_path)


def test_insert_ticket_returns_saved_ticket(tmp_path):
    connection = create_test_connection(tmp_path)

    try:
        ticket = insert_ticket(
            connection,
            ticket_no="T202608300001",
            user_id="demo-user-001",
            order_id="ORD1001",
            ticket_type="complaint",
            content="物流长时间没有更新",
            client_request_id="req-001",
        )
        connection.commit()

        assert ticket["ticket_no"] == "T202608300001"
        assert ticket["user_id"] == "demo-user-001"
        assert ticket["order_id"] == "ORD1001"
        assert ticket["type"] == "complaint"
        assert ticket["status"] == "pending"
        assert ticket["client_request_id"] == "req-001"
        assert ticket["created_at"] is not None
    finally:
        connection.close()


def test_find_ticket_by_ticket_no_returns_ticket(tmp_path):
    connection = create_test_connection(tmp_path)

    try:
        insert_ticket(
            connection,
            ticket_no="T202608300002",
            user_id="demo-user-001",
            order_id=None,
            ticket_type="human",
            content="需要人工客服协助",
        )
        connection.commit()

        ticket = find_ticket_by_ticket_no(
            connection,
            "T202608300002",
        )

        assert ticket is not None
        assert ticket["type"] == "human"
        assert ticket["status"] == "pending"
    finally:
        connection.close()


def test_find_ticket_by_client_request_id_returns_existing_ticket(tmp_path):
    connection = create_test_connection(tmp_path)

    try:
        insert_ticket(
            connection,
            ticket_no="T202608300003",
            user_id="demo-user-001",
            order_id="ORD1001",
            ticket_type="address_change",
            content="改为上海市浦东新区",
            client_request_id="req-003",
        )
        connection.commit()

        ticket = find_ticket_by_client_request_id(
            connection,
            user_id="demo-user-001",
            client_request_id="req-003",
        )

        assert ticket is not None
        assert ticket["ticket_no"] == "T202608300003"
    finally:
        connection.close()


def test_same_user_cannot_reuse_client_request_id(tmp_path):
    connection = create_test_connection(tmp_path)

    try:
        insert_ticket(
            connection,
            ticket_no="T202608300004",
            user_id="demo-user-001",
            order_id="ORD1001",
            ticket_type="complaint",
            content="第一次投诉",
            client_request_id="req-004",
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            insert_ticket(
                connection,
                ticket_no="T202608300005",
                user_id="demo-user-001",
                order_id="ORD1001",
                ticket_type="complaint",
                content="重复投诉",
                client_request_id="req-004",
            )
    finally:
        connection.close()