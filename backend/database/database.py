import hashlib
import math
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

DATABASE_PATH = Path(__file__).resolve().parents[1] / "yexa.db"

STOP_WORDS = {
    "the", "is", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "this", "that", "it", "as", "are", "was", "were",
    "be", "by", "from", "at", "about", "into", "your", "you",
}


def tokenize(text: str) -> list[str]:
    """Return normalized, searchable terms from a text string."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [word for word in words if word not in STOP_WORDS and len(word) > 1]


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_database() -> None:
    """Create all tables and indexes required by the search service."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                crawled_at TEXT NOT NULL
            )
        """)
        # Keep the database compatible with earlier YEXA installations.
        existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(pages)")}
        for column, definition in (
            ("crawl_depth", "INTEGER"),
            ("http_status", "INTEGER"),
            ("content_hash", "TEXT"),
            ("first_crawled_at", "TEXT"),
            ("last_seen_at", "TEXT"),
            ("last_modified", "TEXT"),
            ("etag", "TEXT"),
            ("meta_description", "TEXT"),
            ("language", "TEXT"),
        ):
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE pages ADD COLUMN {column} {definition}")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverted_index (
                term TEXT NOT NULL,
                page_id INTEGER NOT NULL,
                frequency INTEGER NOT NULL,
                PRIMARY KEY (term, page_id),
                FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tfidf_index (
                term TEXT NOT NULL,
                page_id INTEGER NOT NULL,
                tfidf REAL NOT NULL,
                PRIMARY KEY (term, page_id),
                FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_stats (
                page_id INTEGER PRIMARY KEY,
                document_length INTEGER NOT NULL,
                authority REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                source_page_id INTEGER NOT NULL,
                target_url TEXT NOT NULL,
                anchor_text TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (source_page_id, target_url),
                FOREIGN KEY (source_page_id) REFERENCES pages(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inverted_page ON inverted_index(page_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tfidf_page ON tfidf_index(page_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url)")


def save_page(
    url: str,
    title: str,
    content: str,
    *,
    crawl_depth: int | None = None,
    http_status: int | None = None,
    metadata: dict | None = None,
) -> int:
    """Insert or replace a document. Call create_index afterwards to search it."""
    crawl_time = datetime.now(UTC).isoformat()
    metadata = metadata or {}
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO pages (url, title, content, crawled_at, crawl_depth, http_status, content_hash,
                first_crawled_at, last_seen_at, last_modified, etag, meta_description, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                crawled_at = excluded.crawled_at,
                crawl_depth = excluded.crawl_depth,
                http_status = excluded.http_status,
                content_hash = excluded.content_hash,
                first_crawled_at = COALESCE(pages.first_crawled_at, excluded.first_crawled_at),
                last_seen_at = excluded.last_seen_at,
                last_modified = excluded.last_modified,
                etag = excluded.etag,
                meta_description = excluded.meta_description,
                language = excluded.language
        """, (
            url,
            title.strip(),
            content.strip(),
            crawl_time,
            crawl_depth,
            http_status,
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
            crawl_time,
            crawl_time,
            metadata.get("last_modified"),
            metadata.get("etag"),
            metadata.get("meta_description"),
            metadata.get("language"),
        ))
        return connection.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()[0]


def replace_links(source_page_id: int, links: list[tuple[str, str]]) -> None:
    """Store outgoing links and anchor text for one crawled document."""
    with get_connection() as connection:
        connection.execute("DELETE FROM links WHERE source_page_id = ?", (source_page_id,))
        connection.executemany(
            "INSERT OR IGNORE INTO links (source_page_id, target_url, anchor_text) VALUES (?, ?, ?)",
            [(source_page_id, url, text[:500]) for url, text in links],
        )


def page_count() -> int:
    with get_connection() as connection:
        return connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0]


def index_stats() -> dict[str, int]:
    with get_connection() as connection:
        pages = connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        terms = connection.execute("SELECT COUNT(DISTINCT term) FROM inverted_index").fetchone()[0]
    return {"documents": pages, "terms": terms}


def calculate_source_quality(url: str) -> int:
    domain = urlparse(url).netloc.lower()
    score = 50
    if domain.endswith(".edu"):
        score += 25
    if domain.endswith(".gov"):
        score += 30
    if domain.endswith(".org"):
        score += 15
    if url.startswith("https://"):
        score += 5
    return min(score, 100)


def calculate_freshness(crawled_at: str) -> float:
    try:
        crawl_date = datetime.fromisoformat(crawled_at)
        if crawl_date.tzinfo is None:
            crawl_date = crawl_date.replace(tzinfo=UTC)
        age_days = max(0, (datetime.now(UTC) - crawl_date).total_seconds() / 86400)
        return round(min(100 * math.exp(-age_days / 30), 100), 2)
    except (TypeError, ValueError):
        return 0


def cosine_similarity(query_vector: dict[str, float], document_vector: dict[str, float]) -> float:
    dot_product = sum(
        query_vector.get(term, 0) * document_vector.get(term, 0)
        for term in query_vector.keys() | document_vector.keys()
    )
    query_magnitude = math.sqrt(sum(value * value for value in query_vector.values()))
    document_magnitude = math.sqrt(sum(value * value for value in document_vector.values()))
    if not query_magnitude or not document_magnitude:
        return 0
    return dot_product / (query_magnitude * document_magnitude)


def search_pages(query: str, limit: int = 10) -> list[dict]:
    """Rank pages with TF-IDF, title, phrase, source, and freshness signals."""
    query_words = tokenize(query)
    if not query_words:
        return []

    with get_connection() as connection:
        cursor = connection.cursor()
        total_documents = cursor.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        if total_documents == 0:
            return []

        query_vector: dict[str, float] = {}
        for term, frequency in Counter(query_words).items():
            document_frequency = cursor.execute(
                "SELECT COUNT(*) FROM inverted_index WHERE term = ?", (term,)
            ).fetchone()[0]
            if document_frequency:
                query_vector[term] = (1 + math.log(frequency)) * math.log(total_documents / document_frequency)

        if not query_vector:
            return []

        pages = cursor.execute("SELECT id, url, title, content, crawled_at FROM pages").fetchall()
        phrase = query.lower().strip()
        results = []
        for page in pages:
            document_vector = {
                row["term"]: row["tfidf"]
                for row in cursor.execute("SELECT term, tfidf FROM tfidf_index WHERE page_id = ?", (page["id"],))
            }
            similarity = cosine_similarity(query_vector, document_vector)
            title_lower, content_lower, url_lower = page["title"].lower(), page["content"].lower(), page["url"].lower()
            title_matches = sum(term in title_lower for term in query_words)
            content_matches = sum(term in content_lower for term in query_words)
            url_matches = sum(term in url_lower for term in query_words)
            title_relevance = title_matches * 10
            content_relevance = content_matches * 3
            url_relevance = url_matches * 5
            phrase_score = 15 if phrase in title_lower else 8 if phrase in content_lower else 0
            source_quality = calculate_source_quality(page["url"])
            freshness = calculate_freshness(page["crawled_at"])
            tfidf_score = similarity * 60
            source_score = source_quality * 0.10
            freshness_score = freshness * 0.10
            score = (tfidf_score + title_relevance + content_relevance + url_relevance
                     + phrase_score + source_score + freshness_score)
            if similarity or title_matches or content_matches or phrase_score:
                results.append({
                    "id": page["id"], "url": page["url"], "title": page["title"], "content": page["content"],
                    "score": round(score, 2), "similarity": round(similarity, 4),
                    "source_quality": source_quality, "freshness": freshness,
                    "match_summary": f"Matched {title_matches} title and {content_matches} content term(s).",
                    "ranking": {
                        "tfidf_similarity": round(tfidf_score, 2),
                        "title_relevance": title_relevance,
                        "content_relevance": content_relevance,
                        "url_relevance": url_relevance,
                        "exact_phrase": phrase_score,
                        "source_quality": round(source_score, 2),
                        "freshness": round(freshness_score, 2),
                    },
                })
    return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]
