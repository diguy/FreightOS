"""Parse and validate the JSON string returned by the Dify intent workflow."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agent.intent_schema import IntentResult, unknown_intent_result


_THINK_BLOCK_PATTERN = re.compile(
    r"<think>.*?</think>\s*",
    flags=re.IGNORECASE | re.DOTALL,
)
_MARKDOWN_JSON_PATTERN = re.compile(
    r"^```(?:json)?\s*(.*?)\s*```$",
    flags=re.IGNORECASE | re.DOTALL,
)
_ENTITY_FIELDS = {
    "order_id",
    "ticket_no",
    "new_address",
    "complaint_content",
    "contact",
}
_REQUIRED_FIELDS = {
    "intent",
    "confidence",
    "entities",
    "missing_slots",
    "action",
    "should_call_tool",
}


def _clean_result_json(raw: str) -> str:
    """Remove model reasoning and an optional Markdown JSON wrapper."""

    cleaned = _THINK_BLOCK_PATTERN.sub("", raw).strip()
    markdown_match = _MARKDOWN_JSON_PATTERN.match(cleaned)
    if markdown_match:
        cleaned = markdown_match.group(1).strip()
    return cleaned


def _has_valid_shape(payload: dict[str, Any]) -> bool:
    """Check shape-sensitive fields before Pydantic validation."""

    if not _REQUIRED_FIELDS.issubset(payload):
        return False

    if not isinstance(payload["confidence"], (int, float)) or isinstance(
        payload["confidence"], bool
    ):
        return False

    entities = payload["entities"]
    if not isinstance(entities, dict) or set(entities) != _ENTITY_FIELDS:
        return False

    if not isinstance(payload["missing_slots"], list):
        return False
    if not all(isinstance(slot, str) for slot in payload["missing_slots"]):
        return False

    if not isinstance(payload["should_call_tool"], bool):
        return False

    return all(
        value is None or isinstance(value, str)
        for value in entities.values()
    )


def parse_dify_output(result_json: Any) -> IntentResult:
    """Convert a Dify ``result_json`` string into the shared intent model.

    Any malformed, incomplete, or contract-invalid response is converted to
    ``unknown_intent_result`` so downstream tools remain blocked.
    """

    if isinstance(result_json, dict):
        payload = result_json
    elif isinstance(result_json, str) and result_json.strip():
        try:
            cleaned = _clean_result_json(result_json)
            payload = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError, ValueError):
            return unknown_intent_result()
    else:
        return unknown_intent_result()

    try:
        if not isinstance(payload, dict) or not _has_valid_shape(payload):
            return unknown_intent_result()

        return IntentResult.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
        return unknown_intent_result()
