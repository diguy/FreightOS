"""HTTP adapter for the stateful Dify chat orchestration service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.business_tool_executor import BusinessToolError
from app.agent.chat_service import ChatService
from app.agent.dify_client import DifyClientError
from app.core.errors import ErrorCode
from app.core.responses import ApiResponse, ErrorInfo


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    dify_conversation_id: str | None = Field(default=None, max_length=200)


class AgentTurnRequest(BaseModel):
    """One Dify workflow turn handed to the Python stateful agent layer."""

    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    result_json: str | dict[str, object] = Field(min_length=1, max_length=20000)
    dify_conversation_id: str | None = Field(default=None, max_length=200)


def get_chat_service() -> ChatService:
    """Dependency hook; tests can override it without changing route code."""

    from app.main import chat_service

    return chat_service


router = APIRouter(prefix="/api/v1/chat", tags=["会话"])
agent_router = APIRouter(prefix="/api/v1/agent", tags=["Agent 编排"])


@router.post("")
def chat(
    request: ChatRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    service: ChatService = Depends(get_chat_service),
):
    if not x_user_id:
        return JSONResponse(
            status_code=400,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorInfo(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    message="缺少用户身份信息",
                ),
            ).model_dump(),
        )

    try:
        result = service.handle_message(
            session_id=request.session_id,
            user_id=x_user_id,
            message=request.message,
            dify_conversation_id=request.dify_conversation_id,
        )
    except DifyClientError as error:
        return JSONResponse(
            status_code=503,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorInfo(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message=str(error),
                ),
            ).model_dump(),
        )
    except BusinessToolError as error:
        return JSONResponse(
            status_code=400,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorInfo(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    message=str(error),
                ),
            ).model_dump(),
        )

    return ApiResponse(
        success=True,
        data={
            "answer": result.answer,
            "conversation_id": result.conversation_id,
            "intent_result": result.intent_result.model_dump(),
            "context": result.context.model_dump(),
            "answer_context": {
                "current_message": request.message,
                "effective_session_context": result.context.model_dump(),
                "tool_result": result.tool_result,
            },
            "tool_result": result.tool_result,
        },
        error=None,
    )


@agent_router.post("/turn")
def agent_turn(
    request: AgentTurnRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    service: ChatService = Depends(get_chat_service),
):
    """Accept Dify's current-turn JSON and run state/tool orchestration."""

    if not x_user_id:
        return JSONResponse(
            status_code=400,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorInfo(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    message="缺少用户身份信息",
                ),
            ).model_dump(),
        )

    try:
        result = service.handle_result_json(
            session_id=request.session_id,
            user_id=x_user_id,
            message=request.message,
            result_json=request.result_json,
            dify_conversation_id=request.dify_conversation_id,
        )
    except BusinessToolError as error:
        return JSONResponse(
            status_code=400,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorInfo(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    message=str(error),
                ),
            ).model_dump(),
        )
    except ValueError as error:
        return JSONResponse(
            status_code=409,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorInfo(
                    code=ErrorCode.ORDER_ACCESS_DENIED,
                    message=str(error),
                ),
            ).model_dump(),
        )

    return ApiResponse(
        success=True,
        data={
            "answer": result.answer,
            "conversation_id": result.conversation_id,
            "intent_result": result.intent_result.model_dump(),
            "context": result.context.model_dump(),
            "answer_context": {
                "current_message": request.message,
                "effective_session_context": result.context.model_dump(),
                "tool_result": result.tool_result,
            },
            "tool_result": result.tool_result,
        },
        error=None,
    )
