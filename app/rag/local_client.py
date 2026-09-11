"""Small local lexical retrieval client for the pre-RAGFlow stage."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.rag.client import SearchResult


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


class LocalKnowledgeError(RuntimeError):
    """Raised when the local knowledge corpus cannot be queried."""


class LocalKnowledgeClient:
    """Retrieve corpus chunks with deterministic lexical matching."""

    def __init__(self, corpus_path: Path | None = None) -> None:
        self.corpus_path = corpus_path or self._default_corpus_path()

    def search(self, question: str, *, top_k: int = 5) -> list[SearchResult]:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")
        if top_k < 1 or top_k > 50:
            raise ValueError("top_k must be between 1 and 50")

        records = self._load_records()
        query_tokens = set(_tokens(question))
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in records:
            text = str(record.get("text") or "")
            metadata = record.get("metadata") or {}
            searchable = f"{metadata.get('document_name', '')} {text}"
            score = self._score(query_tokens, searchable)
            if score > 0:
                scored.append((score, record))

        scored.sort(
            key=lambda item: (
                item[0],
                str(item[1].get("metadata", {}).get("document_name", "")),
            ),
            reverse=True,
        )
        return [
            SearchResult(
                content=str(record.get("text") or ""),
                score=round(score, 6),
                document_name=record.get("metadata", {}).get("document_name")
                or record.get("metadata", {}).get("file_name"),
                metadata={
                    **(record.get("metadata") or {}),
                    "chunk_id": record.get("chunk_id"),
                    "retrieval_backend": "local_lexical",
                },
            )
            for score, record in scored[:top_k]
        ]

    def _load_records(self) -> list[dict[str, Any]]:
        if not self.corpus_path.is_file():
            raise LocalKnowledgeError(
                f"local knowledge corpus not found: {self.corpus_path}"
            )

        records: list[dict[str, Any]] = []
        try:
            for line_number, line in enumerate(
                self.corpus_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record must be an object")
                records.append(record)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise LocalKnowledgeError(
                f"local knowledge corpus is invalid at line {line_number}"
            ) from error
        return records

    @staticmethod
    def _default_corpus_path() -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "data"
            / "knowledge"
            / "corpus.jsonl"
        )

    @staticmethod
    def _score(query_tokens: set[str], text: str) -> float:
        document_tokens = set(_tokens(text))
        if not query_tokens or not document_tokens:
            return 0.0
        return len(query_tokens & document_tokens) / len(query_tokens)


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]
