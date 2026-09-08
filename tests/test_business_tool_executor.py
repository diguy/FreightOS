import pytest

from app.agent.business_tool_executor import (
    BusinessToolError,
    BusinessToolExecutor,
    BusinessToolHandlers,
)
from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.session_schema import EffectiveSessionContext


def _context(
    intent,
    slots,
    should_call_tool=True,
    action="query",
    session_id="s1",
):
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
        action=action,
        should_call_tool=should_call_tool,
    )
    return EffectiveSessionContext(
        session_id=session_id,
        turn_no=1,
        intent_result=result,
        effective_intent=intent,
        effective_action=action,
        effective_entities=result.entities,
        slots=slots,
        should_call_tool=should_call_tool,
    )


def test_tracking_dispatches_to_order_service():
    calls = []

    def tracking(order_id, *, user_id):
        calls.append((order_id, user_id))
        return {"order_no": order_id}

    executor = BusinessToolExecutor(
        BusinessToolHandlers(get_order_tracking=tracking)
    )

    result = executor.execute(
        context=_context("tracking_query", {"order_id": "ORD1001"}),
        user_id="user-1",
    )

    assert result["type"] == "tracking"
    assert calls == [("ORD1001", "user-1")]


def test_ticket_status_dispatches_to_ticket_service():
    calls = []

    def get_ticket(ticket_no, *, user_id):
        calls.append((ticket_no, user_id))
        return {"ticket_no": ticket_no, "status": "processing"}

    executor = BusinessToolExecutor(
        BusinessToolHandlers(get_ticket=get_ticket)
    )

    result = executor.execute(
        context=_context("ticket_status", {"ticket_no": "TABC12345"}),
        user_id="user-1",
    )

    assert result == {
        "success": True,
        "type": "ticket_status",
        "data": {"ticket_no": "TABC12345", "status": "processing"},
    }
    assert calls == [("TABC12345", "user-1")]


def test_knowledge_query_dispatches_to_local_search():
    from app.rag.client import SearchResult

    def search(question, *, top_k):
        assert question == "酒能通过顺丰进出口件寄送吗？"
        assert top_k == 5
        return [
            SearchResult(
                content="烟草和烟草制品、酒。",
                score=1.0,
                document_name="顺丰禁寄规则.md",
                metadata={"topic": "禁寄和限寄"},
            )
        ]

    executor = BusinessToolExecutor(
        BusinessToolHandlers(search_knowledge=search)
    )
    context = _context(
        "knowledge_query",
        {"question": "酒能通过顺丰进出口件寄送吗？"},
    )

    result = executor.execute(context=context, user_id="user-1")

    assert result["type"] == "knowledge_query"
    assert result["data"]["records"][0]["document_name"] == "顺丰禁寄规则.md"
    assert "烟草和烟草制品" in result["data"]["context"]


def test_address_change_dispatches_only_with_gate():
    calls = []

    def address_change(request, *, user_id):
        calls.append((request, user_id))
        return {"ticket_no": "T1"}

    executor = BusinessToolExecutor(
        BusinessToolHandlers(create_address_change_ticket=address_change)
    )
    result = executor.execute(
        context=_context(
            "address_change",
            {"order_id": "ORD1001", "new_address": "上海市浦东新区张江路1号"},
            action="confirm",
        ),
        user_id="user-1",
    )

    assert result["type"] == "address_change"
    assert calls[0][0].confirmed is True
    assert calls[0][0].client_request_id.startswith("agent-")


def test_write_actions_reuse_request_id_for_same_context():
    complaint_calls = []

    def complaint(request, *, user_id):
        complaint_calls.append((request, user_id))
        return {"ticket_no": "T1"}

    executor = BusinessToolExecutor(
        BusinessToolHandlers(create_complaint_ticket=complaint)
    )
    context = _context(
        "complaint",
        {
            "order_id": "ORD1003",
            "complaint_content": "包裹一直不动",
            "contact": "138****0001",
        },
        session_id="s1",
    )

    executor.execute(context=context, user_id="user-1")
    executor.execute(context=context, user_id="user-1")

    assert len(complaint_calls) == 2
    assert (
        complaint_calls[0][0].client_request_id
        == complaint_calls[1][0].client_request_id
    )


def test_write_actions_use_different_request_id_for_different_sessions():
    def complaint(request, *, user_id):
        return {"client_request_id": request.client_request_id}

    executor = BusinessToolExecutor(
        BusinessToolHandlers(create_complaint_ticket=complaint)
    )
    first = _context(
        "complaint",
        {
            "complaint_content": "包裹一直不动",
            "contact": "138****0001",
        },
        session_id="s1",
    )
    second = _context(
        "complaint",
        {
            "complaint_content": "包裹一直不动",
            "contact": "138****0001",
        },
        session_id="s2",
    )

    first_result = executor.execute(context=first, user_id="user-1")
    second_result = executor.execute(context=second, user_id="user-1")

    assert (
        first_result["data"]["client_request_id"]
        != second_result["data"]["client_request_id"]
    )


def test_blocked_context_never_reaches_handler():
    def fail(**kwargs):
        raise AssertionError("blocked tool must not be called")

    executor = BusinessToolExecutor(
        BusinessToolHandlers(get_order_tracking=fail)
    )
    assert executor.execute(
        context=_context(
            "tracking_query",
            {"order_id": "ORD1001"},
            should_call_tool=False,
        ),
        user_id="user-1",
    ) is None


def test_missing_slot_is_rejected_by_executor():
    executor = BusinessToolExecutor()
    with pytest.raises(BusinessToolError, match="缺少必要字段"):
        executor.execute(
            context=_context("tracking_query", {}),
            user_id="user-1",
        )
