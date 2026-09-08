import json

import pytest

from app.agent.dify_output_parser import parse_dify_output


def _payload(**overrides):
    payload = {
        "intent": "tracking_query",
        "confidence": 0.98,
        "entities": {
            "order_id": "ORD1001",
            "ticket_no": None,
            "new_address": None,
            "complaint_content": None,
            "contact": None,
        },
        "missing_slots": [],
        "action": "query",
        "should_call_tool": True,
    }
    payload.update(overrides)
    return payload


def test_parse_standard_dify_json():
    result = parse_dify_output(json.dumps(_payload()))

    assert result.intent == "tracking_query"
    assert result.confidence == pytest.approx(0.98)
    assert result.entities.order_id == "ORD1001"
    assert result.should_call_tool is True


def test_parse_structured_result_object():
    result = parse_dify_output(_payload())

    assert result.intent == "tracking_query"
    assert result.entities.order_id == "ORD1001"


def test_parse_markdown_json_with_think_block():
    raw = (
        "<think>internal reasoning</think>\n"
        "```json\n"
        f"{json.dumps(_payload(), ensure_ascii=False)}\n"
        "```"
    )

    result = parse_dify_output(raw)

    assert result.intent == "tracking_query"
    assert result.entities.order_id == "ORD1001"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "not json",
        "[]",
        '{"intent": "tracking_query"',
        '{"intent": "tracking_query", "confidence": 0.9}',
    ],
)
def test_invalid_result_falls_back_to_unknown(raw):
    result = parse_dify_output(raw)

    assert result.intent == "unknown"
    assert result.confidence == 0.0
    assert result.should_call_tool is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"intent": "not_an_intent"},
        {"action": "not_an_action"},
        {"confidence": -0.01},
        {"confidence": 1.01},
        {"confidence": True},
        {"entities": None},
        {"entities": {"order_id": "ORD1001"}},
        {"missing_slots": "order_id"},
        {"missing_slots": [1]},
        {"should_call_tool": "true"},
    ],
)
def test_contract_violations_fall_back_to_unknown(overrides):
    result = parse_dify_output(json.dumps(_payload(**overrides)))

    assert result.intent == "unknown"
    assert result.should_call_tool is False


def test_low_confidence_cannot_enable_tool_call():
    result = parse_dify_output(
        json.dumps(_payload(confidence=0.69, should_call_tool=True))
    )

    assert result.intent == "tracking_query"
    assert result.should_call_tool is False


def test_missing_slots_cannot_enable_tool_call():
    result = parse_dify_output(
        json.dumps(
            _payload(
                intent="address_change",
                action="collect_info",
                missing_slots=["new_address"],
                should_call_tool=True,
            )
        )
    )

    assert result.intent == "address_change"
    assert result.should_call_tool is False


def test_unknown_intent_cannot_enable_tool_call():
    result = parse_dify_output(
        json.dumps(
            _payload(
                intent="unknown",
                confidence=0.95,
                action="clarify",
                should_call_tool=True,
            )
        )
    )

    assert result.intent == "unknown"
    assert result.should_call_tool is False
