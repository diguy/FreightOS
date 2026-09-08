"""Create a MySQL logical backup without exposing the password in argv."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.mysql_database import MySQLConfig


def main() -> int:
    config = MySQLConfig.from_env()
    mysqldump = shutil.which("mysqldump")
    container = os.getenv("MYSQL_BACKUP_CONTAINER", "").strip()
    if mysqldump is None and not container:
        print(
            "mysqldump was not found in PATH. Install the MySQL client tools "
            "or set MYSQL_BACKUP_CONTAINER to a MySQL Docker container.",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(os.getenv("MYSQL_BACKUP_DIR", "data/backups"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (
        f"{config.database}_{datetime.now():%Y%m%d_%H%M%S}.sql"
    )
    env = os.environ.copy()
    env["MYSQL_PWD"] = config.password
    dump_args = [
        "--single-transaction",
        "--no-tablespaces",
        "--routines",
        "--triggers",
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--user",
        config.user,
        config.database,
    ]
    if container:
        dump_args[dump_args.index("--host") + 1] = "127.0.0.1"
        dump_args[dump_args.index("--port") + 1] = "3306"
    command = (
        [mysqldump, *dump_args]
        if mysqldump
        else ["docker", "exec", "-e", "MYSQL_PWD", container, "mysqldump", *dump_args]
    )
    try:
        with output_path.open("w", encoding="utf-8", newline="") as output:
            subprocess.run(command, env=env, stdout=output, check=True)
    except subprocess.CalledProcessError:
        output_path.unlink(missing_ok=True)
        raise
    print(f"MySQL backup created: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
