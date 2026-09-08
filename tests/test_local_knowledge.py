from pathlib import Path

import pytest

from app.rag.local_client import LocalKnowledgeClient, LocalKnowledgeError
from app.rag.client import RAGFlowError, SearchResult
from app.rag.config import RAGConfig
from app.rag.retriever import KnowledgeRetriever


def test_local_search_returns_matching_source_and_metadata(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        '{"chunk_id":"c1","text":"酒和烟草属于禁寄或限寄物品。",'
        '"metadata":{"document_name":"顺丰规则.md","topic":"禁寄和限寄"}}\n',
        encoding="utf-8",
    )

    results = LocalKnowledgeClient(corpus).search("酒能寄吗")

    assert len(results) == 1
    assert results[0].document_name == "顺丰规则.md"
    assert results[0].metadata["topic"] == "禁寄和限寄"
    assert results[0].metadata["retrieval_backend"] == "local_lexical"


def test_local_search_does_not_return_unmatched_chunks(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        '{"chunk_id":"c1","text":"顺丰运费按重量计算。","metadata":{}}\n',
        encoding="utf-8",
    )

    assert LocalKnowledgeClient(corpus).search("完全无关的问题") == []


def test_local_search_reports_missing_corpus(tmp_path: Path):
    with pytest.raises(LocalKnowledgeError, match="not found"):
        LocalKnowledgeClient(tmp_path / "missing.jsonl").search("酒能寄吗")


def test_retriever_prefers_ragflow_when_configured():
    class FakeRAGFlow:
        def search(self, question, *, top_k):
            return [
                SearchResult(
                    content="RAGFlow 内容",
                    score=0.9,
                    document_name="ragflow.md",
                    metadata={},
                )
            ]

    class FailingLocal:
        def search(self, question, *, top_k):
            raise AssertionError("local fallback should not be called")

    retriever = KnowledgeRetriever(
        ragflow=FakeRAGFlow(),
        local=FailingLocal(),
        config_loader=lambda: RAGConfig(
            api_key="secret",
            dataset_id="dataset-1",
        ),
    )

    results = retriever.search("测试")

    assert results[0].content == "RAGFlow 内容"
    assert results[0].metadata["retrieval_backend"] == "ragflow"


def test_retriever_falls_back_to_local_when_ragflow_fails(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        '{"chunk_id":"c1","text":"酒属于禁寄物品。",'
        '"metadata":{"document_name":"local.md"}}\n',
        encoding="utf-8",
    )

    class BrokenRAGFlow:
        def search(self, question, *, top_k):
            raise RAGFlowError("timeout")

    retriever = KnowledgeRetriever(
        ragflow=BrokenRAGFlow(),
        local=LocalKnowledgeClient(corpus),
        config_loader=lambda: RAGConfig(
            api_key="secret",
            dataset_id="dataset-1",
        ),
    )

    results = retriever.search("酒能寄吗")

    assert results[0].document_name == "local.md"
    assert results[0].metadata["retrieval_backend"] == "local_fallback"
