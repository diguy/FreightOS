import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.rag.client import RAGFlowClient, RAGFlowError
from app.rag.config import get_rag_config, load_local_env
from app.rag.local_client import LocalKnowledgeClient, LocalKnowledgeError


router = APIRouter(prefix="/api/v1/knowledge", tags=["知识库"])


class KnowledgeSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)


class DifyRetrievalSetting(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class DifyRetrievalRequest(BaseModel):
    knowledge_id: str = Field(min_length=1, max_length=2000)
    query: str = Field(min_length=1, max_length=2000)
    retrieval_setting: DifyRetrievalSetting


@router.post("/local/search")
def search_local_knowledge(request: KnowledgeSearchRequest):
    """Query the checked-in local corpus without contacting RAGFlow."""
    try:
        results = LocalKnowledgeClient().search(
            request.question,
            top_k=request.top_k,
        )
    except LocalKnowledgeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "success": True,
        "data": {
            "records": [result.to_dict() for result in results],
            "context": _context_from_records(
                _records_from_results(results)
            ),
        },
        "error": None,
    }


def _check_dify_api_key(authorization: str | None) -> None:
    load_local_env()
    expected = os.getenv("DIFY_EXTERNAL_KNOWLEDGE_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="DIFY_EXTERNAL_KNOWLEDGE_API_KEY is not configured",
        )
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid external knowledge API key")


def _records_from_results(results, score_threshold: float = 0.0) -> list[dict]:
    records = []
    for result in results:
        score = float(result.score or 0.0)
        if score < score_threshold:
            continue
        records.append(
            {
                "metadata": result.metadata or {},
                "score": score,
                "title": result.document_name or "",
                "content": result.content,
            }
        )
    return records


def _context_from_records(records: list[dict]) -> str:
    if not records:
        return "未检索到相关知识库内容。"
    sections = []
    for index, record in enumerate(records, start=1):
        title = record["title"] or "未命名资料"
        score = record["score"]
        sections.append(
            f"[资料 {index}] {title}（相关度：{score:.4f}）\n"
            f"{record['content']}"
        )
    return "\n\n".join(sections)


@router.post("/retrieval")
def dify_retrieval(
    request: DifyRetrievalRequest,
    authorization: str | None = Header(default=None),
):
    """Dify External Knowledge API adapter for one RAGFlow dataset."""
    _check_dify_api_key(authorization)
    config = get_rag_config()
    if request.knowledge_id != config.dataset_id:
        raise HTTPException(status_code=404, detail="Unknown external knowledge id")

    try:
        results = RAGFlowClient(config).search(
            request.query,
            top_k=request.retrieval_setting.top_k,
        )
    except RAGFlowError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    records = _records_from_results(
        results,
        request.retrieval_setting.score_threshold,
    )
    return {"records": records}


@router.post("/search")
def search_knowledge(
    request: KnowledgeSearchRequest,
    authorization: str | None = Header(default=None),
):
    """给 Dify HTTP Request 节点调用的 RAGFlow 检索适配入口。"""
    _check_dify_api_key(authorization)
    try:
        config = get_rag_config()
        results = RAGFlowClient(config).search(
            request.question,
            top_k=request.top_k,
        )
    except RAGFlowError as error:
        # Keep the Dify workflow alive so its LLM can produce a useful,
        # non-hallucinating fallback instead of ending with an empty answer.
        return {
            "success": False,
            "context": "当前知识库暂时无法检索，请稍后重试或联系人工客服。",
            "records": [],
            "query": request.question,
            "error": str(error),
        }
    return {
        "success": True,
        "data": {
            "records": [result.to_dict() for result in results],
            "retrieval": {
                "bm25_weight": 1 - config.vector_weight,
                "vector_weight": config.vector_weight,
                "rerank_enabled": config.rerank_enabled and bool(config.rerank_id),
            },
        },
        "error": None,
    }


@router.post("/query")
def query_knowledge_for_dify(
    request: KnowledgeSearchRequest,
    authorization: str | None = Header(default=None),
):
    """返回可直接注入 Dify LLM 提示词的检索上下文。"""
    _check_dify_api_key(authorization)
    try:
        config = get_rag_config()
        results = RAGFlowClient(config).search(
            request.question,
            top_k=request.top_k,
        )
    except RAGFlowError as error:
        # Keep Dify's workflow alive so it can return a clear fallback.
        return {
            "success": False,
            "context": "当前知识库暂时无法检索，请稍后重试或联系人工客服。",
            "records": [],
            "query": request.question,
            "error": str(error),
        }

    records = _records_from_results(results)
    return {
        "success": True,
        "context": _context_from_records(records),
        "records": records,
        "query": request.question,
        "error": None,
    }
