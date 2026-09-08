import re


_ORDER_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])ORD[\s-]?(\d{1,})"
    r"(?!\d)",
    re.IGNORECASE,
)
_TICKET_NO_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])T[A-Za-z0-9]{6,}(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:1\d{10}|1\d{2}\*{4}\d{4})(?!\d)",
)

_CONFIRM_PHRASES = (
    "确认提交",
    "确定提交",
    "同意提交",
    "确认修改",
    "确定修改",
    "确认",
    "确定",
    "同意",
)
_CANCEL_PHRASES = (
    "取消",
    "不要了",
    "不用了",
    "不改了",
    "再想想",
)


def extract_order_id(text: str) -> str | None:
    """提取当前消息中明确出现的订单号，并统一为大写。"""

    match = _ORDER_ID_PATTERN.search(text)
    if match is None:
        return None

    return f"ORD{match.group(1)}".upper()


def extract_ticket_no(text: str) -> str | None:
    """提取当前消息中明确出现的工单号，并统一为大写。"""

    match = _TICKET_NO_PATTERN.search(text)
    if match is None:
        return None

    return match.group(0).upper()


def extract_contact(text: str) -> str | None:
    """提取当前消息中明确出现的手机号或脱敏手机号。"""

    match = _PHONE_PATTERN.search(text)
    if match is None:
        return None

    return re.sub(r"\s+", "", match.group(0))


def extract_confirmation(text: str) -> bool | None:
    """识别明确的确认或取消表达，无法判断时返回 None。"""

    if any(phrase in text for phrase in _CANCEL_PHRASES):
        return False

    if any(phrase in text for phrase in _CONFIRM_PHRASES):
        return True

    return None
