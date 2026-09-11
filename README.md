# FreightOS

An AI-powered customer service agent for the logistics industry, featuring
RAG-based knowledge retrieval and shipment tracking.

## Backend

```powershell
poetry run uvicorn app.main:app --reload --port 8000
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Tests

```powershell
poetry run pytest tests -q
```
