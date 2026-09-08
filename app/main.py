from contextlib import asynccontextmanager
from app.routes.tickets import router as tickets_router
from app.routes.knowledge import router as knowledge_router
from app.routes.chat import agent_router as agent_router
from app.routes.chat import router as chat_router
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.routes.orders import router as orders_router
from app.routes.orders import v1_router as orders_v1_router
from app.routes.auth import router as auth_router
from app.services.order_service import init_database
from app.agent.business_tool_executor import BusinessToolExecutor
from app.agent.chat_service import ChatService
from app.agent.dify_client import HttpDifyClient
from app.agent.session_manager import SessionManager
from app.agent.session_store_factory import build_session_store
from app.database_backend import get_business_backend
from app.mysql_database import check_mysql_health


chat_service = ChatService(
    dify_client=HttpDifyClient(),
    session_manager=SessionManager(build_session_store()),
    tool_executor=BusinessToolExecutor(),
)


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="物流客服 Agent API",
    version="0.2.0",
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,
)


@app.get("/health")
def health_check():
    return {
        "success": True,
        "message": "物流客服 API 正常运行",
    }


@app.get("/health/dependencies")
def dependency_health_check():
    result = {
        "success": True,
        "database_backend": get_business_backend(),
        "mysql": {"ok": True, "skipped": True},
        "redis": {"ok": True, "skipped": True},
    }
    if result["database_backend"] == "mysql":
        try:
            result["mysql"] = check_mysql_health()
        except Exception as error:
            result["mysql"] = {"ok": False, "error": type(error).__name__}
    if hasattr(chat_service.session_manager.store, "check_health"):
        try:
            result["redis"] = {
                "ok": chat_service.session_manager.store.check_health()
            }
        except Exception as error:
            result["redis"] = {"ok": False, "error": type(error).__name__}
    result["success"] = all(
        dependency.get("ok", True)
        for dependency in (result["mysql"], result["redis"])
    )
    return result


app.include_router(orders_router)
app.include_router(orders_v1_router)
app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(agent_router)
