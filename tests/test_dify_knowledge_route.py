from fastapi.testclient import TestClient

from app.main import app
from app.rag.client import SearchResult
from app.routes import knowledge


def test_dify_retrieval_returns_dify_records(monkeypatch):
    monkeypatch.setenv("DIFY_EXTERNAL_KNOWLEDGE_API_KEY", "secret")
    monkeypatch.setenv("RAGFLOW_DATASET_ID", "dataset-1")

    def fake_search(self, question, *, top_k=5):
        assert question == "酒能寄吗"
        assert top_k == 3
        return [
            SearchResult(
                content="烟草和烟草制品、酒。",
                score=0.82,
                document_name="顺丰禁寄规则.md",
                metadata={"carrier": "顺丰"},
            )
        ]

    monkeypatch.setattr(knowledge.RAGFlowClient, "search", fake_search)
    response = TestClient(app).post(
        "/api/v1/knowledge/retrieval",
        headers={"Authorization": "Bearer secret"},
        json={
            "knowledge_id": "dataset-1",
            "query": "酒能寄吗",
            "retrieval_setting": {"top_k": 3, "score_threshold": 0.8},
        },
    )

    assert response.status_code == 200
    assert response.json()["records"][0]["content"] == "烟草和烟草制品、酒。"
    assert response.json()["records"][0]["score"] == 0.82


def test_dify_retrieval_rejects_invalid_key(monkeypatch):
    monkeypatch.setenv("DIFY_EXTERNAL_KNOWLEDGE_API_KEY", "secret")
    response = TestClient(app).post(
        "/api/v1/knowledge/retrieval",
        headers={"Authorization": "Bearer wrong"},
        json={
            "knowledge_id": "dataset-1",
            "query": "酒",
            "retrieval_setting": {"top_k": 3, "score_threshold": 0},
        },
    )

    assert response.status_code == 401


def test_query_returns_context_for_dify_http_request(monkeypatch):
    monkeypatch.setenv("DIFY_EXTERNAL_KNOWLEDGE_API_KEY", "secret")
    monkeypatch.setenv("RAGFLOW_DATASET_ID", "dataset-1")

    def fake_search(self, question, *, top_k=5):
        assert question == "液体能寄吗"
        assert top_k == 3
        return [
            SearchResult(
                content="液体类物品需要按照进出口件相关规定确认。",
                score=0.91,
                document_name="顺丰禁寄规则.md",
                metadata={"carrier": "顺丰"},
            )
        ]

    monkeypatch.setattr(knowledge.RAGFlowClient, "search", fake_search)
    response = TestClient(app).post(
        "/api/v1/knowledge/query",
        headers={"Authorization": "Bearer secret"},
        json={"question": "液体能寄吗", "top_k": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "液体类物品" in body["context"]
    assert body["records"][0]["title"] == "顺丰禁寄规则.md"


def test_query_returns_non_empty_fallback_when_ragflow_fails(monkeypatch):
    monkeypatch.setenv("DIFY_EXTERNAL_KNOWLEDGE_API_KEY", "secret")

    def broken_search(self, question, *, top_k=5):
        raise knowledge.RAGFlowError("upstream unavailable")

    monkeypatch.setattr(knowledge.RAGFlowClient, "search", broken_search)
    response = TestClient(app).post(
        "/api/v1/knowledge/query",
        headers={"Authorization": "Bearer secret"},
        json={"question": "酒能寄吗", "top_k": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["records"] == []
    assert body["context"]
