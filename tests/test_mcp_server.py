import asyncio

import pytest

from app.agent.business_tool_executor import BusinessToolExecutor, BusinessToolHandlers
from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.mcp_adapter import McpToolAdapter
from app.agent.session_manager import SessionManager
from app.mcp.context import McpContextError, context_from_session
from app.mcp.server import create_server
from app.mcp.settings import McpServerSettings


def _manager_with_tracking_session(user_id="user-1"):
    manager = SessionManager(InMemorySessionStore())
    manager.process_turn(
        session_id="s1",
        user_id=user_id,
        user_message="查 ORD1001",
        intent_result=IntentResult(
            intent="tracking_query",
            confidence=0.95,
            entities=IntentEntities(order_id="ORD1001"),
            missing_slots=[],
            action="query",
            should_call_tool=True,
        ),
    )
    return manager


def test_server_registers_all_business_tools():
    server = create_server(
        settings=McpServerSettings(user_id="user-1"),
        session_manager=_manager_with_tracking_session(),
    )

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "get_order_tracking",
        "get_ticket_status",
        "search_knowledge",
        "create_address_change_ticket",
        "create_complaint_ticket",
        "create_human_transfer_ticket",
    }


def test_context_is_restored_from_owned_session():
    manager = _manager_with_tracking_session()

    context = context_from_session(
        manager,
        session_id="s1",
        user_id="user-1",
    )

    assert context.effective_intent == "tracking_query"
    assert context.slots["order_id"] == "ORD1001"
    assert context.should_call_tool is True


def test_context_rejects_missing_or_other_user_session():
    manager = _manager_with_tracking_session()

    with pytest.raises(McpContextError, match="不属于当前用户"):
        context_from_session(manager, session_id="s1", user_id="user-2")
    with pytest.raises(McpContextError, match="不存在或已过期"):
        context_from_session(manager, session_id="missing", user_id="user-1")


def test_server_tool_call_uses_adapter_and_does_not_accept_user_id_argument():
    calls = []

    def tracking(order_id, *, user_id):
        calls.append((order_id, user_id))
        return {"order_no": order_id}

    manager = _manager_with_tracking_session()
    adapter = McpToolAdapter(
        BusinessToolExecutor(BusinessToolHandlers(get_order_tracking=tracking))
    )
    server = create_server(
        settings=McpServerSettings(user_id="user-1"),
        adapter=adapter,
        session_manager=manager,
    )

    result = asyncio.run(
        server.call_tool(
            "get_order_tracking",
            {"session_id": "s1", "order_id": "ORD1001"},
        )
    )

    assert result.content[0].text.find("ORD1001") >= 0
    assert calls == [("ORD1001", "user-1")]
