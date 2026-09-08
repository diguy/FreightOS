from datetime import datetime, timedelta, timezone

from app.agent.redis_session_store import RedisSessionStore
from app.agent.session_schema import SessionState


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.calls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.calls.append(("set", key, ex))
        self.values[key] = value

    def delete(self, key):
        self.calls.append(("delete", key))
        self.values.pop(key, None)


def test_redis_store_round_trips_session_state_with_ttl():
    client = FakeRedis()
    store = RedisSessionStore(client=client, key_prefix="test:")
    state = SessionState(
        session_id="s1",
        slots={"order_id": "ORD1001"},
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )

    store.save(state)
    loaded = store.get("s1")

    assert loaded is not None
    assert loaded.slots == {"order_id": "ORD1001"}
    assert client.calls[0][0:2] == ("set", "test:s1")
    assert 1 <= client.calls[0][2] <= 60


def test_redis_store_deletes_expired_state_instead_of_persisting_it():
    client = FakeRedis()
    store = RedisSessionStore(client=client, key_prefix="test:")
    state = SessionState(
        session_id="expired",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    store.save(state)

    assert client.get("test:expired") is None
    assert client.calls == [("delete", "test:expired")]


def test_redis_store_decodes_byte_payloads():
    client = FakeRedis()
    store = RedisSessionStore(client=client)
    state = SessionState(session_id="bytes", summary="状态")
    client.values["logistics:session:bytes"] = state.model_dump_json().encode()

    assert store.get("bytes").summary == "状态"
