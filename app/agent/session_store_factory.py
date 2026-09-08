"""Build the configured session store for application startup."""

from __future__ import annotations

import os

from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.redis_session_store import RedisSessionStore
from app.rag.config import load_local_env


def build_session_store():
    load_local_env()
    store_type = os.getenv("SESSION_STORE", "memory").strip().lower()
    if store_type == "memory":
        return InMemorySessionStore()
    if store_type == "redis":
        return RedisSessionStore(
            url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            key_prefix=os.getenv(
                "REDIS_SESSION_KEY_PREFIX",
                "logistics:session:",
            ),
        )
    raise ValueError("SESSION_STORE must be either 'memory' or 'redis'")
