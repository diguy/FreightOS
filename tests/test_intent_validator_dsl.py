from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
import pytest


DSL_PATH = (
    Path(__file__).resolve().parents[1]
    / "deliverables"
    / "物流意图识别-v3-多轮端到端验证-意图评测修正版.yml"
)
DSL_V2_PATH = DSL_PATH.with_name(
    "物流意图识别-v3-多轮端到端验证-意图评测修正版-v2.yml"
)
DSL_V3_PATH = DSL_PATH.with_name(
    "物流意图识别-v3-多轮端到端验证-意图评测修正版-v3.yml"
)
DSL_V5_PATH = DSL_PATH.with_name("物流意图识别-v3-双阶段回答契约-v5.yml")
DSL_V6_PATH = DSL_PATH.with_name(
    "物流意图识别-v3-双阶段回答契约-v6-会话完成态修复.yml"
)


def _validator_code() -> str:
    workflow = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))["workflow"]
    node = next(
        node
        for node in workflow["graph"]["nodes"]
        if node["id"] == "validator"
    )
    return node["data"]["code"]


def _run_validator(raw_json: str, query: str) -> dict:
    namespace: dict[str, object] = {}
    exec(_validator_code(), namespace)
    return namespace["main"](raw_json, query)


def _v6_validator_code() -> str:
    workflow = yaml.safe_load(DSL_V6_PATH.read_text(encoding="utf-8"))["workflow"]
    node = next(
        node
        for node in workflow["graph"]["nodes"]
        if node["id"] == "validator"
    )
    return node["data"]["code"]


def _run_v6_validator(raw_json: str, query: str) -> dict:
    namespace: dict[str, object] = {}
    exec(_v6_validator_code(), namespace)
    return namespace["main"](raw_json, query)


def _human_transfer_payload() -> str:
    return (
        '{"intent":"human_transfer","confidence":0.98,'
        '"entities":{"order_id":null,"ticket_no":null,"new_address":null,'
        '"complaint_content":null,"contact":"138****0001"},'
        '"missing_slots":[],"action":"transfer","should_call_tool":true}'
    )


def test_dsl_blocks_vague_address_problem_with_contact_only():
    result = _run_validator(
        _human_transfer_payload(),
        "我需要人工处理地址问题，联系方式 138****0001",
    )

    assert result["intent"] == "human_transfer"
    assert result["should_call_tool"] is False
    assert '"missing_slots": ["content"]' in result["result_json"]
    assert '"contact": "138****0001"' in result["result_json"]


def test_dsl_allows_human_transfer_with_concrete_package_problem():
    result = _run_validator(
        _human_transfer_payload(),
        "请转人工客服，我的包裹有问题",
    )

    assert result["should_call_tool"] is True
    assert '"missing_slots": []' in result["result_json"]


def test_dsl_keeps_complaint_content_boundary_and_masked_contact():
    raw = (
        '{"intent":"complaint","confidence":0.95,'
        '"entities":{"order_id":null,"ticket_no":null,"new_address":null,'
        '"complaint_content":"物流异常导致包裹破损，帮我投诉",'
        '"contact":"138****0001"},'
        '"missing_slots":[],"action":"transfer","should_call_tool":true}'
    )

    result = _run_validator(raw, "物流异常导致包裹破损，帮我投诉，联系方式 138****0001")

    assert result["should_call_tool"] is True
    assert '"complaint_content": "物流异常导致包裹破损"' in result["result_json"]
    assert '"contact": "138****0001"' in result["result_json"]


def _complaint_payload(
    *,
    order_id: str | None,
    complaint_content: str | None,
    contact: str | None,
) -> str:
    return json.dumps(
        {
            "intent": "complaint",
            "confidence": 0.95,
            "entities": {
                "order_id": order_id,
                "ticket_no": None,
                "new_address": None,
                "complaint_content": complaint_content,
                "contact": contact,
            },
            "missing_slots": [],
            "action": "transfer",
            "should_call_tool": True,
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    ("query", "payload_content", "expected_content", "order_id", "contact"),
    [
        (
            "ORD1003 的包裹一直不动，我要投诉，联系方式 138****0001",
            "包裹一直不动，我要投诉",
            "包裹一直不动",
            "ORD1003",
            "138****0001",
        ),
        (
            "快递员态度很差，请帮我提交投诉，电话 13800138000",
            "快递员态度很差",
            "快递员态度很差",
            None,
            "13800138000",
        ),
        (
            "物流异常导致包裹破损，联系人是张三，手机号 138****0001",
            "物流异常导致包裹破损",
            "物流异常导致包裹破损",
            None,
            "张三，手机号 138****0001",
        ),
    ],
)
def test_v6_validator_keeps_complete_complaint_fields(
    query,
    payload_content,
    expected_content,
    order_id,
    contact,
):
    result = _run_v6_validator(
        _complaint_payload(
            order_id=order_id,
            complaint_content=payload_content,
            contact=contact,
        ),
        query,
    )
    output = json.loads(result["result_json"])

    assert output["intent"] == "complaint"
    assert output["entities"]["order_id"] == order_id
    assert output["entities"]["complaint_content"] == expected_content
    assert output["entities"]["contact"] == contact
    assert output["missing_slots"] == []
    assert output["should_call_tool"] is True


def test_v6_validator_blocks_intent_017_when_complaint_content_is_missing():
    result = _run_v6_validator(
        _complaint_payload(
            order_id="ORD1003",
            complaint_content=None,
            contact="138****0001",
        ),
        "ORD1003 的包裹一直不动，我要投诉，联系方式 138****0001",
    )
    output = json.loads(result["result_json"])

    assert output["entities"]["complaint_content"] is None
    assert output["missing_slots"] == ["complaint_content"]
    assert output["should_call_tool"] is False


def test_v6_validator_keeps_human_transfer_gate():
    vague = _run_v6_validator(
        _human_transfer_payload(),
        "我需要人工处理地址问题，联系方式 138****0001",
    )
    concrete = _run_v6_validator(
        _human_transfer_payload(),
        "请转人工客服，我的包裹有问题",
    )

    assert json.loads(vague["result_json"])["missing_slots"] == ["content"]
    assert vague["should_call_tool"] is False
    assert concrete["should_call_tool"] is True


def test_v6_validator_keeps_address_change_confirmation_gate():
    payload = json.dumps(
        {
            "intent": "address_change",
            "confidence": 0.95,
            "entities": {
                "order_id": "ORD1001",
                "ticket_no": None,
                "new_address": "上海市浦东新区张江路1号",
                "complaint_content": None,
                "contact": None,
            },
            "missing_slots": [],
            "action": "confirm",
            "should_call_tool": True,
        },
        ensure_ascii=False,
    )

    confirmed = _run_v6_validator(
        payload,
        "确认提交",
    )
    unconfirmed = _run_v6_validator(
        payload,
        "我想改成这个地址",
    )

    assert confirmed["should_call_tool"] is True
    assert unconfirmed["should_call_tool"] is False


def test_dsl_v2_maps_http_body_fields_individually():
    workflow = yaml.safe_load(DSL_V2_PATH.read_text(encoding="utf-8"))["workflow"]
    node = next(
        node for node in workflow["graph"]["nodes"] if node["id"] == "backend_http"
    )
    body = node["data"]["body"]
    fields = {item["key"]: item for item in body["data"]}

    assert body["type"] == "json"
    assert set(fields) == {
        "session_id",
        "message",
        "result_json",
        "dify_conversation_id",
    }
    assert fields["result_json"]["value"] == "{{#validator.result_json#}}"
    assert '"result_json":"{{#validator.result_json#}}"' not in str(body)


def test_dsl_v3_uses_one_json_body_item_and_structured_result_json():
    workflow = yaml.safe_load(DSL_V3_PATH.read_text(encoding="utf-8"))["workflow"]
    node = next(
        node for node in workflow["graph"]["nodes"] if node["id"] == "backend_http"
    )
    body = node["data"]["body"]

    assert body["type"] == "json"
    assert len(body["data"]) == 1
    value = body["data"][0]["value"]
    assert '"result_json":{{#validator.result_json#}}' in value


def test_dsl_v5_adds_answer_stage_and_keeps_final_answer_boundary():
    workflow = yaml.safe_load(DSL_V5_PATH.read_text(encoding="utf-8"))["workflow"]
    nodes = {node["id"]: node for node in workflow["graph"]["nodes"]}
    edges = {
        (edge["source"], edge["target"])
        for edge in workflow["graph"]["edges"]
    }

    assert {"intent_llm", "validator", "backend_http", "answer_llm", "result_answer"} <= set(nodes)
    assert ("backend_http", "answer_llm") in edges
    assert ("answer_llm", "result_answer") in edges
    assert nodes["result_answer"]["data"]["answer"] == "{{#answer_llm.text#}}"
    prompt = nodes["answer_llm"]["data"]["prompt_template"][0]["text"]
    for selector in (
        "{{#sys.query#}}",
        "{{#history_summary#}}",
        "{{#recent_turns#}}",
        "{{#backend_http.body#}}",
        "{{#answer_system_prompt#}}",
    ):
        assert selector in prompt
    assert "effective_session_context" in prompt
    assert "tool_result" in prompt
    assert '"final_answer"' in prompt


def test_dsl_v6_blocks_revival_of_completed_requests_for_unknown_turns():
    workflow = yaml.safe_load(DSL_V6_PATH.read_text(encoding="utf-8"))["workflow"]
    nodes = {node["id"]: node for node in workflow["graph"]["nodes"]}
    prompt = nodes["answer_llm"]["data"]["prompt_template"][0]["text"]

    assert "effective_session_context 是当前轮的可信边界" in prompt
    assert "存在待处理任务" in prompt
    assert "effective_missing_slots" in prompt
    assert "awaiting_confirmation" in prompt
    assert "effective_intent 为 unknown、effective_missing_slots 为空" in prompt
    assert "不得根据历史对话恢复或继续已完成" in prompt
