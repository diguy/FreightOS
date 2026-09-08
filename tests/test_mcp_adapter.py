import pytest

from app.agent.business_tool_executor import BusinessToolExecutor, BusinessToolHandlers
from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.mcp_adapter import McpAdapterError, McpToolAdapter
from app.agent.session_schema import EffectiveSessionContext


def _context(intent, slots, *, allowed=True):
    result = IntentResult(
        intent=intent,
        confidence=0.95,
        entities=IntentEntities(
            order_id=slots.get("order_id"),
            ticket_no=slots.get("ticket_no"),
            new_address=slots.get("new_address"),
            complaint_content=slots.get("complaint_content"),
            contact=slots.get("contact"),
        ),
        missing_slots=[],
        action="query",
        should_call_tool=allowed,
    )
    return EffectiveSessionContext(
        session_id="mcp-session",
        turn_no=1,
        intent_result=result,
        effective_intent=intent,
        effective_action="query",
        effective_entities=result.entities,
        slots=slots,
        should_call_tool=allowed,
    )


def test_lists_stable_tool_metadata():
    tools = McpToolAdapter().list_tools()

    assert {tool["name"] for tool in tools} == {
        "get_order_tracking",
        "get_ticket_status",
        "search_knowledge",
        "create_address_change_ticket",
        "create_complaint_ticket",
        "create_human_transfer_ticket",
    }
    address_tool = next(
        tool for tool in tools if tool["name"] == "create_address_change_ticket"
    )
    assert address_tool["annotations"]["readOnlyHint"] is False
    assert address_tool["inputSchema"]["properties"]["confirmed"] == {"const": True}


def test_invocation_delegates_only_after_context_gate():
    calls = []

    def tracking(order_id, *, user_id):
        calls.append((order_id, user_id))
        return {"order_no": order_id}

    adapter = McpToolAdapter(
        BusinessToolExecutor(BusinessToolHandlers(get_order_tracking=tracking))
    )
    result = adapter.invoke(
        "get_order_tracking",
        arguments={"order_id": "ORD1001"},
        context=_context("tracking_query", {"order_id": "ORD1001"}),
        user_id="user-1",
    )

    assert result["data"]["order_no"] == "ORD1001"
    assert calls == [("ORD1001", "user-1")]


def test_rejects_unknown_tool_and_mismatched_arguments():
    adapter = McpToolAdapter()
    context = _context("tracking_query", {"order_id": "ORD1001"})

    with pytest.raises(McpAdapterError, match="未知工具"):
        adapter.invoke("delete_order", arguments={}, context=context, user_id="user-1")
    with pytest.raises(McpAdapterError, match="槽位不一致"):
        adapter.invoke(
            "get_order_tracking",
            arguments={"order_id": "ORD1002"},
            context=context,
            user_id="user-1",
        )


def test_rejects_unconfirmed_write_and_blocked_context():
    adapter = McpToolAdapter()
    address_context = _context(
        "address_change",
        {"order_id": "ORD1001", "new_address": "上海市浦东新区张江路1号"},
    )

    with pytest.raises(McpAdapterError, match="必须明确确认"):
        adapter.invoke(
            "create_address_change_ticket",
            arguments={
                "order_id": "ORD1001",
                "new_address": "上海市浦东新区张江路1号",
                "confirmed": False,
            },
            context=address_context,
            user_id="user-1",
        )

    with pytest.raises(McpAdapterError, match="未通过工具调用门控"):
        adapter.invoke(
            "get_order_tracking",
            arguments={"order_id": "ORD1001"},
            context=_context(
                "tracking_query",
                {"order_id": "ORD1001"},
                allowed=False,
            ),
            user_id="user-1",
        )
