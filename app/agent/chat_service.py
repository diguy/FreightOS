"""Application orchestration for Dify, session state, and business tools."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol

from app.agent.dify_client import DifyClient
from app.agent.dify_output_parser import parse_dify_output
from app.agent.intent_schema import IntentResult
from app.agent.session_manager import SessionManager
from app.agent.session_schema import EffectiveSessionContext


class ToolExecutor(Protocol):
    def execute(
        self,
        *,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Execute an already-gated business action."""


class NoopToolExecutor:
    """Default executor for development before business dispatch is wired."""

    def execute(
        self,
        *,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any] | None:
        return None


@dataclass(frozen=True)
class ChatResult:
    answer: str
    intent_result: IntentResult
    context: EffectiveSessionContext
    tool_result: dict[str, Any] | None = None
    conversation_id: str | None = None


class ChatService:
    """Keep Dify stateless and make Python the stateful orchestration layer."""

    def __init__(
        self,
        *,
        dify_client: DifyClient,
        session_manager: SessionManager,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.dify_client = dify_client
        self.session_manager = session_manager
        self.tool_executor = tool_executor or NoopToolExecutor()

    def handle_message(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
        dify_conversation_id: str | None = None,
    ) -> ChatResult:
        dify_response = self.dify_client.chat(
            query=message,
            user=user_id,
            conversation_id=dify_conversation_id
            or self._stored_conversation_id(session_id),
            inputs=self._dify_inputs(session_id),
        )
        raw_result = self._extract_result_json(dify_response)
        intent_result = parse_dify_output(raw_result)

        return self._process_intent_result(
            session_id=session_id,
            user_id=user_id,
            message=message,
            intent_result=intent_result,
            dify_conversation_id=dify_response.get("conversation_id"),
            answer_response=dify_response,
        )

    def handle_result_json(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
        result_json: Any,
        dify_conversation_id: str | None = None,
    ) -> ChatResult:
        """Process a Dify result already produced by the current workflow.

        This boundary is intentionally Dify-free: it is used when Dify calls
        the Python agent endpoint from inside a workflow.
        """

        intent_result = parse_dify_output(result_json)
        return self._process_intent_result(
            session_id=session_id,
            user_id=user_id,
            message=message,
            intent_result=intent_result,
            dify_conversation_id=dify_conversation_id,
            extra_slots=self._extra_slots(message, intent_result),
            answer_response=None,
        )

    def _process_intent_result(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
        intent_result: IntentResult,
        dify_conversation_id: str | None,
        answer_response: dict[str, Any] | None,
        extra_slots: dict[str, str] | None = None,
    ) -> ChatResult:
        tool_result = None
        context = self.session_manager.process_turn(
            session_id=session_id,
            user_message=message,
            intent_result=intent_result,
            user_id=user_id,
            dify_conversation_id=dify_conversation_id,
            extra_slots=extra_slots or self._extra_slots(message, intent_result),
        )
        if context.should_call_tool:
            tool_result = self.tool_executor.execute(
                context=context,
                user_id=user_id,
            )

        answer = self._answer(answer_response or {}, context, tool_result)
        return ChatResult(
            answer=answer,
            intent_result=intent_result,
            context=context,
            tool_result=tool_result,
            conversation_id=dify_conversation_id,
        )

    @staticmethod
    def _extra_slots(message: str, result: IntentResult) -> dict[str, str]:
        """Fill workflow-only slots when the message contains a concrete reason."""

        if result.intent == "knowledge_query":
            return {"question": message.strip()}

        if result.intent != "human_transfer":
            return {}
        if "content" in result.missing_slots:
            return {}

        transfer_only_phrases = {
            "帮我转人工",
            "转人工",
            "转人工客服",
            "我要人工",
            "人工客服",
        }
        if message.strip() in transfer_only_phrases:
            return {}

        reason_markers = (
            "包裹",
            "订单",
            "物流",
            "地址",
            "投诉",
            "问题",
            "异常",
            "破损",
            "快递员",
        )
        if any(marker in message for marker in reason_markers):
            return {"content": message.strip()}
        return {}

    def _stored_conversation_id(self, session_id: str) -> str | None:
        state = self.session_manager.get_state(session_id)
        return state.dify_conversation_id if state else None

    def _dify_inputs(self, session_id: str) -> dict[str, Any]:
        state = self.session_manager.get_state(session_id)
        if state is None:
            return {}
        return {
            "session_id": session_id,
            "memory_summary": state.summary,
            "slots": state.slots,
            "recent_turns": [
                {
                    "turn_no": turn.turn_no,
                    "user_message": turn.user_message,
                    "intent": turn.intent_result.intent,
                }
                for turn in state.recent_turns
            ],
        }

    @staticmethod
    def _extract_result_json(response: dict[str, Any]) -> Any:
        """Support common Dify answer/output shapes without trusting them."""

        if "result_json" in response:
            return response["result_json"]
        for container_key in ("data", "outputs"):
            container = response.get(container_key)
            if isinstance(container, dict) and "result_json" in container:
                return container["result_json"]
            if isinstance(container, dict):
                outputs = container.get("outputs")
                if isinstance(outputs, dict) and "result_json" in outputs:
                    return outputs["result_json"]

        answer = response.get("answer")
        if isinstance(answer, str):
            try:
                answer_payload = json.loads(answer)
            except (TypeError, ValueError):
                return answer
            if isinstance(answer_payload, dict):
                data = answer_payload.get("data")
                if isinstance(data, dict):
                    if "result_json" in data:
                        return data["result_json"]
                    if "intent_result" in data:
                        return data["intent_result"]
        return answer

    @staticmethod
    def _answer(
        response: dict[str, Any],
        context: EffectiveSessionContext,
        tool_result: dict[str, Any] | None,
    ) -> str:
        if tool_result is not None:
            if tool_result.get("type") == "knowledge_query":
                return _format_knowledge_answer(tool_result)
            data = tool_result.get("data")
            if isinstance(data, dict):
                message = tool_result.get("message") or data.get("message")
                if isinstance(message, str) and message.strip():
                    return message
                if tool_result.get("type") == "tracking":
                    return _format_tracking_answer(data)
                if tool_result.get("type") == "ticket_status":
                    return _format_ticket_status_answer(data)
                if tool_result.get("type") in {
                    "address_change",
                    "complaint",
                    "human_transfer",
                }:
                    return _format_ticket_created_answer(
                        tool_result["type"],
                        data,
                    )
                return "已完成处理，但暂时无法整理出详细结果。"
            return str(tool_result.get("message") or tool_result)
        customer_answer = _extract_customer_answer(response.get("answer"))
        if customer_answer and not _is_internal_summary(customer_answer):
            return customer_answer
        if context.effective_missing_slots:
            return _format_missing_slots(context)
        if context.awaiting_confirmation:
            return "信息已完整，请确认是否提交。"
        if customer_answer:
            return customer_answer
        summary = context.context.get("summary", "")
        if isinstance(summary, str) and summary.strip():
            return summary
        return "我暂时无法处理这个请求，请稍后重试。"


def _extract_customer_answer(raw_answer: Any) -> str | None:
    """Unwrap backend/Dify JSON layers before showing an answer to customers."""

    if not isinstance(raw_answer, str) or not raw_answer.strip():
        return None

    candidate = raw_answer.strip()
    for _ in range(2):
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError):
            break
        if not isinstance(payload, dict):
            break
        nested = payload.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("answer"), str):
            candidate = nested["answer"].strip()
            continue
        if isinstance(payload.get("answer"), str):
            candidate = payload["answer"].strip()
            continue
        break
    return candidate or None


def _is_internal_summary(answer: str) -> bool:
    return answer.startswith("当前意图：") or answer.startswith("已填槽位：")


def _format_missing_slots(context: EffectiveSessionContext) -> str:
    labels = {
        "order_id": "订单号",
        "new_address": "新的收货地址",
        "complaint_content": "投诉内容",
        "contact": "联系方式",
        "ticket_no": "工单号",
        "content": "需要人工处理的问题",
    }
    missing = [
        labels.get(slot, slot)
        for slot in context.effective_missing_slots
    ]
    if context.effective_intent == "address_change":
        return "好的，我可以帮您修改收货地址。请提供订单号和新的收货地址。"
    if len(missing) == 1:
        return f"为了继续处理，请提供{missing[0]}。"
    return f"为了继续处理，请提供：{'、'.join(missing)}。"


def _format_tracking_answer(data: dict[str, Any]) -> str:
    """Convert an order tracking record into customer-facing Chinese."""

    order_no = data.get("order_no", "当前订单")
    carrier = data.get("carrier")
    tracking_no = data.get("tracking_no")
    status = {
        "in_transit": "运输中",
        "delivered": "已签收",
        "exception": "物流异常",
        "cancelled": "已取消",
    }.get(data.get("status"), data.get("status") or "状态未知")
    lines = [f"已为您查到订单 {order_no} 的物流信息："]
    if carrier:
        lines.append(f"物流公司：{carrier}")
    if tracking_no:
        lines.append(f"运单号：{tracking_no}")
    lines.append(f"当前状态：{status}")

    events = data.get("tracking_events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        latest = events[0]
        event_time = latest.get("event_time", "")
        location = latest.get("location", "")
        description = latest.get("description", "")
        lines.append(f"最新进展：{event_time}，{location}，{description}")
    return "\n".join(lines)


def _format_ticket_status_answer(data: dict[str, Any]) -> str:
    """Convert a ticket record into a concise status response."""

    status = {
        "pending": "待处理",
        "processing": "处理中",
        "completed": "已完成",
        "rejected": "已驳回",
        "cancelled": "已取消",
    }.get(data.get("status"), data.get("status") or "状态未知")
    lines = [
        f"已为您查询工单 {data.get('ticket_no', '')}：",
        f"当前状态：{status}",
    ]
    if data.get("order_id"):
        lines.append(f"关联订单：{data['order_id']}")
    return "\n".join(lines)


def _format_ticket_created_answer(
    tool_type: str,
    data: dict[str, Any],
) -> str:
    """Confirm creation of a change, complaint, or human-service ticket."""

    title = {
        "address_change": "地址修改",
        "complaint": "投诉",
        "human_transfer": "人工客服",
    }.get(tool_type, "服务")
    status = {
        "pending": "待处理",
        "processing": "处理中",
        "completed": "已完成",
    }.get(data.get("status"), data.get("status") or "待处理")
    lines = [
        f"已为您提交{title}工单。",
        f"工单号：{data.get('ticket_no', '')}",
        f"当前状态：{status}",
    ]
    if data.get("order_id"):
        lines.append(f"关联订单：{data['order_id']}")
    return "\n".join(lines)


def _format_knowledge_answer(tool_result: dict[str, Any]) -> str:
    """Render a grounded local-knowledge response with traceable sources."""

    data = tool_result.get("data")
    if not isinstance(data, dict):
        return "当前知识库暂时无法返回有效结果，请稍后重试或联系人工客服。"

    records = data.get("records")
    if not isinstance(records, list) or not records:
        return (
            "知识库中暂未检索到明确相关规则，"
            "我不对该问题自行补充结论。建议联系人工客服进一步确认。"
        )

    context = data.get("context")
    answer = str(context).strip() if isinstance(context, str) else ""
    sources = []
    for record in records:
        if not isinstance(record, dict):
            continue
        title = record.get("document_name") or record.get("title")
        if isinstance(title, str) and title.strip() and title not in sources:
            sources.append(title.strip())

    if not answer:
        answer = "已检索到相关知识库内容，请以以下资料为准。"
    if sources:
        answer += "\n\n来源：" + "；".join(sources)
    return answer
