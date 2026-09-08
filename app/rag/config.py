from dataclasses import dataclass
import os
from pathlib import Path


def load_local_env() -> None:
    """Load the project .env without overriding explicitly exported variables."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _as_float(name: str, default: float) -> float:
    value = os.getenv(name, str(default))
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error


@dataclass(frozen=True)
class RAGConfig:
    """Runtime configuration for the external RAGFlow integration."""

    base_url: str = "http://127.0.0.1:9380"
    api_key: str = ""
    dataset_id: str = ""
    timeout_seconds: float = 30.0
    bm25_weight: float = 0.7
    vector_weight: float = 0.3
    rerank_enabled: bool = True
    rerank_id: str = ""
    score_threshold: float = 0.0

    def __post_init__(self) -> None:
        if not 0 <= self.bm25_weight <= 1:
            raise ValueError("RAGFLOW_BM25_WEIGHT must be between 0 and 1")
        if not 0 <= self.vector_weight <= 1:
            raise ValueError("RAGFLOW_VECTOR_WEIGHT must be between 0 and 1")
        if self.bm25_weight + self.vector_weight <= 0:
            raise ValueError("At least one retrieval weight must be greater than zero")
        if not 0 <= self.score_threshold <= 1:
            raise ValueError("RAGFLOW_SCORE_THRESHOLD must be between 0 and 1")


def get_rag_config() -> RAGConfig:
    load_local_env()
    return RAGConfig(
        base_url=os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380").rstrip("/"),
        api_key=os.getenv("RAGFLOW_API_KEY", ""),
        dataset_id=os.getenv("RAGFLOW_DATASET_ID", ""),
        timeout_seconds=_as_float("RAGFLOW_TIMEOUT_SECONDS", 30.0),
        bm25_weight=_as_float("RAGFLOW_BM25_WEIGHT", 0.7),
        vector_weight=_as_float("RAGFLOW_VECTOR_WEIGHT", 0.3),
        rerank_enabled=os.getenv("RAGFLOW_RERANK_ENABLED", "true").lower() == "true",
        rerank_id=os.getenv("RAGFLOW_RERANK_ID", ""),
        score_threshold=_as_float("RAGFLOW_SCORE_THRESHOLD", 0.0),
    )
