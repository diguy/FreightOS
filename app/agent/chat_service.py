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
                return str(
                    tool_result.get("message")
                    or data.get("message")
                    or data
                )
            return str(tool_result.get("message") or tool_result)
        if isinstance(response.get("answer"), str) and response["answer"].strip():
            return response["answer"]
        summary = context.context.get("summary", "")
        if isinstance(summary, str) and summary.strip():
            return summary
        if context.effective_missing_slots:
            return f"还需要提供：{', '.join(context.effective_missing_slots)}"
        if context.awaiting_confirmation:
            return "信息已完整，请确认是否提交。"
        return "我暂时无法处理这个请求，请稍后重试。"


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
