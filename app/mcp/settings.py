"""Configuration for the local MCP server entry point."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.rag.config import load_local_env


@dataclass(frozen=True)
class McpServerSettings:
    name: str = "logistics-business-tools"
    version: str = "0.1.0"
    user_id: str = ""
    bearer_token: str = ""
    issuer_url: str = "https://local.invalid"
    resource_server_url: str = "http://127.0.0.1:8001"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "McpServerSettings":
        load_local_env()
        return cls(
            name=os.getenv("MCP_SERVER_NAME", cls.name),
            version=os.getenv("MCP_SERVER_VERSION", cls.version),
            user_id=os.getenv("MCP_USER_ID", ""),
            bearer_token=os.getenv("MCP_BEARER_TOKEN", ""),
            issuer_url=os.getenv("MCP_ISSUER_URL", cls.issuer_url),
            resource_server_url=os.getenv(
                "MCP_RESOURCE_SERVER_URL",
                cls.resource_server_url,
            ),
            log_level=os.getenv("MCP_LOG_LEVEL", cls.log_level).upper(),
        )
