from pathlib import Path

from app.rag.etl import (
    build_chunks,
    chunk_text,
    clean_text,
    infer_metadata,
)


def test_clean_text_removes_page_markers_and_repeated_lines():
    text = "页眉\n页眉\n第一段\r\n\r\n第 1 页\n"

    assert clean_text(text) == "页眉\n第一段"


def test_chunk_text_preserves_paragraphs_and_overlap():
    chunks = chunk_text("一" * 30 + "\n\n" + "二" * 30, max_chars=40, overlap=10)

    assert len(chunks) == 2
    assert chunks[0].startswith("一")
    assert chunks[1].startswith("二")


def test_build_chunks_infers_carrier_and_topic(tmp_path: Path):
    path = tmp_path / "顺丰运费规则.md"
    path.write_text("# 计费规则\n\n实际重量和体积重量取较大值。", encoding="utf-8")

    chunks = build_chunks(path, "2026-09-04")

    assert len(chunks) == 1
    assert chunks[0].metadata.carrier == "顺丰"
    assert chunks[0].metadata.topic == "计费规则"
    assert chunks[0].metadata.query_date == "2026-09-04"


def test_infer_metadata_uses_generic_defaults(tmp_path: Path):
    metadata = infer_metadata(tmp_path / "通用FAQ.md", "2026-09-04")

    assert metadata.carrier == "通用"
    assert metadata.topic == "FAQ"
