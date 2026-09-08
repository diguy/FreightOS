import sqlite3


TICKET_COLUMNS = """
    ticket_no,
    user_id,
    order_id,
    type,
    content,
    status,
    client_request_id,
    created_at
"""


def insert_ticket(
    connection: sqlite3.Connection,
    *,
    ticket_no: str,
    user_id: str,
    order_id: str | None,
    ticket_type: str,
    content: str,
    status: str = "pending",
    client_request_id: str | None = None,
) -> dict:
    """插入工单，但不提交事务。事务由 Service 控制。"""
    connection.execute(
        """
        INSERT INTO tickets (
            ticket_no,
            user_id,
            order_id,
            type,
            content,
            status,
            client_request_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
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

    ticket = connection.execute(
        f"""
        SELECT {TICKET_COLUMNS}
        FROM tickets
        WHERE ticket_no = ?
        """,
        (ticket_no,),
    ).fetchone()

    if ticket is None:
        raise RuntimeError("工单写入后无法读取")

    return dict(ticket)


def find_ticket_by_ticket_no(
    connection: sqlite3.Connection,
    ticket_no: str,
) -> dict | None:
    """根据后端生成的工单号查询工单。"""
    ticket = connection.execute(
        f"""
        SELECT {TICKET_COLUMNS}
        FROM tickets
        WHERE ticket_no = ?
        """,
        (ticket_no,),
    ).fetchone()

    return dict(ticket) if ticket is not None else None


def find_ticket_by_client_request_id(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    client_request_id: str,
) -> dict | None:
    """查询当前用户是否已经使用过指定幂等请求号。"""
    ticket = connection.execute(
        f"""
        SELECT {TICKET_COLUMNS}
        FROM tickets
        WHERE user_id = ?
          AND client_request_id = ?
        """,
        (user_id, client_request_id),
    ).fetchone()

    return dict(ticket) if ticket is not None else None

def update_ticket_status(
    connection: sqlite3.Connection,
    *,
    ticket_no: str,
    status: str,
) -> dict | None:
    """更新工单状态，但不提交事务。"""

    cursor = connection.execute(
        """
        UPDATE tickets
        SET status = ?
        WHERE ticket_no = ?
        """,
        (status, ticket_no),
    )

    if cursor.rowcount == 0:
        return None

    return find_ticket_by_ticket_no(connection, ticket_no)