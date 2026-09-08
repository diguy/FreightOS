from dataclasses import dataclass
from typing import Any

import requests

from app.rag.config import RAGConfig, get_rag_config


class RAGFlowError(RuntimeError):
    """Raised when RAGFlow cannot complete a retrieval request."""


@dataclass(frozen=True)
class SearchResult:
    content: str
    score: float | None
    document_name: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "score": self.score,
            "document_name": self.document_name,
            "metadata": self.metadata,
        }


class RAGFlowClient:
    def __init__(self, config: RAGConfig | None = None, session: requests.Session | None = None):
        self.config = config or get_rag_config()
        if session is None:
            session = requests.Session()
            # RAGFlow may be on a directly reachable host; avoid transparent
            # HTTP(S)_PROXY settings turning the retrieval call into a 502.
            session.trust_env = False
        self.session = session

    def search(self, question: str, *, top_k: int = 5) -> list[SearchResult]:
        if not question.strip():
            raise ValueError("question must not be empty")
        if top_k < 1 or top_k > 50:
            raise ValueError("top_k must be between 1 and 50")
        if not self.config.dataset_id:
            raise RAGFlowError("RAGFLOW_DATASET_ID is not configured")

        payload = {
            "question": question,
            "dataset_ids": [self.config.dataset_id],
            "page": 1,
            "page_size": top_k,
            "knn_top_k": max(top_k, 20),
            "knn_num_candidates": max(top_k, 20) * 2,
            "rerank_candidates_count": max(top_k, 20),
            "vector_similarity_weight": self.config.vector_weight,
            "keyword": True,
            "highlight": False,
        }
        if self.config.rerank_enabled and self.config.rerank_id:
            payload["rerank_id"] = self.config.rerank_id
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            response = self.session.post(
                f"{self.config.base_url}/api/v1/retrieval",
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as error:
            raise RAGFlowError(f"RAGFlow retrieval failed: {error}") from error

        if body.get("code", 0) not in (0, 200, None):
            raise RAGFlowError(body.get("message", "RAGFlow returned an error"))
        data = body.get("data") or {}
        chunks = data.get("chunks", []) if isinstance(data, dict) else data
        return [_parse_result(item) for item in chunks]


def _parse_result(item: dict[str, Any]) -> SearchResult:
    metadata = item.get("metadata") or {}
    if not metadata:
        metadata = {
            "document_id": item.get("document_id"),
            "dataset_id": item.get("dataset_id"),
            "source_name": item.get("document_keyword"),
        }
    return SearchResult(
        content=item.get("content") or item.get("chunk") or "",
        score=item.get("score", item.get("similarity")),
        document_name=item.get("document_name") or item.get("document_keyword"),
        metadata=metadata,
    )
