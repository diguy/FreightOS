import asyncio
import os
import uuid

import pytest

from app.agent.intent_schema import IntentEntities, IntentResult
from app.agent.redis_session_store import RedisSessionStore
from app.agent.session_manager import SessionManager
from app.rag.config import load_local_env
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _seed_read_only_session(session_id: str, user_id: str) -> RedisSessionStore:
    load_local_env()
    store = RedisSessionStore(
        url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        key_prefix=os.getenv("REDIS_SESSION_KEY_PREFIX", "logistics:session:"),
    )
    SessionManager(store).process_turn(
        session_id=session_id,
        user_id=user_id,
        user_message="查一下 ORD1001 到哪里了",
        intent_result=IntentResult(
            intent="tracking_query",
            confidence=0.95,
            entities=IntentEntities(order_id="ORD1001"),
            missing_slots=[],
            action="query",
            should_call_tool=True,
        ),
    )
    return store


async def _run_protocol(session_id: str, user_id: str):
    env = os.environ.copy()
    env["MCP_USER_ID"] = user_id
    parameters = StdioServerParameters(
        command="poetry",
        args=["run", "python", "-m", "app.mcp.server"],
        cwd=os.getcwd(),
        env=env,
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as client:
            initialized = await client.initialize()
            tools = await client.list_tools()
            result = await client.call_tool(
                "get_order_tracking",
                {
                    "session_id": session_id,
                    "order_id": "ORD1001",
                },
            )
            return initialized, tools, result


@pytest.mark.integration
def test_stdio_protocol_initialize_list_and_read_only_call():
    user_id = "demo-user-001"
    session_id = f"mcp-stdio-{uuid.uuid4().hex}"
    store = _seed_read_only_session(session_id, user_id)

    try:
        initialized, tools, result = asyncio.run(
            _run_protocol(session_id, user_id)
        )
    except Exception as error:
        pytest.fail(f"stdio MCP protocol failed: {error}")
    finally:
        store.delete(session_id)

    assert initialized.server_info.name == "logistics-business-tools"
    assert len(tools.tools) == 6
    assert {tool.name for tool in tools.tools} >= {"get_order_tracking"}
    assert result.is_error is False
    assert "ORD1001" in result.content[0].text
