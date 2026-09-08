"""Knowledge retrieval orchestration for RAGFlow with local fallback."""

from __future__ import annotations

from typing import Callable

from app.rag.client import RAGFlowClient, RAGFlowError, SearchResult
from app.rag.config import get_rag_config
from app.rag.local_client import LocalKnowledgeClient, LocalKnowledgeError


class KnowledgeRetriever:
    """Use RAGFlow when configured and fall back to the local corpus."""

    def __init__(
        self,
        *,
        ragflow: RAGFlowClient | None = None,
        local: LocalKnowledgeClient | None = None,
        config_loader: Callable = get_rag_config,
    ) -> None:
        self.ragflow = ragflow
        self.local = local or LocalKnowledgeClient()
        self.config_loader = config_loader

    def search(self, question: str, *, top_k: int = 5) -> list[SearchResult]:
        config = self.config_loader()
        if config.api_key and config.dataset_id:
            try:
                client = self.ragflow or RAGFlowClient(config)
                results = client.search(question, top_k=top_k)
                return [
                    _with_backend(result, "ragflow")
                    for result in results
                    if _meets_threshold(result, config.score_threshold)
                ]
            except RAGFlowError:
                pass

        try:
            return [
                _with_backend(result, "local_fallback")
                for result in self.local.search(question, top_k=top_k)
                if _meets_threshold(result, config.score_threshold)
            ]
        except LocalKnowledgeError:
            raise


def _with_backend(result: SearchResult, backend: str) -> SearchResult:
    return SearchResult(
        content=result.content,
        score=result.score,
        document_name=result.document_name,
        metadata={**result.metadata, "retrieval_backend": backend},
    )


def _meets_threshold(result: SearchResult, threshold: float) -> bool:
    return result.score is not None and float(result.score) >= threshold
