"""Evaluate local/RAGFlow knowledge retrieval and grounded answer output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.business_tool_executor import BusinessToolExecutor
from app.agent.chat_service import ChatService
from app.agent.in_memory_session_store import InMemorySessionStore
from app.agent.session_manager import SessionManager
from app.agent.intent_schema import IntentEntities, IntentResult
from app.rag.retriever import KnowledgeRetriever


def load_cases(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate_case(case: dict, retriever: KnowledgeRetriever) -> dict:
    question = case["question"]
    results = retriever.search(question, top_k=5)
    context = "\n".join(result.content for result in results)
    sources = "\n".join(result.document_name or "" for result in results)
    terms = context + "\n" + sources
    required_ok = all(term in terms for term in case["required_terms"])
    forbidden_ok = all(term not in context for term in case["forbidden_terms"])
    source_ok = (
        not case["expected_source_contains"]
        or case["expected_source_contains"] in sources
    )
    return {
        "id": case["id"],
        "question": question,
        "result_count": len(results),
        "backends": sorted(
            {result.metadata.get("retrieval_backend") for result in results}
        ),
        "required_terms_ok": required_ok,
        "forbidden_terms_ok": forbidden_ok,
        "source_ok": source_ok,
        "passed": required_ok and forbidden_ok and source_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("scripts/evaluation/cases/knowledge_cases.jsonl"),
    )
    args = parser.parse_args()
    results = [
        evaluate_case(case, KnowledgeRetriever())
        for case in load_cases(args.cases)
    ]
    passed = sum(result["passed"] for result in results)
    print(json.dumps({"passed": passed, "total": len(results), "cases": results}, ensure_ascii=False, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
