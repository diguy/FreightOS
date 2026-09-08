import json
from pathlib import Path

from evaluation.evaluate_knowledge import evaluate_case
from app.rag.local_client import LocalKnowledgeClient
from app.rag.retriever import KnowledgeRetriever


def test_knowledge_case_evaluator_checks_terms_and_source(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "chunk_id": "c1",
                "text": "进出口件中，烟草和酒属于禁寄或限寄物品。",
                "metadata": {"document_name": "顺丰快递规则.md"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    case = {
        "id": "alcohol",
        "question": "酒能寄吗？",
        "required_terms": ["酒", "禁寄"],
        "forbidden_terms": ["一定可以寄"],
        "expected_source_contains": "顺丰快递规则",
    }

    result = evaluate_case(
        case,
        KnowledgeRetriever(
            local=LocalKnowledgeClient(corpus),
            config_loader=lambda: type(
                "Config",
                (),
                {"api_key": "", "dataset_id": "", "score_threshold": 0.0},
            )(),
        ),
    )

    assert result["passed"] is True
