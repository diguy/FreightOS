"""Small client boundary for the Dify chat API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests

from app.rag.config import load_local_env


class DifyClientError(RuntimeError):
    """Raised when Dify cannot return a usable response."""


class DifyClient(Protocol):
    def chat(
        self,
        *,
        query: str,
        user: str,
        conversation_id: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one message and return the decoded Dify response."""


@dataclass(frozen=True)
class DifySettings:
    base_url: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "DifySettings":
        load_local_env()
        return cls(
            base_url=os.getenv("DIFY_BASE_URL", "http://127.0.0.1:5001").rstrip("/"),
            api_key=os.getenv("DIFY_API_KEY", ""),
            timeout_seconds=float(os.getenv("DIFY_TIMEOUT_SECONDS", "30")),
        )


class HttpDifyClient:
    """Requests-based implementation of the Dify chat API boundary."""

    def __init__(self, settings: DifySettings | None = None) -> None:
        self.settings = settings or DifySettings.from_env()

    def chat(
        self,
        *,
        query: str,
        user: str,
        conversation_id: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.api_key:
            raise DifyClientError("DIFY_API_KEY is not configured")

        payload: dict[str, Any] = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "blocking",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            response = requests.post(
                f"{self.settings.base_url}/v1/chat-messages",
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as error:
            raise DifyClientError(f"Dify request failed: {error}") from error

        if not isinstance(data, dict):
            raise DifyClientError("Dify response must be a JSON object")
        return data
