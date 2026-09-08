"""Run a real, read-only Dify -> Python -> order-service chain test.

This script is opt-in. It never prints the Dify API key and defaults to a
tracking query that does not create or mutate a ticket.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.business_tool_executor import BusinessToolExecutor
from app.agent.chat_service import ChatService
from app.agent.dify_client import DifyClientError, DifySettings, HttpDifyClient
from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.session_manager import SessionManager


def build_service() -> ChatService:
    return ChatService(
        dify_client=HttpDifyClient(DifySettings.from_env()),
        session_manager=SessionManager(InMemorySessionStore()),
        tool_executor=BusinessToolExecutor(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test the live Dify and Python chat chain with a read-only query."
    )
    parser.add_argument(
        "--message",
        default="查一下 ORD1001 到哪里了",
        help="Message sent to Dify; keep the default for a read-only smoke test.",
    )
    parser.add_argument("--session-id", default="live-chain-smoke")
    parser.add_argument("--user-id", default="demo-user-001")
    args = parser.parse_args()

    settings = DifySettings.from_env()
    if not settings.api_key:
        print(
            "未执行：缺少 DIFY_API_KEY。请在 .env 中配置 DIFY_BASE_URL、"
            "DIFY_API_KEY 和可选的 DIFY_TIMEOUT_SECONDS。",
            file=sys.stderr,
        )
        return 2

    try:
        result = build_service().handle_message(
            session_id=args.session_id,
            user_id=args.user_id,
            message=args.message,
        )
    except DifyClientError as error:
        print(f"Dify 链路失败：{error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Python 编排链路失败：{error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "answer": result.answer,
                "conversation_id": result.conversation_id,
                "intent_result": result.intent_result.model_dump(),
                "context": result.context.model_dump(),
                "tool_result": result.tool_result,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    if result.context.effective_intent != "tracking_query":
        print("链路失败：默认只读样例未识别为 tracking_query", file=sys.stderr)
        return 1
    if result.context.effective_entities.order_id != "ORD1001":
        print("链路失败：订单号不是 ORD1001", file=sys.stderr)
        return 1
    if not result.context.should_call_tool or result.tool_result is None:
        print("链路失败：订单查询工具未被正确调用", file=sys.stderr)
        return 1

    print("真实 Dify 链路测试通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
