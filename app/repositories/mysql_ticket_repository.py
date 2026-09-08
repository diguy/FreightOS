"""MySQL ticket repository with the same return contract as SQLite."""

from __future__ import annotations

from typing import Any


TICKET_COLUMNS = """
    ticket_no, user_id, order_id, type, content, status,
    client_request_id, created_at
"""


def insert_ticket(
    connection: Any,
    *,
    ticket_no: str,
    user_id: str,
    order_id: str | None,
    ticket_type: str,
    content: str,
    status: str = "pending",
    client_request_id: str | None = None,
) -> dict:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO tickets (
                ticket_no, user_id, order_id, type, content, status,
                client_request_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ticket_no,
                user_id,
                order_id,
                ticket_type,
                content,
                status,
                client_request_id,
            ),
        )
        cursor.execute(
            f"SELECT {TICKET_COLUMNS} FROM tickets WHERE ticket_no = %s",
            (ticket_no,),
        )
        ticket = cursor.fetchone()
        if ticket is None:
            raise RuntimeError("工单写入后无法读取")
        return dict(ticket)
    finally:
        cursor.close()


def find_ticket_by_ticket_no(connection: Any, ticket_no: str) -> dict | None:
    return _find_one(connection, "ticket_no = %s", (ticket_no,))


def find_ticket_by_client_request_id(
    connection: Any,
    *,
    user_id: str,
    client_request_id: str,
) -> dict | None:
    return _find_one(
        connection,
        "user_id = %s AND client_request_id = %s",
        (user_id, client_request_id),
    )


def update_ticket_status(
    connection: Any,
    *,
    ticket_no: str,
    status: str,
) -> dict | None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE tickets SET status = %s WHERE ticket_no = %s",
            (status, ticket_no),
        )
        if cursor.rowcount == 0:
            return None
    finally:
        cursor.close()
    return find_ticket_by_ticket_no(connection, ticket_no)


def _find_one(connection: Any, condition: str, params: tuple[str, ...]) -> dict | None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT {TICKET_COLUMNS} FROM tickets WHERE {condition}",
            params,
        )
        ticket = cursor.fetchone()
        return dict(ticket) if ticket is not None else None
    finally:
        cursor.close()
