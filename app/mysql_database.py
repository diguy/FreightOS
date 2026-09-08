"""Optional MySQL connection and schema initialization for business data."""

from __future__ import annotations

from dataclasses import dataclass
import os
from queue import Empty, Queue
from threading import Lock
from typing import Any

from app.rag.config import load_local_env


@dataclass(frozen=True)
class MySQLConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    database: str = "logistics"
    user: str = "logistics"
    password: str = ""
    charset: str = "utf8mb4"
    pool_min_size: int = 1
    pool_max_size: int = 5

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        load_local_env()
        return cls(
            host=os.getenv("APP_MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("APP_MYSQL_PORT", "3306")),
            database=os.getenv("APP_MYSQL_DATABASE", "logistics"),
            user=os.getenv("APP_MYSQL_USER", "logistics"),
            password=os.getenv("APP_MYSQL_PASSWORD", ""),
            charset=os.getenv("APP_MYSQL_CHARSET", "utf8mb4"),
            pool_min_size=int(os.getenv("APP_MYSQL_POOL_MIN_SIZE", "1")),
            pool_max_size=int(os.getenv("APP_MYSQL_POOL_MAX_SIZE", "5")),
        )


class _PooledConnection:
    def __init__(self, pool: "_MySQLConnectionPool", connection: Any):
        self._pool = pool
        self._connection = connection
        self._returned = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def close(self) -> None:
        if not self._returned:
            self._returned = True
            self._pool.release(self._connection)


class _MySQLConnectionPool:
    def __init__(self, config: MySQLConfig):
        if config.pool_min_size < 0 or config.pool_max_size < 1:
            raise ValueError("MySQL pool sizes must be positive")
        if config.pool_min_size > config.pool_max_size:
            raise ValueError("APP_MYSQL_POOL_MIN_SIZE cannot exceed max size")
        self.config = config
        self._available: Queue[Any] = Queue(maxsize=config.pool_max_size)
        self._created = 0
        self._lock = Lock()
        for _ in range(config.pool_min_size):
            self._available.put(self._create_raw_connection())
            self._created += 1

    def _create_raw_connection(self) -> Any:
        return _create_mysql_connection(self.config)

    def acquire(self) -> _PooledConnection:
        try:
            connection = self._available.get_nowait()
        except Empty:
            with self._lock:
                if self._created < self.config.pool_max_size:
                    connection = self._create_raw_connection()
                    self._created += 1
                else:
                    connection = self._available.get()
        try:
            connection.ping()
        except Exception:
            connection.close()
            with self._lock:
                self._created -= 1
            connection = self._create_raw_connection()
            with self._lock:
                self._created += 1
        return _PooledConnection(self, connection)

    def release(self, connection: Any) -> None:
        try:
            connection.rollback()
            self._available.put_nowait(connection)
        except Exception:
            connection.close()
            with self._lock:
                self._created -= 1


_POOLS: dict[MySQLConfig, _MySQLConnectionPool] = {}
_POOLS_LOCK = Lock()


def _create_mysql_connection(config: MySQLConfig) -> Any:
    """Create a MySQL connection only when the optional driver is installed."""

    try:
        import pymysql
    except ImportError as error:
        raise RuntimeError(
            "MySQL support requires the 'pymysql' package"
        ) from error

    return pymysql.connect(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
        charset=config.charset,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_mysql_connection(config: MySQLConfig | None = None) -> Any:
    """Acquire a pooled MySQL connection with the existing connection contract."""

    settings = config or MySQLConfig.from_env()
    with _POOLS_LOCK:
        pool = _POOLS.get(settings)
        if pool is None:
            pool = _MySQLConnectionPool(settings)
            _POOLS[settings] = pool
    return pool.acquire()


def check_mysql_health(config: MySQLConfig | None = None) -> dict[str, Any]:
    connection = get_mysql_connection(config)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()
        finally:
            cursor.close()
        return {"ok": bool(row and row["ok"] == 1)}
    finally:
        connection.close()


MYSQL_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(100) PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        phone_masked VARCHAR(50) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        order_no VARCHAR(50) NOT NULL UNIQUE,
        user_id VARCHAR(100) NULL,
        customer_name VARCHAR(200) NOT NULL,
        carrier VARCHAR(100) NOT NULL,
        tracking_no VARCHAR(100) NOT NULL,
        status VARCHAR(30) NOT NULL,
        INDEX idx_orders_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS tracking_events (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        order_no VARCHAR(50) NOT NULL,
        event_time DATETIME NOT NULL,
        location VARCHAR(200) NOT NULL,
        description VARCHAR(1000) NOT NULL,
        UNIQUE KEY uq_tracking_event (order_no, event_time, location, description(191)),
        INDEX idx_tracking_events_order_time (order_no, event_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS tickets (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        ticket_no VARCHAR(50) NOT NULL UNIQUE,
        user_id VARCHAR(100) NOT NULL,
        order_id VARCHAR(50) NULL,
        type VARCHAR(30) NOT NULL,
        content TEXT NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        client_request_id VARCHAR(100) NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_tickets_user_request (user_id, client_request_id),
        INDEX idx_tickets_user_status (user_id, status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


def init_mysql_schema(
    connection: Any,
    *,
    statements: tuple[str, ...] = MYSQL_SCHEMA_STATEMENTS,
) -> None:
    """Create the business schema without seeding or touching RAGFlow tables."""

    cursor = connection.cursor()
    try:
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def ensure_tracking_event_uniqueness(connection: Any) -> None:
    """Repair legacy duplicate events and enforce idempotent event writes."""

    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            DELETE older FROM tracking_events AS older
            INNER JOIN tracking_events AS newer
              ON older.order_no = newer.order_no
             AND older.event_time = newer.event_time
             AND older.location = newer.location
             AND older.description = newer.description
             AND older.id > newer.id
            """
        )
        try:
            cursor.execute(
                """
                ALTER TABLE tracking_events
                ADD UNIQUE KEY uq_tracking_event (
                    order_no, event_time, location, description(191)
                )
                """
            )
        except Exception as error:
            if "Duplicate key name" not in str(error):
                raise
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
