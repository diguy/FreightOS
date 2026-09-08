"""MCP-style metadata and guarded dispatch for business tools.

This module intentionally does not depend on an MCP transport SDK. It keeps
the tool contract and authorization boundary independent from the eventual
server or framework integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.agent.business_tool_executor import BusinessToolExecutor
from app.agent.session_schema import EffectiveSessionContext


class McpAdapterError(ValueError):
    """Raised when an MCP tool request is invalid or not authorized."""


@dataclass(frozen=True)
class McpToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool
    required_intent: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "readOnlyHint": self.read_only,
                "destructiveHint": not self.read_only,
            },
        }


_TOOL_DEFINITIONS = (
    McpToolDefinition(
        name="get_order_tracking",
        description="查询当前用户有权访问的订单物流轨迹。",
        required_intent="tracking_query",
        read_only=True,
        input_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string", "minLength": 1}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
    ),
    McpToolDefinition(
        name="get_ticket_status",
        description="查询当前用户有权访问的工单状态。",
        required_intent="ticket_status",
        read_only=True,
        input_schema={
            "type": "object",
            "properties": {"ticket_no": {"type": "string", "minLength": 1}},
            "required": ["ticket_no"],
            "additionalProperties": False,
        },
    ),
    McpToolDefinition(
        name="search_knowledge",
        description="检索物流知识库中的相关资料。",
        required_intent="knowledge_query",
        read_only=True,
        input_schema={
            "type": "object",
            "properties": {"question": {"type": "string", "minLength": 1}},
            "required": ["question"],
            "additionalProperties": False,
        },
    ),
    McpToolDefinition(
        name="create_address_change_ticket",
        description="在当前会话已完成地址确认后创建改址工单。",
        required_intent="address_change",
        read_only=False,
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "minLength": 1},
                "new_address": {"type": "string", "minLength": 5},
                "confirmed": {"const": True},
            },
            "required": ["order_id", "new_address", "confirmed"],
            "additionalProperties": False,
        },
    ),
    McpToolDefinition(
        name="create_complaint_ticket",
        description="创建投诉工单并记录联系方式。",
        required_intent="complaint",
        read_only=False,
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {"type": ["string", "null"]},
                "complaint_content": {"type": "string", "minLength": 1},
                "contact": {"type": "string", "minLength": 3},
            },
            "required": ["complaint_content", "contact"],
            "additionalProperties": False,
        },
    ),
    McpToolDefinition(
        name="create_human_transfer_ticket",
        description="创建人工客服工单。",
        required_intent="human_transfer",
        read_only=False,
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "minLength": 1},
                "contact": {"type": ["string", "null"]},
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    ),
)


class McpToolAdapter:
    """Expose guarded business operations through an MCP-compatible shape."""

    def __init__(self, executor: BusinessToolExecutor | None = None) -> None:
        self.executor = executor or BusinessToolExecutor()
        self._definitions = {tool.name: tool for tool in _TOOL_DEFINITIONS}

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.as_dict() for tool in _TOOL_DEFINITIONS]

    def invoke(
        self,
        name: str,
        *,
        arguments: Mapping[str, Any],
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any] | None:
        tool = self._definitions.get(name)
        if tool is None:
            raise McpAdapterError(f"未知工具：{name}")
        if not user_id.strip():
            raise McpAdapterError("缺少用户身份信息")
        if context.effective_intent != tool.required_intent:
            raise McpAdapterError("当前会话意图与工具不匹配")
        if not context.should_call_tool:
            raise McpAdapterError("当前会话未通过工具调用门控")

        self._validate_arguments(tool, arguments, context)
        return self.executor.execute(context=context, user_id=user_id)

    @staticmethod
    def _validate_arguments(
        tool: McpToolDefinition,
        arguments: Mapping[str, Any],
        context: EffectiveSessionContext,
    ) -> None:
        if not isinstance(arguments, Mapping):
            raise McpAdapterError("工具参数必须是对象")
        allowed = set(tool.input_schema["properties"])
        if set(arguments) - allowed:
            raise McpAdapterError("包含未声明的工具参数")

        for field in tool.input_schema.get("required", []):
            if field not in arguments:
                raise McpAdapterError(f"缺少工具参数：{field}")

        if tool.name == "create_address_change_ticket":
            if arguments.get("confirmed") is not True:
                raise McpAdapterError("改址工具必须明确确认")

        slot_fields = {
            "order_id": "order_id",
            "ticket_no": "ticket_no",
            "new_address": "new_address",
            "complaint_content": "complaint_content",
            "contact": "contact",
            "question": "question",
            "content": "content",
        }
        for argument_name, slot_name in slot_fields.items():
            if argument_name not in arguments:
                continue
            value = arguments[argument_name]
            expected = context.slots.get(slot_name)
            if value is not None and value != expected:
                raise McpAdapterError(f"工具参数与会话槽位不一致：{argument_name}")
