"""Migrate business data from the local SQLite database to MySQL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import DATABASE_PATH, get_connection
from app.mysql_database import (
    ensure_tracking_event_uniqueness,
    get_mysql_connection,
    init_mysql_schema,
)


def _rows(connection, table: str) -> list[dict]:
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def migrate(
    *,
    source_path: Path = DATABASE_PATH,
    dry_run: bool = False,
) -> dict[str, int]:
    sqlite_connection = get_connection(source_path)
    mysql_connection = get_mysql_connection()
    try:
        init_mysql_schema(mysql_connection)
        ensure_tracking_event_uniqueness(mysql_connection)
        data = {
            table: _rows(sqlite_connection, table)
            for table in ("users", "orders", "tracking_events", "tickets")
        }

        if dry_run:
            return {table: len(rows) for table, rows in data.items()}

        cursor = mysql_connection.cursor()
        try:
            for row in data["users"]:
                cursor.execute(
                    """
                    INSERT INTO users (id, name, phone_masked)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        phone_masked = VALUES(phone_masked)
                    """,
                    (row["id"], row["name"], row["phone_masked"]),
                )

            for row in data["orders"]:
                cursor.execute(
                    """
                    INSERT INTO orders (
                        order_no, user_id, customer_name, carrier, tracking_no, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        user_id = VALUES(user_id),
                        customer_name = VALUES(customer_name),
                        carrier = VALUES(carrier),
                        tracking_no = VALUES(tracking_no),
                        status = VALUES(status)
                    """,
                    (
                        row["order_no"],
                        row["user_id"],
                        row["customer_name"],
                        row["carrier"],
                        row["tracking_no"],
                        row["status"],
                    ),
                )

            for row in data["tracking_events"]:
                cursor.execute(
                    """
                    SELECT 1 FROM tracking_events
                    WHERE order_no = %s AND event_time = %s
                      AND location = %s AND description = %s
                    LIMIT 1
                    """,
                    (
                        row["order_no"],
                        row["event_time"],
                        row["location"],
                        row["description"],
                    ),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO tracking_events (
                            order_no, event_time, location, description
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            row["order_no"],
                            row["event_time"],
                            row["location"],
                            row["description"],
                        ),
                    )

            for row in data["tickets"]:
                cursor.execute(
                    """
                    INSERT INTO tickets (
                        ticket_no, user_id, order_id, type, content, status,
                        client_request_id, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        user_id = VALUES(user_id),
                        order_id = VALUES(order_id),
                        type = VALUES(type),
                        content = VALUES(content),
                        status = VALUES(status),
                        client_request_id = VALUES(client_request_id),
                        created_at = VALUES(created_at)
                    """,
                    (
                        row["ticket_no"],
                        row["user_id"],
                        row["order_id"],
                        row["type"],
                        row["content"],
                        row["status"],
                        row["client_request_id"],
                        row["created_at"],
                    ),
                )

            mysql_connection.commit()
        except Exception:
            mysql_connection.rollback()
            raise
        finally:
            cursor.close()

        return {table: len(rows) for table, rows in data.items()}
    finally:
        sqlite_connection.close()
        mysql_connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DATABASE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    counts = migrate(source_path=args.source, dry_run=args.dry_run)
    prefix = "would migrate" if args.dry_run else "migrated"
    details = ", ".join(f"{table}={count}" for table, count in counts.items())
    print(f"{prefix}: {details}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
