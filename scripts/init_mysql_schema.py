"""Initialize the optional MySQL business-data schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.mysql_database import MySQLConfig, get_mysql_connection, init_mysql_schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without connecting to MySQL.",
    )
    args = parser.parse_args()
    config = MySQLConfig.from_env()

    if args.dry_run:
        print(
            f"valid MySQL config for {config.host}:{config.port}/"
            f"{config.database} as {config.user}"
        )
        return 0

    connection = get_mysql_connection(config)
    try:
        init_mysql_schema(connection)
    finally:
        connection.close()
    print(f"MySQL business schema initialized: {config.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
