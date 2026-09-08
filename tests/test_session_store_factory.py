import pytest

from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.redis_session_store import RedisSessionStore
from app.agent.session_store_factory import build_session_store


def test_factory_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("SESSION_STORE", raising=False)
    monkeypatch.setattr(
        "app.agent.session_store_factory.load_local_env",
        lambda: None,
    )

    assert isinstance(build_session_store(), InMemorySessionStore)


def test_factory_builds_redis_from_environment(monkeypatch):
    monkeypatch.setenv("SESSION_STORE", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://redis.example/2")
    monkeypatch.setenv("REDIS_SESSION_KEY_PREFIX", "test-session:")

    class FakeRedisStore:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(
        "app.agent.session_store_factory.RedisSessionStore",
        FakeRedisStore,
    )

    store = build_session_store()

    assert store.kwargs == {
        "url": "redis://redis.example/2",
        "key_prefix": "test-session:",
    }


def test_factory_rejects_unknown_store(monkeypatch):
    monkeypatch.setenv("SESSION_STORE", "sqlite")

    with pytest.raises(ValueError, match="SESSION_STORE"):
        build_session_store()
