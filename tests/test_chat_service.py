from app.agent.chat_service import ChatService
from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.intent_schema import IntentResult
from app.agent.session_manager import SessionManager


def _payload(intent="tracking_query", order_id="ORD1001", action="query"):
    return {
        "intent": intent,
        "confidence": 0.95,
        "entities": {
            "order_id": order_id,
            "ticket_no": None,
            "new_address": None,
            "complaint_content": None,
            "contact": None,
        },
        "missing_slots": [],
        "action": action,
        "should_call_tool": True,
    }


class FakeDifyClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.responses)


class RecordingToolExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": "订单已查询"}


def test_chat_service_parses_merges_and_executes_only_after_gate():
    dify = FakeDifyClient(
        [
            {
                "answer": "正在查询",
                "conversation_id": "conv-1",
                "result_json": __import__("json").dumps(_payload()),
            }
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="session-1",
        user_id="user-1",
        message="查一下 ORD1001 到哪里了",
    )

    assert result.intent_result.intent == "tracking_query"
    assert result.context.effective_entities.order_id == "ORD1001"
    assert result.context.should_call_tool is True
    assert len(tools.calls) == 1
    assert dify.calls[0]["conversation_id"] is None


def test_chat_service_accepts_final_answer_without_executing_tool_again():
    dify = FakeDifyClient(
        [
            {
                "answer": __import__("json").dumps(
                    {"final_answer": "订单目前正在运输中。"},
                    ensure_ascii=False,
                ),
                "conversation_id": "conv-final-answer",
            }
        ]
    )
    tools = RecordingToolExecutor()
    session_manager = SessionManager(InMemorySessionStore())
    session_manager.process_turn(
        session_id="session-final-answer",
        user_message="查一下 ORD1001 到哪里了",
        intent_result=IntentResult.model_validate(_payload()),
        user_id="user-final-answer",
    )
    session_manager.record_tool_result(
        "session-final-answer",
        {"type": "tracking", "data": {"order_no": "ORD1001"}},
    )
    service = ChatService(
        dify_client=dify,
        session_manager=session_manager,
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="session-final-answer",
        user_id="user-final-answer",
        message="查一下 ORD1001 到哪里了",
    )

    assert result.answer == "订单目前正在运输中。"
    assert result.intent_result.intent == "tracking_query"
    assert result.tool_result["type"] == "tracking"
    assert tools.calls == []


def test_invalid_final_answer_uses_safe_tool_fallback():
    dify = FakeDifyClient(
        [
            {
                "answer": __import__("json").dumps(
                    {"final_answer": '{"tool_result": "泄漏"}'},
                    ensure_ascii=False,
                ),
                "conversation_id": "conv-invalid-final-answer",
            }
        ]
    )
    session_manager = SessionManager(InMemorySessionStore())
    session_manager.process_turn(
        session_id="session-invalid-final-answer",
        user_message="查一下 ORD1001 到哪里了",
        intent_result=IntentResult.model_validate(_payload()),
        user_id="user-invalid-final-answer",
    )
    session_manager.record_tool_result(
        "session-invalid-final-answer",
        {
            "type": "tracking",
            "data": {
                "order_no": "ORD1001",
                "status": "in_transit",
            },
        },
    )
    service = ChatService(
        dify_client=dify,
        session_manager=session_manager,
        tool_executor=RecordingToolExecutor(),
    )

    result = service.handle_message(
        session_id="session-invalid-final-answer",
        user_id="user-invalid-final-answer",
        message="查一下 ORD1001 到哪里了",
    )

    assert "订单 ORD1001" in result.answer
    assert "tool_result" not in result.answer


def test_final_answer_with_think_trace_keeps_customer_text_only():
    dify = FakeDifyClient(
        [
            {
                "answer": __import__("json").dumps(
                    {
                        "final_answer": (
                            "<think>internal reasoning</think>"
                            "订单目前正在运输中。"
                        )
                    },
                    ensure_ascii=False,
                ),
                "conversation_id": "conv-think-final-answer",
            }
        ]
    )
    session_manager = SessionManager(InMemorySessionStore())
    session_manager.process_turn(
        session_id="session-think-final-answer",
        user_id="user-think-final-answer",
        user_message="查一下 ORD1001 到哪里了",
        intent_result=IntentResult.model_validate(_payload()),
    )
    session_manager.record_tool_result(
        "session-think-final-answer",
        {
            "type": "tracking",
            "data": {
                "order_no": "ORD1001",
                "status": "in_transit",
            },
        },
    )
    service = ChatService(
        dify_client=dify,
        session_manager=session_manager,
        tool_executor=RecordingToolExecutor(),
    )

    result = service.handle_message(
        session_id="session-think-final-answer",
        user_id="user-think-final-answer",
        message="查一下 ORD1001 到哪里了",
    )

    assert "<think>" not in result.answer
    assert "internal reasoning" not in result.answer
    assert result.answer == "订单目前正在运输中。"


def test_legacy_answer_with_think_trace_keeps_customer_text_only():
    payload = _payload(
        intent="address_change",
        order_id=None,
        action="collect_info",
    )
    payload["missing_slots"] = ["order_id", "new_address"]
    payload["should_call_tool"] = False
    dify = FakeDifyClient(
        [
            {
                "answer": (
                    "<think>internal reasoning</think>"
                    "请提供订单号和新的收货地址。"
                ),
                "conversation_id": "conv-think-legacy-answer",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=RecordingToolExecutor(),
    )

    result = service.handle_message(
        session_id="session-think-legacy-answer",
        user_id="user-think-legacy-answer",
        message="我要修改收货地址",
    )

    assert result.answer == "请提供订单号和新的收货地址。"
    assert "<think>" not in result.answer


def test_unknown_follow_up_after_completed_address_change_does_not_reuse_old_request():
    first = _payload(
        intent="address_change",
        order_id="ORD1001",
        action="confirm",
    )
    first["entities"]["new_address"] = "上海市浦东新区世纪大道100号"
    dify = FakeDifyClient(
        [
            {
                "answer": "已提交",
                "conversation_id": "conv-completed-address",
                "result_json": __import__("json").dumps(first),
            },
            {
                "answer": "请说明您需要处理的具体问题。",
                "conversation_id": "conv-completed-address",
                "result_json": __import__(
                    "json"
                ).dumps(
                    _payload(
                        intent="unknown",
                        order_id=None,
                        action="clarify",
                    )
                ),
            },
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    service.handle_message(
        session_id="completed-address-chat",
        user_id="user-1",
        message="确认提交",
    )
    second = service.handle_message(
        session_id="completed-address-chat",
        user_id="user-1",
        message="帮我处理一下",
    )

    assert second.context.effective_intent == "unknown"
    assert second.context.should_call_tool is False
    assert "ORD1001" not in second.answer
    assert "上海市浦东新区世纪大道100号" not in second.answer
    assert second.context.context["summary"] == "当前没有待处理的业务请求。"
    assert len(tools.calls) == 1


def test_unknown_follow_up_with_pending_address_change_still_requests_missing_slots():
    first = _payload(
        intent="address_change",
        order_id=None,
        action="collect_info",
    )
    first["missing_slots"] = ["order_id", "new_address"]
    first["should_call_tool"] = False
    dify = FakeDifyClient(
        [
            {
                "answer": "请提供订单号和新的收货地址。",
                "conversation_id": "conv-pending-address",
                "result_json": __import__("json").dumps(first),
            },
            {
                "answer": "为了继续修改收货地址，请提供订单号和新的收货地址。",
                "conversation_id": "conv-pending-address",
                "result_json": __import__(
                    "json"
                ).dumps(
                    _payload(
                        intent="unknown",
                        order_id=None,
                        action="clarify",
                    )
                ),
            },
        ]
    )
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=RecordingToolExecutor(),
    )

    service.handle_message(
        session_id="pending-address-chat",
        user_id="user-1",
        message="我要修改收货地址",
    )
    second = service.handle_message(
        session_id="pending-address-chat",
        user_id="user-1",
        message="帮我处理一下",
    )

    assert second.context.effective_intent == "address_change"
    assert second.context.effective_missing_slots == ["order_id", "new_address"]
    assert second.context.should_call_tool is False
    assert "订单号" in second.answer
    assert "新的收货地址" in second.answer


def test_invalid_dify_output_is_safe_and_does_not_call_tool():
    dify = FakeDifyClient(
        [{"answer": "无法识别", "conversation_id": "conv-2", "result_json": "bad"}]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="session-2",
        user_id="user-2",
        message="帮我处理",
    )

    assert result.intent_result.intent == "unknown"
    assert result.context.should_call_tool is False
    assert tools.calls == []


def test_nested_dify_outputs_are_supported():
    dify = FakeDifyClient(
        [
            {
                "answer": "已识别",
                "conversation_id": "conv-nested",
                "data": {"outputs": {"result_json": __import__("json").dumps(_payload())}},
            }
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="session-nested",
        user_id="user-nested",
        message="查 ORD1001",
    )

    assert result.intent_result.intent == "tracking_query"
    assert result.context.should_call_tool is True


def test_backend_wrapped_answer_output_is_supported():
    import json

    dify = FakeDifyClient(
        [
            {
                "answer": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "answer": "订单已查询",
                            "intent_result": _payload(),
                        },
                    }
                ),
                "conversation_id": "conv-backend-wrapped",
            }
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="session-backend-wrapped",
        user_id="user-backend-wrapped",
        message="查 ORD1001",
    )

    assert result.intent_result.intent == "tracking_query"
    assert result.context.should_call_tool is True
    assert len(tools.calls) == 1


def test_backend_wrapped_internal_answer_is_not_shown_as_json():
    import json

    payload = _payload(
        intent="address_change",
        order_id=None,
        action="collect_info",
    )
    payload["missing_slots"] = ["order_id", "new_address"]
    payload["should_call_tool"] = False
    dify = FakeDifyClient(
        [
            {
                "answer": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "answer": "当前意图：address_change；已填槽位：无。",
                            "intent_result": payload,
                        },
                    },
                    ensure_ascii=False,
                ),
                "conversation_id": "conv-address-clarify",
                "result_json": json.dumps(payload, ensure_ascii=False),
            }
        ]
    )
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=RecordingToolExecutor(),
    )

    result = service.handle_message(
        session_id="session-address-clarify",
        user_id="user-address-clarify",
        message="我要修改收货地址",
    )

    assert result.answer == "好的，我可以帮您修改收货地址。请提供订单号和新的收货地址。"
    assert "intent_result" not in result.answer
    assert "missing_slots" not in result.answer


def test_human_transfer_without_content_stays_pending():
    payload = _payload(intent="human_transfer", order_id=None, action="collect_info")
    payload["missing_slots"] = ["content"]
    payload["should_call_tool"] = False
    dify = FakeDifyClient(
        [
            {
                "answer": "请说明需要人工处理的问题",
                "conversation_id": "conv-human",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="session-human",
        user_id="user-human",
        message="帮我转人工",
    )

    assert result.context.effective_missing_slots == ["content"]
    assert result.context.should_call_tool is False
    assert tools.calls == []


def test_follow_up_uses_saved_dify_conversation_and_slots():
    first = _payload(
        intent="address_change",
        order_id="ORD1001",
        action="collect_info",
    )
    first["entities"]["new_address"] = "上海市浦东新区张江路1号"
    first["missing_slots"] = []
    first["should_call_tool"] = False
    dify = FakeDifyClient(
        [
            {"answer": "请确认", "conversation_id": "conv-3", "result_json": __import__("json").dumps(first)},
            {
                "answer": "已提交",
                "conversation_id": "conv-3",
                "result_json": __import__("json").dumps(
                    _payload(
                        intent="address_change",
                        order_id=None,
                        action="confirm",
                    )
                ),
            },
        ]
    )
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=RecordingToolExecutor(),
    )

    service.handle_message(
        session_id="session-3",
        user_id="user-3",
        message="ORD1001 改到上海市浦东新区张江路1号",
    )
    second = service.handle_message(
        session_id="session-3",
        user_id="user-3",
        message="确认提交",
    )

    assert dify.calls[1]["conversation_id"] == "conv-3"
    assert dify.calls[1]["inputs"]["slots"]["order_id"] == "ORD1001"
    assert second.context.should_call_tool is True


def test_human_reason_is_injected_as_workflow_content():
    payload = _payload(intent="human_transfer", order_id=None, action="transfer")
    dify = FakeDifyClient(
        [
            {
                "answer": "已转人工",
                "conversation_id": "conv-human-reason",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=RecordingToolExecutor(),
    )

    result = service.handle_message(
        session_id="human-reason",
        user_id="user-1",
        message="请转人工客服，我的包裹有问题",
    )

    assert result.context.slots["content"] == "请转人工客服，我的包裹有问题"
    assert result.context.should_call_tool is True


def test_human_transfer_missing_content_cannot_be_inferred_from_address_problem():
    payload = _payload(intent="human_transfer", order_id=None, action="clarify")
    payload["missing_slots"] = ["content"]
    payload["should_call_tool"] = False
    dify = FakeDifyClient(
        [
            {
                "answer": "请说明需要人工处理的问题",
                "conversation_id": "conv-human-address",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="human-address",
        user_id="user-1",
        message="我需要人工处理地址问题，联系方式 138****0001",
    )

    assert result.context.effective_missing_slots == ["content"]
    assert result.context.should_call_tool is False
    assert result.context.slots.get("content") is None
    assert tools.calls == []


def test_agent_turn_answer_uses_context_summary_when_no_tool_runs():
    payload = _payload(intent="human_transfer", order_id=None, action="clarify")
    payload["missing_slots"] = ["content"]
    payload["should_call_tool"] = False
    dify = FakeDifyClient([])
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=RecordingToolExecutor(),
    )

    result = service.handle_result_json(
        session_id="agent-turn-summary",
        user_id="user-1",
        message="帮我转人工",
        result_json=__import__("json").dumps(payload),
    )

    assert result.answer == "为了继续处理，请提供需要人工处理的问题。"
    assert result.context.effective_missing_slots == ["content"]


def test_knowledge_query_uses_local_tool_with_current_question():
    payload = _payload(intent="knowledge_query", order_id=None)
    dify = FakeDifyClient(
        [
            {
                "answer": "正在查询知识库",
                "conversation_id": "conv-knowledge",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )
    tools = RecordingToolExecutor()
    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=tools,
    )

    result = service.handle_message(
        session_id="knowledge-session",
        user_id="user-knowledge",
        message="顺丰进出口件哪些物品不能寄？",
    )

    assert result.context.slots["question"] == "顺丰进出口件哪些物品不能寄？"
    assert result.context.should_call_tool is True
    assert len(tools.calls) == 1


def test_knowledge_query_answer_contains_context_and_source():
    payload = _payload(intent="knowledge_query", order_id=None)
    dify = FakeDifyClient(
        [
            {
                "answer": "Dify 原始回答",
                "conversation_id": "conv-knowledge-answer",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )

    class KnowledgeToolExecutor:
        def execute(self, **kwargs):
            return {
                "success": True,
                "type": "knowledge_query",
                "data": {
                    "context": "[资料 1] 顺丰规则.md\n酒属于禁寄或限寄物品。",
                    "records": [
                        {
                            "document_name": "顺丰规则.md",
                            "content": "酒属于禁寄或限寄物品。",
                        }
                    ],
                },
            }

    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=KnowledgeToolExecutor(),
    )

    result = service.handle_message(
        session_id="knowledge-answer",
        user_id="user-knowledge",
        message="酒能寄吗？",
    )

    assert "酒属于禁寄或限寄物品" in result.answer
    assert "来源：顺丰规则.md" in result.answer
    assert "Dify 原始回答" not in result.answer


def test_knowledge_query_answer_has_explicit_no_result_fallback():
    payload = _payload(intent="knowledge_query", order_id=None)
    dify = FakeDifyClient(
        [
            {
                "answer": "Dify 原始回答",
                "conversation_id": "conv-knowledge-empty",
                "result_json": __import__("json").dumps(payload),
            }
        ]
    )

    class EmptyKnowledgeToolExecutor:
        def execute(self, **kwargs):
            return {
                "success": True,
                "type": "knowledge_query",
                "data": {"context": "未检索到相关知识库内容。", "records": []},
            }

    service = ChatService(
        dify_client=dify,
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=EmptyKnowledgeToolExecutor(),
    )

    result = service.handle_message(
        session_id="knowledge-empty",
        user_id="user-knowledge",
        message="完全无关的问题",
    )

    assert "暂未检索到明确相关规则" in result.answer
    assert "自行补充结论" in result.answer


def test_tracking_tool_result_is_formatted_for_customers():
    answer = ChatService._answer(
        {},
        None,
        {
            "success": True,
            "type": "tracking",
            "data": {
                "order_no": "ORD1001",
                "carrier": "顺丰速运",
                "tracking_no": "SF1001001",
                "status": "in_transit",
                "tracking_events": [
                    {
                        "event_time": "2026-08-29 12:10:00",
                        "location": "上海浦东转运中心",
                        "description": "包裹正在转运中",
                    }
                ],
            },
        },
    )

    assert answer == (
        "已为您查到订单 ORD1001 的物流信息：\n"
        "物流公司：顺丰速运\n"
        "运单号：SF1001001\n"
        "当前状态：运输中\n"
        "最新进展：2026-08-29 12:10:00，上海浦东转运中心，包裹正在转运中"
    )


def test_ticket_status_tool_result_is_formatted_for_customers():
    answer = ChatService._answer(
        {},
        None,
        {
            "success": True,
            "type": "ticket_status",
            "data": {
                "ticket_no": "TABC12345",
                "status": "processing",
                "order_id": "ORD1001",
            },
        },
    )

    assert answer == (
        "已为您查询工单 TABC12345：\n"
        "当前状态：处理中\n"
        "关联订单：ORD1001"
    )
