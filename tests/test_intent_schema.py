import pytest
from pydantic import ValidationError

from app.agent.intent_schema import (
    IntentEntities,
    IntentResult,
    unknown_intent_result,
)


def test_intent_result_accepts_valid_payload():
    result = IntentResult(
        intent="tracking_query",
        confidence=0.95,
        entities=IntentEntities(order_id="ORD1001"),
        missing_slots=[],
        action="query",
        should_call_tool=True,
    )

    assert result.intent == "tracking_query"
    assert result.entities.order_id == "ORD1001"
    assert result.should_call_tool is True


def test_low_confidence_result_cannot_call_tool():
    result = IntentResult(
        intent="tracking_query",
        confidence=0.69,
        entities=IntentEntities(order_id="ORD1001"),
        missing_slots=[],
        action="query",
        should_call_tool=True,
    )

    assert result.should_call_tool is False


def test_missing_slots_result_cannot_call_tool():
    result = IntentResult(
        intent="address_change",
        confidence=0.95,
        entities=IntentEntities(order_id="ORD1001"),
        missing_slots=["new_address"],
        action="collect_info",
        should_call_tool=True,
    )

    assert result.should_call_tool is False


def test_unknown_intent_result_is_safe():
    result = unknown_intent_result()

    assert result.intent == "unknown"
    assert result.confidence == 0.0
    assert result.should_call_tool is False


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        IntentResult(
            intent="tracking_query",
            confidence=1.1,
            entities=IntentEntities(),
            action="query",
        )


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        IntentResult(
            intent="unknown",
            confidence=0.0,
            entities=IntentEntities(),
            action="clarify",
            unexpected="value",
        )
