"""Select the business-data backend without changing service contracts."""

from __future__ import annotations

import os
from pathlib import Path

from app.database import DATABASE_PATH
from app.rag.config import load_local_env


def get_business_backend() -> str:
    load_local_env()
    backend = os.getenv("APP_DATABASE", "sqlite").strip().lower()
    if backend not in {"sqlite", "mysql"}:
        raise ValueError("APP_DATABASE must be either 'sqlite' or 'mysql'")
    return backend


def use_mysql(database_path: Path | None = None) -> bool:
    """Select MySQL only for the configured application database."""

    return get_business_backend() == "mysql" and (
        database_path is None or database_path == DATABASE_PATH
    )
