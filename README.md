# YEXA Search Engine

YEXA is an independent, local-first search-engine MVP. It crawls a controlled portion of a public website or imports local HTML, builds its own inverted index, and ranks results in its own FastAPI service. It is **not** a Google/Bing API wrapper.

## Architecture

```text
React frontend
  → FastAPI query API
    → query tokenization + keyword search
      → inverted index + TF-IDF cosine similarity
        → explainable ranking signals
          → ranked YEXA results

Crawler/local HTML importer → SQLite documents → indexer → inverted + TF-IDF indexes
```

Semantic-vector retrieval and LLM-generated answer summaries are deliberately not included yet. They are future improvements, not advertised as working features.

## Features

- Controlled, same-domain HTML crawler with `robots.txt`, page, and depth limits
- Duplicate URL prevention, fragment removal, redirects checks, and crawl reports
- Local HTML importer for offline/demo content
- SQLite document store with crawl timestamp, depth, response status, and content hash metadata
- Inverted index, TF-IDF, cosine similarity, stop-word filtering, and title weighting
- Explainable ranking: keyword similarity, title/content/URL relevance, exact phrase, source quality, and freshness
- FastAPI validation, JSON errors, health/stats, ingest, crawl, and reindex endpoints
- Responsive React interface with loading, error, no-results, and ranking-detail states

## Tech stack

- Backend: Python, FastAPI, SQLite, Requests, Beautiful Soup
- Frontend: React, Vite

## Project structure

```text
backend/
  crawler/        # web crawler and local HTML importer
  database/       # SQLite storage, query processing, search ranking
  indexer/        # inverted-index and TF-IDF rebuild
  tests/          # automated backend checks
  main.py         # FastAPI application
frontend/
  src/            # YEXA React UI
```

## Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On first start, YEXA seeds three small demo documents so the interface is immediately searchable. Runtime data is stored in `backend/yexa.db` and is intentionally not committed to Git.

## Frontend setup

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open the Vite URL, usually `http://localhost:5173`. In development, Vite proxies `/api` to the backend on port 8000. For a deployed API set `VITE_API_BASE_URL`.

## Crawl and import content

Run a controlled crawl from the backend directory:

```bash
python -m crawler.crawler https://example.org --max-pages 10 --max-depth 1
```

The crawler only follows links on the starting domain, respects a site's `robots.txt` when available, and indexes successfully crawled HTML once the crawl is complete.

To import the included local HTML samples:

```bash
python -m crawler.import_local
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service and index health |
| `GET` | `/stats` | Indexed document and term counts |
| `GET` | `/search?query=python&limit=10` | Explainable ranked search results |
| `POST` | `/documents` | Add one document and rebuild the index |
| `POST` | `/crawl` | Crawl a public HTTP(S) site within validated limits |
| `POST` | `/reindex` | Rebuild all index tables |

Example document ingest:

```json
POST /documents
{
  "url": "https://example.org/guide",
  "title": "YEXA guide",
  "content": "A document must contain enough text for the search index."
}
```

Interactive API documentation is available at `http://localhost:8000/docs`.

## Tests and verification

```bash
cd backend
python -m unittest discover -s tests -v
python -m py_compile main.py database/database.py indexer/index.py crawler/crawler.py crawler/import_local.py

cd ../frontend
npm run lint
npm run build
```

## Future improvements

- Persistent crawl scheduling, sitemap support, and per-domain crawl policy
- Query spelling suggestions and language-aware tokenization
- Vector/semantic retrieval with a locally hosted embedding model
- An answer layer that cites indexed source passages
- Pagination and document-management UI
