from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.session_manager import SessionManager


def _result(
    intent,
    *,
    confidence=0.95,
    entities=None,
    missing_slots=None,
    action="query",
    should_call_tool=True,
):
    return IntentResult(
        intent=intent,
        confidence=confidence,
        entities=entities or IntentEntities(),
        missing_slots=missing_slots or [],
        action=action,
        should_call_tool=should_call_tool,
    )


def test_follow_up_turn_fills_previous_tracking_order():
    manager = SessionManager(InMemorySessionStore())
    first = manager.process_turn(
        session_id="s1",
        user_message="我想查物流",
        intent_result=_result(
            "tracking_query",
            entities=IntentEntities(),
            missing_slots=["order_id"],
            action="collect_info",
            should_call_tool=False,
        ),
    )
    second = manager.process_turn(
        session_id="s1",
        user_message="ORD1001",
        intent_result=_result(
            "tracking_query",
            entities=IntentEntities(order_id="ORD1001"),
        ),
    )

    assert first.should_call_tool is False
    assert second.effective_entities.order_id == "ORD1001"
    assert second.effective_missing_slots == []
    assert second.should_call_tool is True


def test_follow_up_turn_fills_ticket_number_before_status_query():
    manager = SessionManager(InMemorySessionStore())
    first = manager.process_turn(
        session_id="ticket-session",
        user_message="我想查询工单进度",
        intent_result=_result(
            "ticket_status",
            missing_slots=["ticket_no"],
            action="collect_info",
            should_call_tool=False,
        ),
    )
    second = manager.process_turn(
        session_id="ticket-session",
        user_message="TABC12345",
        intent_result=_result(
            "ticket_status",
            entities=IntentEntities(ticket_no="TABC12345"),
        ),
    )

    assert first.effective_missing_slots == ["ticket_no"]
    assert first.should_call_tool is False
    assert second.effective_entities.ticket_no == "TABC12345"
    assert second.effective_missing_slots == []
    assert second.should_call_tool is True


def test_unknown_ticket_number_resumes_pending_ticket_status_query():
    manager = SessionManager(InMemorySessionStore())
    manager.process_turn(
        session_id="ticket-unknown-follow-up",
        user_message="我想查询工单进度",
        intent_result=_result(
            "ticket_status",
            missing_slots=["ticket_no"],
            action="collect_info",
            should_call_tool=False,
        ),
    )

    second = manager.process_turn(
        session_id="ticket-unknown-follow-up",
        user_message="TABC12345",
        intent_result=_result(
            "unknown",
            confidence=0.5,
            entities=IntentEntities(ticket_no="TABC12345"),
            action="clarify",
            should_call_tool=False,
        ),
    )

    assert second.effective_intent == "ticket_status"
    assert second.effective_entities.ticket_no == "TABC12345"
    assert second.effective_missing_slots == []
    assert second.should_call_tool is True


def test_unknown_ticket_number_without_pending_status_stays_blocked():
    manager = SessionManager(InMemorySessionStore())

    result = manager.process_turn(
        session_id="ticket-unknown-without-context",
        user_message="TABC12345",
        intent_result=_result(
            "unknown",
            confidence=0.5,
            entities=IntentEntities(ticket_no="TABC12345"),
            action="clarify",
            should_call_tool=False,
        ),
    )

    assert result.effective_intent == "unknown"
    assert result.effective_entities.ticket_no is None
    assert result.should_call_tool is False


def test_address_change_requires_confirmation_after_slots_are_complete():
    manager = SessionManager(InMemorySessionStore())
    pending = manager.process_turn(
        session_id="s2",
        user_message="我要修改收货地址",
        intent_result=_result(
            "address_change",
            entities=IntentEntities(),
            missing_slots=["order_id", "new_address"],
            action="collect_info",
            should_call_tool=False,
        ),
    )
    ready = manager.process_turn(
        session_id="s2",
        user_message="ORD1001，改到上海市浦东新区张江路1号",
        intent_result=_result(
            "address_change",
            entities=IntentEntities(
                order_id="ORD1001",
                new_address="上海市浦东新区张江路1号",
            ),
            action="collect_info",
            should_call_tool=False,
        ),
    )
    confirmed = manager.process_turn(
        session_id="s2",
        user_message="确认提交",
        intent_result=_result(
            "address_change",
            entities=IntentEntities(),
            action="confirm",
            should_call_tool=False,
        ),
    )

    assert pending.effective_missing_slots == ["order_id", "new_address"]
    assert ready.awaiting_confirmation is True
    assert ready.should_call_tool is False
    assert confirmed.awaiting_confirmation is False
    assert confirmed.should_call_tool is True


def test_unknown_turn_does_not_erase_pending_state():
    manager = SessionManager(InMemorySessionStore())
    manager.process_turn(
        session_id="s3",
        user_message="查 ORD1001",
        intent_result=_result(
            "tracking_query",
            entities=IntentEntities(order_id="ORD1001"),
        ),
    )
    result = manager.process_turn(
        session_id="s3",
        user_message="嗯",
        intent_result=_result(
            "unknown",
            confidence=0.2,
            action="clarify",
            should_call_tool=False,
        ),
    )

    assert result.effective_intent == "tracking_query"
    assert result.should_call_tool is False
    assert manager.get_state("s3").turn_no == 2


def test_session_is_bound_to_the_first_user():
    manager = SessionManager(InMemorySessionStore())
    manager.process_turn(
        session_id="s4",
        user_id="user-a",
        user_message="查 ORD1001",
        intent_result=_result(
            "tracking_query",
            entities=IntentEntities(order_id="ORD1001"),
        ),
    )

    try:
        manager.process_turn(
            session_id="s4",
            user_id="user-b",
            user_message="查 ORD1001",
            intent_result=_result(
                "tracking_query",
                entities=IntentEntities(order_id="ORD1001"),
            ),
        )
    except ValueError as error:
        assert str(error) == "session belongs to another user"
    else:
        raise AssertionError("cross-user session reuse should be rejected")


def test_extra_slots_support_non_entity_workflow_values():
    manager = SessionManager(InMemorySessionStore())
    result = manager.process_turn(
        session_id="s5",
        user_message="我要人工处理包裹问题",
        intent_result=_result(
            "human_transfer",
            missing_slots=["content"],
            action="collect_info",
            should_call_tool=False,
        ),
        extra_slots={"content": "包裹问题"},
    )

    assert result.slots["content"] == "包裹问题"
    assert result.effective_missing_slots == []
    assert result.should_call_tool is True


def test_confirmation_turn_resolves_pending_address_change():
    manager = SessionManager(InMemorySessionStore())
    manager.process_turn(
        session_id="s6",
        user_message="ORD1001 改到上海市浦东新区张江路1号",
        intent_result=_result(
            "address_change",
            entities=IntentEntities(
                order_id="ORD1001",
                new_address="上海市浦东新区张江路1号",
            ),
            action="collect_info",
            should_call_tool=False,
        ),
    )

    confirmed = manager.process_turn(
        session_id="s6",
        user_message="确认提交",
        intent_result=_result(
            "unknown",
            confidence=0.2,
            action="clarify",
            should_call_tool=False,
        ),
    )

    assert confirmed.effective_intent == "address_change"
    assert confirmed.effective_action == "confirm"
    assert confirmed.should_call_tool is True


def test_complete_address_change_still_waits_when_dify_says_confirm():
    manager = SessionManager(InMemorySessionStore())
    ready = manager.process_turn(
        session_id="s7",
        user_message="ORD1001 改到上海市浦东新区张江路1号",
        intent_result=_result(
            "address_change",
            entities=IntentEntities(
                order_id="ORD1001",
                new_address="上海市浦东新区张江路1号",
            ),
            action="confirm",
            should_call_tool=True,
        ),
    )

    assert ready.awaiting_confirmation is True
    assert ready.effective_action == "confirm"
    assert ready.should_call_tool is False
