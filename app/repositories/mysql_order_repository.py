"""MySQL order and tracking repository."""

from __future__ import annotations

from typing import Any


def _event_time(value: Any) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else str(value)


def find_order_tracking(connection: Any, order_no: str) -> dict | None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT order_no, user_id, customer_name, carrier, tracking_no, status
            FROM orders
            WHERE order_no = %s
            """,
            (order_no,),
        )
        order = cursor.fetchone()
        if order is None:
            return None

        cursor.execute(
            """
            SELECT event_time, location, description
            FROM tracking_events
            WHERE order_no = %s
            ORDER BY event_time DESC
            """,
            (order_no,),
        )
        events = cursor.fetchall()
        return {
            **order,
            "tracking_events": [
                {
                    "event_time": _event_time(event["event_time"]),
                    "location": event["location"],
                    "description": event["description"],
                }
                for event in events
            ],
        }
    finally:
        cursor.close()
