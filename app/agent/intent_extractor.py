from dataclasses import dataclass

from app.agent.intent_rules import (
    extract_confirmation,
    extract_contact,
    extract_order_id,
    extract_ticket_no,
)
from app.agent.intent_schema import IntentEntities


@dataclass(frozen=True)
class RuleExtractionResult:
    """高确定性规则提取结果，不包含 LLM 语义判断。"""

    entities: IntentEntities
    confirmation: bool | None


def extract_rule_entities(text: str) -> RuleExtractionResult:
    """组合当前消息的规则提取器，输出统一实体结构。"""

    return RuleExtractionResult(
        entities=IntentEntities(
            order_id=extract_order_id(text),
            ticket_no=extract_ticket_no(text),
            contact=extract_contact(text),
        ),
        confirmation=extract_confirmation(text),
    )
