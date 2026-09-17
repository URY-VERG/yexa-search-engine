# YEXA Search Engine

YEXA is an independent search-engine project with a FastAPI backend and a React/Vite frontend. It indexes documents with an inverted index and TF-IDF ranking, then adds title, phrase, source-quality, and freshness signals to rank results.

## Run locally

Start the backend in one terminal:

```bash
cd backend
./venv/bin/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend in a second terminal:

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

The frontend sends `/api` requests to the local backend through Vite's development proxy. To use a deployed backend instead, set `VITE_API_BASE_URL` to its URL.

## API

- `GET /search?query=python` — ranked results
- `GET /health` and `GET /stats` — service/index health
- `POST /documents` — add a document, then automatically index it
- `POST /reindex` — rebuild the full index

Interactive API documentation is available at `http://localhost:8000/docs`.
