# RAGFlow Knowledge Base Setup

This repository keeps the existing SQLite order and ticket services unchanged.
RAGFlow is an FAQ retrieval service only.

The planned MySQL business-data migration uses `APP_MYSQL_*` settings and a
separate `logistics` database. Do not reuse RAGFlow's `MYSQL_DATABASE` for
orders or tickets.

## 1. Start dependencies

Copy `.env.example` to `.env`, review passwords, then run:

```powershell
docker compose -f docker-compose.ragflow-deps.yml up -d
```

The compose file is a dependency template. The exact RAGFlow version and its
official application compose file must be pinned separately before starting the
RAGFlow server.

## 2. Prepare documents

Place source files under a local directory, for example `data/knowledge/source`.
The ETL currently supports text PDF, DOCX, TXT and Markdown files.

```powershell
poetry run python scripts/build_knowledge_corpus.py `
  --input data/knowledge/source `
  --output data/knowledge/corpus.jsonl `
  --query-date 2026-09-04
```

Inspect the JSONL output before importing it into RAGFlow. It contains cleaned
chunks and traceable metadata; it does not contain orders, tracking events,
phone numbers or addresses.

## 3. Configure the API adapter

Set `RAGFLOW_BASE_URL`, `RAGFLOW_API_KEY` and `RAGFLOW_DATASET_ID` in the
runtime environment. The local FastAPI adapter exposes:

```text
POST /api/v1/knowledge/search
```

Example request:

```json
{"question":"圆通体积重量怎么算？","top_k":5}
```

The adapter forwards BM25 weight `0.7`, vector weight `0.3` and the rerank flag
to RAGFlow, then returns the result chunks and metadata for Dify.

For the Dify workflow path that does not use Dify's external knowledge-base
import, call this endpoint from an HTTP Request node instead:

```text
POST /api/v1/knowledge/query
Authorization: Bearer <DIFY_EXTERNAL_KNOWLEDGE_API_KEY>
Content-Type: application/json
```

Request body:

```json
{"question":"顺丰进出口件是否禁止寄递液体类物品？","top_k":3}
```

The response contains `context`, which can be passed directly to the
downstream LLM node, plus `records` for citations and debugging.
