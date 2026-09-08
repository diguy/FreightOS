import asyncio

from app.mcp.auth import StaticTokenVerifier


def test_static_token_verifier_maps_subject_without_exposing_policy():
    verifier = StaticTokenVerifier(token="test-token", user_id="user-1")

    accepted = asyncio.run(verifier.verify_token("test-token"))
    rejected = asyncio.run(verifier.verify_token("wrong-token"))

    assert accepted is not None
    assert accepted.subject == "user-1"
    assert rejected is None
