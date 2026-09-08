"""Stateful orchestration around the stateless Dify intent result."""

from __future__ import annotations

from datetime import timedelta
from typing import Mapping

from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.intent_rules import extract_confirmation
from app.agent.session_schema import (
    EffectiveSessionContext,
    SessionState,
    SessionTurn,
    utc_now,
)
from app.agent.session_store import SessionStore


_REQUIRED_SLOTS: dict[str, tuple[str, ...]] = {
    "tracking_query": ("order_id",),
    "knowledge_query": (),
    "address_change": ("order_id", "new_address"),
    "complaint": ("complaint_content", "contact"),
    "human_transfer": ("content",),
    "ticket_status": ("ticket_no",),
    "unknown": (),
}
_ENTITY_SLOT_NAMES = {
    "order_id",
    "ticket_no",
    "new_address",
    "complaint_content",
    "contact",
}


class SessionManager:
    """Merge turns, maintain pending work, and expose an effective context."""

    def __init__(
        self,
        store: SessionStore,
        *,
        ttl_seconds: int = 1800,
        max_recent_turns: int = 10,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_recent_turns <= 0:
            raise ValueError("max_recent_turns must be positive")
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.max_recent_turns = max_recent_turns

    def process_turn(
        self,
        *,
        session_id: str,
        user_message: str,
        intent_result: IntentResult,
        user_id: str | None = None,
        dify_conversation_id: str | None = None,
        extra_slots: Mapping[str, str | None] | None = None,
    ) -> EffectiveSessionContext:
        """Apply one parsed Dify turn and return state-resolved context."""

        state = self.store.get(session_id)
        if state is None:
            now = utc_now()
            state = SessionState(
                session_id=session_id,
                user_id=user_id,
                dify_conversation_id=dify_conversation_id,
                created_at=now,
                updated_at=now,
            )
        else:
            self._validate_session_owner(state, user_id)
            if state.user_id is None:
                state.user_id = user_id
            if state.dify_conversation_id is None:
                state.dify_conversation_id = dify_conversation_id

        self._reset_completed_turn(state)
        state.turn_no += 1
        state.updated_at = utc_now()
        state.expires_at = state.updated_at + timedelta(seconds=self.ttl_seconds)
        state.last_tool_result = None

        turn = SessionTurn(
            turn_no=state.turn_no,
            user_message=user_message,
            intent_result=intent_result,
        )
        state.recent_turns.append(turn)
        state.recent_turns = state.recent_turns[-self.max_recent_turns :]

        if intent_result.intent == "unknown":
            if (
                state.active_intent == "ticket_status"
                and state.missing_slots == ["ticket_no"]
                and intent_result.entities.ticket_no
            ):
                state.slots["ticket_no"] = intent_result.entities.ticket_no
                state.missing_slots = []
                state.pending_action = "query"
                state.summary = self._build_summary(state)
                resolved_result = IntentResult(
                    intent="ticket_status",
                    confidence=max(intent_result.confidence, 0.90),
                    entities=IntentEntities(
                        ticket_no=intent_result.entities.ticket_no,
                    ),
                    missing_slots=[],
                    action="query",
                    should_call_tool=True,
                )
                context = self._build_context(state, resolved_result)
                self.store.save(state)
                return context

            confirmation = extract_confirmation(user_message)
            if (
                confirmation is True
                and state.active_intent == "address_change"
                and not state.missing_slots
                and state.awaiting_confirmation
            ):
                state.pending_action = "confirm"
                state.awaiting_confirmation = False
                state.summary = self._build_summary(state)
                confirmed_result = IntentResult(
                    intent="address_change",
                    confidence=0.95,
                    entities=IntentEntities(
                        **{
                            field: state.slots.get(field)
                            for field in _ENTITY_SLOT_NAMES
                        }
                    ),
                    missing_slots=[],
                    action="confirm",
                    should_call_tool=True,
                )
                context = self._build_context(state, confirmed_result)
                self.store.save(state)
                return context
            context = self._build_context(state, intent_result)
            self.store.save(state)
            return context

        previous_intent = state.active_intent
        merged_slots = self._carried_slots(state.slots, previous_intent, intent_result.intent)
        merged_slots.update(self._entity_slots(intent_result))
        if extra_slots:
            merged_slots.update(
                {
                    key: value
                    for key, value in extra_slots.items()
                    if key and value is not None
                }
            )

        if intent_result.action == "cancel":
            state.active_intent = "unknown"
            state.pending_action = "cancel"
            state.slots = {}
            state.missing_slots = []
            state.awaiting_confirmation = False
            state.summary = "当前会话中的待处理请求已取消。"
            context = self._build_context(state, intent_result)
            self.store.save(state)
            return context

        state.active_intent = intent_result.intent
        state.pending_action = intent_result.action
        state.slots = merged_slots
        state.missing_slots = self._missing_slots(intent_result.intent, merged_slots)
        user_confirmed = extract_confirmation(user_message) is True
        state.awaiting_confirmation = (
            intent_result.intent == "address_change"
            and not state.missing_slots
            and not user_confirmed
        )
        if intent_result.intent == "address_change" and user_confirmed:
            state.pending_action = "confirm"
            state.awaiting_confirmation = False
        state.summary = self._build_summary(state)

        context = self._build_context(state, intent_result)
        self.store.save(state)
        return context

    def get_state(self, session_id: str) -> SessionState | None:
        """Read a defensive copy of the current session state."""

        return self.store.get(session_id)

    def get_effective_context(
        self,
        session_id: str,
    ) -> EffectiveSessionContext | None:
        """Rebuild the latest orchestration context without another turn."""

        state = self.store.get(session_id)
        if state is None or not state.recent_turns:
            return None
        return self._build_context(
            state,
            state.recent_turns[-1].intent_result,
        )

    def record_tool_result(
        self,
        session_id: str,
        tool_result: dict | None,
    ) -> None:
        """Persist the latest tool result for answer-stage fallback."""

        state = self.store.get(session_id)
        if state is None:
            return
        state.last_tool_result = tool_result
        state.updated_at = utc_now()
        self.store.save(state)

    @staticmethod
    def _reset_completed_turn(state: SessionState) -> None:
        """Start a fresh request after the previous one completed successfully."""

        if state.last_tool_result is None:
            return
        state.active_intent = "unknown"
        state.pending_action = "clarify"
        state.slots = {
            key: value
            for key, value in state.slots.items()
            if key in {"order_id", "ticket_no"} and value is not None
        }
        state.missing_slots = []
        state.awaiting_confirmation = False
        state.summary = SessionManager._build_summary(state)

    @staticmethod
    def _validate_session_owner(
        state: SessionState,
        user_id: str | None,
    ) -> None:
        if state.user_id is not None and user_id is not None and state.user_id != user_id:
            raise ValueError("session belongs to another user")

    @staticmethod
    def _entity_slots(intent_result: IntentResult) -> dict[str, str]:
        entities = intent_result.entities.model_dump()
        return {
            key: value
            for key, value in entities.items()
            if key in _ENTITY_SLOT_NAMES and value is not None
        }

    @staticmethod
    def _carried_slots(
        previous_slots: dict[str, str | None],
        previous_intent: str,
        current_intent: str,
    ) -> dict[str, str | None]:
        if previous_intent == current_intent:
            return dict(previous_slots)
        # A referenced order/ticket can be reused when the user changes the
        # requested operation, but unrelated address/complaint data cannot.
        reusable = {"order_id", "ticket_no"}
        return {
            key: value
            for key, value in previous_slots.items()
            if key in reusable and value is not None
        }

    @staticmethod
    def _missing_slots(intent: str, slots: Mapping[str, str | None]) -> list[str]:
        return [
            slot
            for slot in _REQUIRED_SLOTS[intent]
            if not slots.get(slot)
        ]

    def _build_context(
        self,
        state: SessionState,
        intent_result: IntentResult,
    ) -> EffectiveSessionContext:
        effective_intent = state.active_intent
        effective_slots = dict(state.slots)
        if intent_result.intent != "unknown":
            effective_intent = intent_result.intent
            effective_slots.update(self._entity_slots(intent_result))

        missing_slots = self._missing_slots(effective_intent, effective_slots)
        awaiting_confirmation = (
            effective_intent == "address_change"
            and not missing_slots
            and state.awaiting_confirmation
        )
        allowed = (
            effective_intent != "unknown"
            and intent_result.confidence >= 0.70
            and not missing_slots
            and not awaiting_confirmation
            and intent_result.action != "cancel"
        )
        effective_entities = IntentEntities(
            **{
                field: effective_slots.get(field)
                for field in _ENTITY_SLOT_NAMES
            }
        )
        context = {
            "session_id": state.session_id,
            "turn_no": state.turn_no,
            "active_intent": effective_intent,
            "slots": effective_slots,
            "missing_slots": missing_slots,
            "awaiting_confirmation": awaiting_confirmation,
            "summary": state.summary,
            "recent_turns": [
                {
                    "turn_no": turn.turn_no,
                    "user_message": turn.user_message,
                    "intent": turn.intent_result.intent,
                    "action": turn.intent_result.action,
                    "entities": turn.intent_result.entities.model_dump(),
                }
                for turn in state.recent_turns
            ],
        }
        return EffectiveSessionContext(
            session_id=state.session_id,
            turn_no=state.turn_no,
            intent_result=intent_result,
            effective_intent=effective_intent,
            effective_action=state.pending_action,
            effective_entities=effective_entities,
            effective_missing_slots=missing_slots,
            awaiting_confirmation=awaiting_confirmation,
            should_call_tool=allowed,
            slots=effective_slots,
            context=context,
        )

    @staticmethod
    def _build_summary(state: SessionState) -> str:
        if state.active_intent == "unknown":
            return "当前没有待处理的业务请求。"
        slot_text = ", ".join(
            f"{key}={value}" for key, value in state.slots.items() if value
        )
        return f"当前意图：{state.active_intent}；已填槽位：{slot_text or '无'}。"
