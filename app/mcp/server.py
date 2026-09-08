"""Official MCP Python SDK v2 server for the logistics business tools."""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations

from app.agent.mcp_adapter import McpAdapterError, McpToolAdapter
from app.agent.session_manager import SessionManager
from app.agent.session_store_factory import build_session_store
from app.mcp.context import context_from_session
from app.mcp.auth import StaticTokenVerifier
from app.mcp.settings import McpServerSettings


def create_server(
    *,
    settings: McpServerSettings | None = None,
    adapter: McpToolAdapter | None = None,
    session_manager: SessionManager | None = None,
    token_verifier: TokenVerifier | None = None,
) -> MCPServer:
    settings = settings or McpServerSettings.from_env()
    adapter = adapter or McpToolAdapter()
    session_manager = session_manager or SessionManager(build_session_store())
    server = MCPServer(
        name=settings.name,
        version=settings.version,
        description="物流客服业务工具。所有调用都必须通过会话和用户权限校验。",
        log_level=settings.log_level,
        auth=(
            AuthSettings(
                issuer_url=settings.issuer_url,
                resource_server_url=settings.resource_server_url,
                required_scopes=["logistics:read"],
            )
            if token_verifier
            else None
        ),
        token_verifier=token_verifier,
    )

    def invoke(
        tool_name: str,
        *,
        session_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any] | None:
        if token_verifier:
            access_token = get_access_token()
            user_id = access_token.subject if access_token else None
            if not user_id:
                raise McpAdapterError("认证信息缺少用户身份")
        else:
            user_id = settings.user_id
            if not user_id:
                raise McpAdapterError("MCP_USER_ID 未配置")
        context = context_from_session(
            session_manager,
            session_id=session_id,
            user_id=user_id,
        )
        return adapter.invoke(
            tool_name,
            arguments=arguments,
            context=context,
            user_id=user_id,
        )

    @server.tool(
        name="get_order_tracking",
        description="查询当前用户有权访问的订单物流轨迹。",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
        ),
    )
    def get_order_tracking(
        session_id: str,
        order_id: str,
    ) -> dict[str, Any] | None:
        return invoke(
            "get_order_tracking",
            session_id=session_id,
            arguments={"order_id": order_id},
        )

    @server.tool(
        name="get_ticket_status",
        description="查询当前用户有权访问的工单状态。",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
        ),
    )
    def get_ticket_status(
        session_id: str,
        ticket_no: str,
    ) -> dict[str, Any] | None:
        return invoke(
            "get_ticket_status",
            session_id=session_id,
            arguments={"ticket_no": ticket_no},
        )

    @server.tool(
        name="search_knowledge",
        description="检索物流知识库中的相关资料。",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
        ),
    )
    def search_knowledge(
        session_id: str,
        question: str,
    ) -> dict[str, Any] | None:
        return invoke(
            "search_knowledge",
            session_id=session_id,
            arguments={"question": question},
        )

    @server.tool(
        name="create_address_change_ticket",
        description="在当前会话已完成地址确认后创建改址工单。",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
        ),
    )
    def create_address_change_ticket(
        session_id: str,
        order_id: str,
        new_address: str,
        confirmed: bool,
    ) -> dict[str, Any] | None:
        return invoke(
            "create_address_change_ticket",
            session_id=session_id,
            arguments={
                "order_id": order_id,
                "new_address": new_address,
                "confirmed": confirmed,
            },
        )

    @server.tool(
        name="create_complaint_ticket",
        description="创建投诉工单并记录联系方式。",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
        ),
    )
    def create_complaint_ticket(
        session_id: str,
        complaint_content: str,
        contact: str,
        order_id: str | None = None,
    ) -> dict[str, Any] | None:
        return invoke(
            "create_complaint_ticket",
            session_id=session_id,
            arguments={
                "order_id": order_id,
                "complaint_content": complaint_content,
                "contact": contact,
            },
        )

    @server.tool(
        name="create_human_transfer_ticket",
        description="创建人工客服工单。",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
        ),
    )
    def create_human_transfer_ticket(
        session_id: str,
        content: str,
        contact: str | None = None,
    ) -> dict[str, Any] | None:
        return invoke(
            "create_human_transfer_ticket",
            session_id=session_id,
            arguments={"content": content, "contact": contact},
        )

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the logistics MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="Transport for the server.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.transport == "stdio":
        server = create_server()
        server.run("stdio")
        return

    settings = McpServerSettings.from_env()
    verifier = StaticTokenVerifier(
        token=settings.bearer_token,
        user_id=settings.user_id,
    )
    server = create_server(settings=settings, token_verifier=verifier)
    server.run(
        "streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
