import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "logistics.db"


def get_connection(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """创建数据库连接。"""
    DATA_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection