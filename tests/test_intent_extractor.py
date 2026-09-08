from app.agent.intent_extractor import extract_rule_entities


def test_rule_extractor_combines_entities_and_confirmation():
    result = extract_rule_entities(
        "请把 ord1001 改成上海市浦东新区张江路1号，"
        "联系电话 138****0001，确认提交"
    )

    assert result.entities.order_id == "ORD1001"
    assert result.entities.contact == "138****0001"
    assert result.confirmation is True
    assert result.entities.ticket_no is None


def test_rule_extractor_returns_empty_optional_values():
    result = extract_rule_entities("我想咨询一下物流规则")

    assert result.entities.order_id is None
    assert result.entities.ticket_no is None
    assert result.entities.contact is None
    assert result.confirmation is None
