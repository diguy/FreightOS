"""Dispatch effective session contexts to existing business services."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable

from app.agent.session_schema import EffectiveSessionContext
from app.rag.retriever import KnowledgeRetriever
from app.schemas import AddressChangeRequest, ComplaintRequest, HumanRequest
from app.services.order_service import get_order_tracking
from app.services.ticket_service import (
    create_address_change_ticket,
    create_complaint_ticket,
    create_human_ticket,
    get_ticket,
)


class BusinessToolError(RuntimeError):
    """A business service rejected an otherwise well-formed tool request."""


@dataclass(frozen=True)
class BusinessToolHandlers:
    """Injectable business functions, keeping dispatch logic easy to test."""

    get_order_tracking: Callable[..., dict | None] = get_order_tracking
    get_ticket: Callable[..., dict] = get_ticket
    search_knowledge: Callable[..., list] = KnowledgeRetriever().search
    create_address_change_ticket: Callable[..., dict] = create_address_change_ticket
    create_complaint_ticket: Callable[..., dict] = create_complaint_ticket
    create_human_ticket: Callable[..., dict] = create_human_ticket


class BusinessToolExecutor:
    """Map intent names to existing order and ticket service operations."""

    def __init__(self, handlers: BusinessToolHandlers | None = None) -> None:
        self.handlers = handlers or BusinessToolHandlers()

    def execute(
        self,
        *,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any] | None:
        if not context.should_call_tool:
            return None

        try:
            if context.effective_intent == "tracking_query":
                return self._tracking(context, user_id)
            if context.effective_intent == "ticket_status":
                return self._ticket_status(context, user_id)
            if context.effective_intent == "address_change":
                return self._address_change(context, user_id)
            if context.effective_intent == "complaint":
                return self._complaint(context, user_id)
            if context.effective_intent == "human_transfer":
                return self._human_transfer(context, user_id)
            if context.effective_intent == "knowledge_query":
                return self._knowledge_query(context)
        except (KeyError, TypeError, ValueError) as error:
            raise BusinessToolError(str(error)) from error

        # Knowledge retrieval remains behind its existing dedicated route.
        return None

    def _knowledge_query(
        self,
        context: EffectiveSessionContext,
    ) -> dict[str, Any]:
        question = self._required_slot(context, "question")
        results = self.handlers.search_knowledge(question, top_k=5)
        records = [result.to_dict() for result in results]
        return {
            "success": True,
            "type": "knowledge_query",
            "data": {
                "question": question,
                "records": records,
                "context": _context_from_results(results),
            },
        }

    def _tracking(
        self,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any]:
        order_id = self._required_slot(context, "order_id")
        data = self.handlers.get_order_tracking(order_id, user_id=user_id)
        if data is None:
            raise BusinessToolError("订单不存在或无权访问")
        return {"success": True, "type": "tracking", "data": data}

    def _ticket_status(
        self,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any]:
        ticket_no = self._required_slot(context, "ticket_no")
        data = self.handlers.get_ticket(ticket_no, user_id=user_id)
        return {"success": True, "type": "ticket_status", "data": data}

    def _address_change(
        self,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any]:
        request = AddressChangeRequest(
            order_id=self._required_slot(context, "order_id"),
            new_address=self._required_slot(context, "new_address"),
            confirmed=True,
            client_request_id=self._client_request_id(context),
        )
        data = self.handlers.create_address_change_ticket(
            request,
            user_id=user_id,
        )
        return {"success": True, "type": "address_change", "data": data}

    def _complaint(
        self,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any]:
        request = ComplaintRequest(
            order_id=context.slots.get("order_id"),
            description=self._required_slot(context, "complaint_content"),
            contact=self._required_slot(context, "contact"),
            client_request_id=self._client_request_id(context),
        )
        data = self.handlers.create_complaint_ticket(request, user_id=user_id)
        return {"success": True, "type": "complaint", "data": data}

    def _human_transfer(
        self,
        context: EffectiveSessionContext,
        user_id: str,
    ) -> dict[str, Any]:
        request = HumanRequest(
            content=self._required_slot(context, "content"),
            contact=context.slots.get("contact"),
            client_request_id=self._client_request_id(context),
        )
        data = self.handlers.create_human_ticket(request, user_id=user_id)
        return {"success": True, "type": "human_transfer", "data": data}

    @staticmethod
    def _client_request_id(context: EffectiveSessionContext) -> str:
        """Keep retries of the same session action idempotent."""

        payload = {
            "session_id": context.session_id,
            "intent": context.effective_intent,
            "slots": {
                key: value
                for key, value in sorted(context.slots.items())
                if value is not None
            },
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        return f"agent-{digest}"

    @staticmethod
    def _required_slot(context: EffectiveSessionContext, name: str) -> str:
        value = context.slots.get(name)
        if not isinstance(value, str) or not value.strip():
            raise BusinessToolError(f"缺少必要字段：{name}")
        return value.strip()


def _context_from_results(results: list) -> str:
    if not results:
        return "未检索到相关知识库内容。"
    return "\n\n".join(
        f"[资料 {index}] {result.document_name or '未命名资料'}\n"
        f"{result.content}"
        for index, result in enumerate(results, start=1)
    )
