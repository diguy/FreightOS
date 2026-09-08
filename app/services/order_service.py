from pathlib import Path

from app.core.errors import OrderAccessDeniedError
from app.database import DATABASE_PATH, get_connection
from app.repositories.order_repository import find_order_tracking
from app.database_backend import get_business_backend, use_mysql
from app.mysql_database import (
    ensure_tracking_event_uniqueness,
    get_mysql_connection,
    init_mysql_schema,
)
from app.repositories.mysql_order_repository import (
    find_order_tracking as find_mysql_order_tracking,
)

MYSQL_DEMO_USERS = (
    ("demo-user-001", "演示用户一", "138****0001"),
    ("demo-user-002", "演示用户二", "138****0002"),
)
MYSQL_DEMO_ORDERS = (
    ("ORD1001", "demo-user-001", "张三", "顺丰速运", "SF1001001", "in_transit"),
    ("ORD1002", "demo-user-001", "李四", "中通快递", "ZT1002002", "delivered"),
    ("ORD1003", "demo-user-001", "王五", "圆通速递", "YT1003003", "exception"),
)
MYSQL_DEMO_EVENTS = (
    ("ORD1001", "2026-08-29 08:30:00", "上海分拨中心", "包裹已到达分拨中心"),
    ("ORD1001", "2026-08-29 12:10:00", "上海浦东转运中心", "包裹正在转运中"),
    ("ORD1002", "2026-08-28 09:00:00", "杭州配送站", "快递员正在派送"),
    ("ORD1002", "2026-08-28 14:20:00", "杭州市西湖区", "客户本人已签收"),
    ("ORD1003", "2026-08-27 16:40:00", "武汉转运中心", "包裹运输途中出现异常"),
)


def _seed_mysql_demo_data(connection) -> None:
    cursor = connection.cursor()
    try:
        cursor.executemany(
            "INSERT IGNORE INTO users (id, name, phone_masked) VALUES (%s, %s, %s)",
            MYSQL_DEMO_USERS,
        )
        cursor.executemany(
            """
            INSERT IGNORE INTO orders
                (order_no, user_id, customer_name, carrier, tracking_no, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            MYSQL_DEMO_ORDERS,
        )
        cursor.executemany(
            """
            INSERT IGNORE INTO tracking_events
                (order_no, event_time, location, description)
            VALUES (%s, %s, %s, %s)
            """,
            MYSQL_DEMO_EVENTS,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


ORDER_STATUS_LABELS = {
    "in_transit": "运输中",
    "delivered": "已签收",
    "exception": "物流异常",
    "cancelled": "已取消",
}
def init_database(database_path: Path = DATABASE_PATH) -> None:
    """创建数据表并写入模拟数据。"""
    if use_mysql(database_path):
        connection = get_mysql_connection()
        try:
            init_mysql_schema(connection)
            ensure_tracking_event_uniqueness(connection)
            _seed_mysql_demo_data(connection)
        finally:
            connection.close()
        return

    connection = get_connection(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                carrier TEXT NOT NULL,
                tracking_no TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tracking_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT NOT NULL,
                event_time TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                FOREIGN KEY (order_no) REFERENCES orders(order_no)
            )
            """
        )
        # ========== 新增 1：创建 users 表（幂等） ==========
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone_masked TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_no TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                order_id TEXT,
                type TEXT NOT NULL CHECK (
                    type IN ('address_change', 'complaint', 'human')
                ),
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (
                    status IN ('pending', 'processing', 'completed', 'rejected', 'cancelled')
                ),
                client_request_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, client_request_id)
            )
            """
        )
        # ========== 新增 2：为 orders 增加 user_id 列（幂等） ==========
        # 查询现有列名，避免重复添加
        order_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(orders)"
            ).fetchall()
        }
        if "user_id" not in order_columns:
            connection.execute(
                "ALTER TABLE orders ADD COLUMN user_id TEXT"
            )
        order_count = connection.execute(
            "SELECT COUNT(*) AS count FROM orders"
        ).fetchone()["count"]

        if order_count == 0:
            connection.executemany(
                """
                INSERT INTO orders (
                    order_no,
                    customer_name,
                    carrier,
                    tracking_no,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        "ORD1001",
                        "张三",
                        "顺丰速运",
                        "SF1001001",
                        "in_transit",
                    ),
                    (
                        "ORD1002",
                        "李四",
                        "中通快递",
                        "ZT1002002",
                        "delivered",
                    ),
                    (
                        "ORD1003",
                        "王五",
                        "圆通速递",
                        "YT1003003",
                        "exception",
                    ),
                ],
            )

            connection.executemany(
                """
                INSERT INTO tracking_events (
                    order_no,
                    event_time,
                    location,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "ORD1001",
                        "2026-08-29 08:30:00",
                        "上海分拨中心",
                        "包裹已到达分拨中心",
                    ),
                    (
                        "ORD1001",
                        "2026-08-29 12:10:00",
                        "上海浦东转运中心",
                        "包裹正在转运中",
                    ),
                    (
                        "ORD1002",
                        "2026-08-28 09:00:00",
                        "杭州配送站",
                        "快递员正在派送",
                    ),
                    (
                        "ORD1002",
                        "2026-08-28 14:20:00",
                        "杭州市西湖区",
                        "客户本人已签收",
                    ),
                    (
                        "ORD1003",
                        "2026-08-27 16:40:00",
                        "武汉转运中心",
                        "包裹运输途中出现异常",
                    ),
                ],
            )
        connection.executemany(
            """
            INSERT OR IGNORE INTO users (id, name, phone_masked)
            VALUES (?, ?, ?)
            """,
            [
                ("demo-user-001", "演示用户一", "138****0001"),
                ("demo-user-002", "演示用户二", "138****0002"),
            ],
        )
        connection.execute(
            """
            UPDATE orders
            SET user_id = ?
            WHERE user_id IS NULL
            """,
            ("demo-user-001",),
        )
        connection.execute(
            """
            UPDATE orders
            SET status = 'in_transit'
            WHERE status = '运输中'
            """
        )

        connection.execute(
            """
            UPDATE orders
            SET status = 'delivered'
            WHERE status = '已签收'
            """
        )

        connection.execute(
            """
            UPDATE orders
            SET status = 'exception'
            WHERE status = '物流异常'
            """
        )
        connection.commit()

    finally:
        connection.close()

def get_order_tracking(
    order_no: str,
    database_path: Path = DATABASE_PATH,
    *,
    user_id: str | None = None,
) -> dict | None:
    """查询订单物流，并在提供用户 ID 时校验订单归属。"""
    if use_mysql(database_path):
        connection = get_mysql_connection()
        try:
            result = find_mysql_order_tracking(connection, order_no)
        finally:
            connection.close()
    else:
        result = find_order_tracking(order_no, database_path)

    if result is None:
        return None

    if user_id is not None and result["user_id"] != user_id:
        raise OrderAccessDeniedError

    result.pop("user_id", None)
    return result
