from app.agent.intent_rules import (
    extract_confirmation,
    extract_contact,
    extract_order_id,
    extract_ticket_no,
)


def test_extract_order_id_and_normalize_case():
    assert extract_order_id("请查询 ord1001") == "ORD1001"
    assert extract_order_id("订单号：ORD-1002") == "ORD1002"


def test_extract_order_id_returns_none_when_missing():
    assert extract_order_id("请帮我查询物流") is None


def test_phone_number_is_not_order_id():
    assert extract_order_id("我的手机号是13800138000") is None


def test_tracking_number_is_not_order_id():
    assert extract_order_id("运单号 SF1001001") is None


def test_extract_contact_supports_plain_and_masked_phone():
    assert extract_contact("联系电话：13800138000") == "13800138000"
    assert extract_contact("手机号 138****0001") == "138****0001"


def test_non_phone_number_is_not_contact():
    assert extract_contact("订单金额是 138 元") is None


def test_extract_ticket_no_and_normalize_case():
    assert extract_ticket_no("查询工单 tabc12345") == "TABC12345"


def test_short_or_embedded_ticket_like_text_is_ignored():
    assert extract_ticket_no("今天温度是T123") is None
    assert extract_ticket_no("ABC123456") is None


def test_extract_confirmation():
    assert extract_confirmation("确认提交") is True
    assert extract_confirmation("确定修改") is True
    assert extract_confirmation("我同意") is True


def test_extract_cancellation():
    assert extract_confirmation("取消") is False
    assert extract_confirmation("不要了") is False
    assert extract_confirmation("我再想想") is False


def test_ambiguous_confirmation_returns_none():
    assert extract_confirmation("我确认收到通知") is True
    assert extract_confirmation("我想问一下") is None
