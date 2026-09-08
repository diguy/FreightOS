import requests

from app.rag.client import RAGFlowClient, RAGFlowError
from app.rag.config import RAGConfig


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "code": 0,
            "data": {
                "chunks": [
                    {
                        "content": "圆通体积重量按长宽高除以8000计算。",
                        "similarity": 0.92,
                        "document_keyword": "圆通计费规则.md",
                        "metadata": {"carrier": "圆通"},
                    }
                ]
            },
        }


class FakeSession:
    def __init__(self):
        self.payload = None

    def post(self, url, **kwargs):
        self.payload = (url, kwargs)
        return FakeResponse()


def test_search_sends_hybrid_retrieval_configuration():
    session = FakeSession()
    client = RAGFlowClient(
        RAGConfig(
            base_url="http://ragflow",
            dataset_id="dataset-1",
            bm25_weight=0.7,
            vector_weight=0.3,
        ),
        session=session,
    )

    results = client.search("圆通体积重量怎么算？")

    assert results[0].metadata["carrier"] == "圆通"
    assert session.payload[0] == "http://ragflow/api/v1/retrieval"
    assert session.payload[1]["json"]["keyword"] is True
    assert session.payload[1]["json"]["vector_similarity_weight"] == 0.3
    assert session.payload[1]["json"]["page_size"] == 5


def test_search_requires_dataset_id():
    client = RAGFlowClient(RAGConfig(base_url="http://ragflow"))

    try:
        client.search("测试")
    except RAGFlowError as error:
        assert "DATASET_ID" in str(error)
    else:
        raise AssertionError("expected RAGFlowError")


def test_search_converts_network_errors():
    class BrokenSession:
        def post(self, *args, **kwargs):
            raise requests.Timeout("timeout")

    client = RAGFlowClient(
        RAGConfig(base_url="http://ragflow", dataset_id="dataset-1"),
        session=BrokenSession(),
    )

    try:
        client.search("测试")
    except RAGFlowError as error:
        assert "retrieval failed" in str(error)
    else:
        raise AssertionError("expected RAGFlowError")
