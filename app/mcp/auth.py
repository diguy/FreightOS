"""Local bearer-token verification seam for the first HTTP phase."""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken


class StaticTokenVerifier:
    """Verify one configured token without exposing the token in logs."""

    def __init__(self, *, token: str, user_id: str) -> None:
        if not token.strip() or not user_id.strip():
            raise ValueError("MCP bearer token and user id are required")
        self._token = token
        self._user_id = user_id

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != self._token:
            return None
        return AccessToken(
            token=token,
            client_id="local-mcp-client",
            scopes=["logistics:read", "logistics:write"],
            subject=self._user_id,
        )
