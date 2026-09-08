from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IntentName = Literal[
    "tracking_query",
    "knowledge_query",
    "address_change",
    "complaint",
    "human_transfer",
    "ticket_status",
    "unknown",
]


ActionName = Literal[
    "query",
    "collect_info",
    "clarify",
    "transfer",
    "confirm",
    "cancel",
]


class IntentEntities(BaseModel):
    """实体提取结果，只表示当前消息中明确出现的信息。"""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = None
    ticket_no: str | None = None
    new_address: str | None = None
    complaint_content: str | None = None
    contact: str | None = None


class IntentResult(BaseModel):
    """意图识别模块对外输出的统一结构。"""

    model_config = ConfigDict(extra="forbid")

    intent: IntentName
    confidence: float = Field(ge=0.0, le=1.0)
    entities: IntentEntities
    missing_slots: list[str] = Field(default_factory=list)
    action: ActionName
    should_call_tool: bool = False

    @model_validator(mode="after")
    def enforce_tool_call_gate(self) -> "IntentResult":
        """低置信度、未知意图或缺少字段时禁止调用工具。"""

        if (
            self.intent == "unknown"
            or self.confidence < 0.70
            or self.missing_slots
        ):
            self.should_call_tool = False

        return self


def unknown_intent_result(
    *,
    action: ActionName = "clarify",
) -> IntentResult:
    """生成解析失败或无法判断时使用的安全默认结果。"""

    return IntentResult(
        intent="unknown",
        confidence=0.0,
        entities=IntentEntities(),
        missing_slots=[],
        action=action,
        should_call_tool=False,
    )
