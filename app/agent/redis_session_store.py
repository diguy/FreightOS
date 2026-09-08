"""Redis-backed session storage with the same contract as the memory store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agent.session_schema import SessionState


class RedisSessionStore:
    """Persist session snapshots as JSON with server-side expiration."""

    def __init__(
        self,
        *,
        url: str = "redis://127.0.0.1:6379/0",
        key_prefix: str = "logistics:session:",
        client: Any | None = None,
    ) -> None:
        if not key_prefix:
            raise ValueError("key_prefix must not be empty")
        self.key_prefix = key_prefix
        self.client = client or self._create_client(url)

    def get(self, session_id: str) -> SessionState | None:
        payload = self.client.get(self._key(session_id))
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return SessionState.model_validate_json(payload)

    def save(self, state: SessionState) -> None:
        key = self._key(state.session_id)
        if state.expires_at is None:
            self.client.set(key, state.model_dump_json())
            return

        ttl = int(
            (state.expires_at - datetime.now(timezone.utc)).total_seconds()
        )
        if ttl <= 0:
            self.delete(state.session_id)
            return
        self.client.set(key, state.model_dump_json(), ex=ttl)

    def delete(self, session_id: str) -> None:
        self.client.delete(self._key(session_id))

    def check_health(self) -> bool:
        return bool(self.client.ping())

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"

    @staticmethod
    def _create_client(url: str) -> Any:
        try:
            import redis
        except ImportError as error:
            raise RuntimeError(
                "Redis session storage requires the 'redis' package"
            ) from error
        return redis.Redis.from_url(url, decode_responses=True)
