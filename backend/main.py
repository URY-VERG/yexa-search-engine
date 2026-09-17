from contextlib import asynccontextmanager

from ipaddress import ip_address
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

from database.database import create_database, index_stats, page_count, save_page, search_pages
from crawler.crawler import crawl_website
from indexer.index import create_index


def seed_demo_documents() -> None:
    if page_count():
        return
    samples = [
        ("https://yexa.local/flutter", "Flutter Mobile App Development", "Flutter is a framework for building Android, iOS, web, and desktop applications with Dart and reusable widgets."),
        ("https://yexa.local/python", "Python Programming Language", "Python is a versatile programming language used for web development, automation, data science, and artificial intelligence."),
        ("https://yexa.local/artificial-intelligence", "Artificial Intelligence", "Artificial intelligence helps computers learn from data, recognize patterns, and make useful predictions."),
    ]
    for url, title, content in samples:
        save_page(url, title, content)
    create_index()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database()
    seed_demo_documents()
    yield


app = FastAPI(title="YEXA Search API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DocumentCreate(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=20, max_length=100_000)


class CrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(default=1, ge=0, le=3)


def is_safe_crawl_url(url: str) -> bool:
    """Prevent the public crawl endpoint from being used against local networks."""
    hostname = urlparse(url).hostname
    if not hostname or hostname == "localhost":
        return False
    try:
        return not (ip_address(hostname).is_private or ip_address(hostname).is_loopback)
    except ValueError:
        return True


@app.get("/")
def home():
    return {"name": "YEXA", "status": "online", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", **index_stats()}


@app.get("/stats")
def stats():
    return index_stats()


@app.get("/search")
def search(query: str = Query(min_length=1, max_length=200), limit: int = Query(default=10, ge=1, le=20)):
    results = search_pages(query, limit)
    return {"query": query, "total_results": len(results), "results": [
        {**result, "description": result["content"][:300]} for result in results
    ]}


@app.post("/documents", status_code=201)
def add_document(document: DocumentCreate):
    save_page(str(document.url), document.title, document.content)
    return {"status": "indexed", **create_index()}


@app.post("/crawl", status_code=202)
def crawl(request: CrawlRequest):
    target_url = str(request.url)
    if not is_safe_crawl_url(target_url):
        raise HTTPException(status_code=400, detail="Only public HTTP(S) websites can be crawled.")
    report = crawl_website(target_url, max_pages=request.max_pages, max_depth=request.max_depth)
    return {"status": "completed", "crawl": report, **index_stats()}


@app.post("/reindex")
def reindex():
    if not page_count():
        raise HTTPException(status_code=400, detail="No documents are available to index.")
    return {"status": "indexed", **create_index()}
