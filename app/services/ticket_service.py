import uuid
from pathlib import Path
import sqlite3
import pymysql
from app.database import DATABASE_PATH, get_connection
from app.repositories.order_repository import find_order_tracking
from app.repositories.ticket_repository import (
    find_ticket_by_client_request_id,
    find_ticket_by_ticket_no,
    insert_ticket,
    update_ticket_status,
)
from app.database_backend import use_mysql
from app.mysql_database import get_mysql_connection
from app.repositories.mysql_order_repository import (
    find_order_tracking as find_mysql_order_tracking,
)
from app.repositories.mysql_ticket_repository import (
    find_ticket_by_client_request_id as find_mysql_ticket_by_client_request_id,
    find_ticket_by_ticket_no as find_mysql_ticket_by_ticket_no,
    insert_ticket as insert_mysql_ticket,
    update_ticket_status as update_mysql_ticket_status,
)
from app.schemas import (
    AddressChangeRequest,
    ComplaintRequest,
    HumanRequest,
    TicketCreateRequest,
)


def generate_ticket_no() -> str:
    """生成不暴露数据库自增 ID 的工单号。"""
    return f"T{uuid.uuid4().hex[:16].upper()}"


def _find_order_tracking(order_no: str, database_path: Path) -> dict | None:
    if use_mysql(database_path):
        connection = get_mysql_connection()
        try:
            return find_mysql_order_tracking(connection, order_no)
        finally:
            connection.close()
    return find_order_tracking(order_no, database_path)


def create_ticket(
    request: TicketCreateRequest,
    *,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """根据请求创建工单，并保证客户端请求幂等。"""

    if request.type == "address_change" and not request.order_id:
        raise ValueError("改址工单必须提供订单号")

    mysql_backend = use_mysql(database_path)
    connection = get_mysql_connection() if mysql_backend else get_connection(database_path)
    find_by_request = (
        find_mysql_ticket_by_client_request_id
        if mysql_backend
        else find_ticket_by_client_request_id
    )
    insert = insert_mysql_ticket if mysql_backend else insert_ticket

    try:
        if request.client_request_id:
            existing_ticket = find_by_request(
                connection,
                user_id=user_id,
                client_request_id=request.client_request_id,
            )

            if existing_ticket is not None:
                return existing_ticket

        ticket = insert(
            connection,
            ticket_no=generate_ticket_no(),
            user_id=user_id,
            order_id=request.order_id,
            ticket_type=request.type,
            content=request.content,
            client_request_id=request.client_request_id,
        )

        connection.commit()
        return ticket

    except (sqlite3.IntegrityError, pymysql.IntegrityError):
        connection.rollback()

        if request.client_request_id:
            existing_ticket = find_by_request(
                connection,
                user_id=user_id,
                client_request_id=request.client_request_id,
            )

            if existing_ticket is not None:
                return existing_ticket

        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def create_address_change_ticket(
    request: AddressChangeRequest,
    *,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """创建改址申请工单。"""

    if not request.confirmed:
        raise ValueError("用户尚未确认改址申请")

    order_id = request.order_id.upper()
    order = _find_order_tracking(order_id, database_path)

    if order is None:
        raise ValueError("订单不存在或无权访问")

    if order["user_id"] != user_id:
        raise ValueError("订单不存在或无权访问")

    if order["status"] in {"delivered", "cancelled"}:
        raise ValueError("当前订单状态不允许改址")

    ticket_request = TicketCreateRequest(
        order_id=order_id,
        type="address_change",
        content=f"申请将收货地址修改为：{request.new_address}",
        client_request_id=request.client_request_id,
    )

    return create_ticket(
        ticket_request,
        user_id=user_id,
        database_path=database_path,
    )

def create_complaint_ticket(
    request: ComplaintRequest,
    *,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """创建投诉工单。"""

    order_id = request.order_id.upper() if request.order_id else None

    if order_id is not None:
        order = _find_order_tracking(order_id, database_path)

        if order is None:
            raise ValueError("订单不存在或无权访问")

        if order["user_id"] != user_id:
            raise ValueError("订单不存在或无权访问")

    content = (
        f"投诉内容：{request.description}\n"
        f"联系方式：{request.contact}"
    )

    ticket_request = TicketCreateRequest(
        order_id=order_id,
        type="complaint",
        content=content,
        client_request_id=request.client_request_id,
    )

    return create_ticket(
        ticket_request,
        user_id=user_id,
        database_path=database_path,
    )


def create_human_ticket(
    request: HumanRequest,
    *,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """创建人工客服工单。"""

    content = request.content

    if request.contact:
        content = (
            f"{content}\n"
            f"联系方式：{request.contact}"
        )

    ticket_request = TicketCreateRequest(
        type="human",
        content=content,
        client_request_id=request.client_request_id,
    )

    return create_ticket(
        ticket_request,
        user_id=user_id,
        database_path=database_path,
    )

ALLOWED_TICKET_STATUS_TRANSITIONS = {
    "pending": {"processing"},
    "processing": {"completed", "rejected", "cancelled"},
    "completed": set(),
    "rejected": set(),
    "cancelled": set(),
}


def update_ticket_status_by_service(
    ticket_no: str,
    new_status: str,
    *,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """按照允许的状态路径更新工单。"""

    mysql_backend = use_mysql(database_path)
    connection = get_mysql_connection() if mysql_backend else get_connection(database_path)
    try:
        find_ticket = (
            find_mysql_ticket_by_ticket_no
            if mysql_backend
            else find_ticket_by_ticket_no
        )
        update_ticket = (
            update_mysql_ticket_status
            if mysql_backend
            else update_ticket_status
        )
        ticket = find_ticket(
            connection,
            ticket_no,
        )

        if ticket is None:
            raise ValueError("工单不存在")

        if ticket["user_id"] != user_id:
            raise ValueError("工单不存在或无权访问")

        current_status = ticket["status"]
        allowed_statuses = ALLOWED_TICKET_STATUS_TRANSITIONS[
            current_status
        ]

        if new_status not in allowed_statuses:
            raise ValueError(
                f"不允许从 {current_status} 流转到 {new_status}"
            )

        updated_ticket = update_ticket(
            connection,
            ticket_no=ticket_no,
            status=new_status,
        )

        if updated_ticket is None:
            raise RuntimeError("工单状态更新失败")

        connection.commit()
        return updated_ticket

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_ticket(
    ticket_no: str,
    *,
    user_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """查询当前用户拥有的工单。"""

    ticket_no = ticket_no.strip().upper()
    mysql_backend = use_mysql(database_path)
    connection = get_mysql_connection() if mysql_backend else get_connection(database_path)

    try:
        find_ticket = (
            find_mysql_ticket_by_ticket_no
            if mysql_backend
            else find_ticket_by_ticket_no
        )
        ticket = find_ticket(
            connection,
            ticket_no,
        )

        if ticket is None:
            raise ValueError("工单不存在")

        if ticket["user_id"] != user_id:
            raise ValueError("工单不存在或无权访问")

        return ticket

    finally:
        connection.close()
