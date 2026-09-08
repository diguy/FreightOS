from pathlib import Path

from app.database import DATABASE_PATH, get_connection


def find_order_tracking(
    order_no: str,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """根据订单号读取订单和物流轨迹。"""
    connection = get_connection(database_path)

    try:
        order = connection.execute(
            """
            SELECT
                order_no,
                user_id,
                customer_name,
                carrier,
                tracking_no,
                status
            FROM orders
            WHERE order_no = ?
            """,
            (order_no,),
        ).fetchone()

        if order is None:
            return None

        events = connection.execute(
            """
            SELECT
                event_time,
                location,
                description
            FROM tracking_events
            WHERE order_no = ?
            ORDER BY event_time DESC
            """,
            (order_no,),
        ).fetchall()

        return {
            "order_no": order["order_no"],
            "user_id": order["user_id"],
            "customer_name": order["customer_name"],
            "carrier": order["carrier"],
            "tracking_no": order["tracking_no"],
            "status": order["status"],
            "tracking_events": [
                {
                    "event_time": event["event_time"],
                    "location": event["location"],
                    "description": event["description"],
                }
                for event in events
            ],
        }

    finally:
        connection.close()