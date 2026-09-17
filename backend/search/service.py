"""Local search service with real lexical retrieval and explainable ranking."""

import math
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from database.database import (
    calculate_freshness,
    calculate_source_quality,
    cosine_similarity,
    get_connection,
    tokenize,
)


def process_query(query: str) -> dict:
    normalized = " ".join(query.strip().split())
    phrases = [phrase.lower().strip() for phrase in re.findall(r'"([^"\n]+)"', normalized) if phrase.strip()]
    return {"normalized": normalized, "terms": tokenize(normalized), "phrases": phrases}


def make_snippet(content: str, terms: list[str], max_length: int = 280) -> str:
    """Select a readable text window around the first relevant term."""
    compact = " ".join(content.split())
    if len(compact) <= max_length:
        return compact
    lower = compact.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if positions:
        start = max(0, min(positions) - max_length // 3)
    else:
        start = 0
    end = min(len(compact), start + max_length)
    prefix = "…" if start else ""
    suffix = "…" if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"


def suggestions(prefix: str, limit: int = 6) -> list[str]:
    terms = tokenize(prefix)
    if not terms:
        return []
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT term, COUNT(*) AS frequency FROM inverted_index WHERE term LIKE ? "
            "GROUP BY term ORDER BY frequency DESC, term LIMIT ?",
            (f"{terms[-1]}%", limit),
        ).fetchall()
    return [row["term"] for row in rows]


def search(
    query: str,
    *,
    limit: int = 10,
    offset: int = 0,
    domain: str | None = None,
    freshness_days: int | None = None,
) -> dict:
    started = time.perf_counter()
    processed = process_query(query)
    terms = processed["terms"]
    if not terms:
        return {"query": processed["normalized"], "total_results": 0, "results": [], "took_ms": 0, "suggestions": []}

    with get_connection() as connection:
        cursor = connection.cursor()
        document_count = cursor.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        if not document_count:
            return {"query": processed["normalized"], "total_results": 0, "results": [], "took_ms": 0, "suggestions": suggestions(query)}

        placeholders = ",".join("?" for _ in set(terms))
        postings = cursor.execute(
            f"SELECT term, page_id, frequency FROM inverted_index WHERE term IN ({placeholders})", tuple(set(terms))
        ).fetchall()
        by_page: dict[int, dict[str, int]] = defaultdict(dict)
        document_frequency = Counter()
        for row in postings:
            by_page[row["page_id"]][row["term"]] = row["frequency"]
            document_frequency[row["term"]] += 1
        if not by_page:
            return {"query": processed["normalized"], "total_results": 0, "results": [], "took_ms": 0, "suggestions": suggestions(query)}

        average_length = cursor.execute("SELECT AVG(document_length) FROM document_stats").fetchone()[0] or 1
        pages = cursor.execute(
            f"SELECT p.*, COALESCE(s.document_length, 1) AS document_length, COALESCE(s.authority, 0) AS authority "
            f"FROM pages p LEFT JOIN document_stats s ON s.page_id = p.id WHERE p.id IN ({','.join('?' for _ in by_page)})",
            tuple(by_page),
        ).fetchall()
        results = []
        cutoff = datetime.now(UTC) - timedelta(days=freshness_days) if freshness_days else None
        for page in pages:
            parsed_domain = urlparse(page["url"]).netloc.lower()
            if domain and parsed_domain != domain.lower():
                continue
            if cutoff and datetime.fromisoformat(page["crawled_at"]).replace(tzinfo=UTC) < cutoff:
                continue
            bm25 = 0.0
            for term in set(terms):
                frequency = by_page[page["id"]].get(term, 0)
                if not frequency:
                    continue
                idf = math.log(1 + (document_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                bm25 += idf * (frequency * 2.0) / (frequency + 1.2 * (1 - 0.75 + 0.75 * page["document_length"] / average_length))

            title_lower, content_lower, url_lower = page["title"].lower(), page["content"].lower(), page["url"].lower()
            title_score = sum(term in title_lower for term in terms) * 10
            content_score = sum(term in content_lower for term in terms) * 2
            url_score = sum(term in url_lower for term in terms) * 4
            phrase_score = sum(12 if phrase in title_lower else 7 if phrase in content_lower else 0 for phrase in processed["phrases"])
            source_score = calculate_source_quality(page["url"]) * 0.08
            freshness_score = calculate_freshness(page["crawled_at"]) * 0.08
            authority_score = page["authority"] * 6
            duplicate_count = cursor.execute("SELECT COUNT(*) FROM pages WHERE content_hash = ?", (page["content_hash"],)).fetchone()[0]
            duplicate_penalty = -10 if duplicate_count > 1 else 0
            final_score = bm25 * 18 + title_score + content_score + url_score + phrase_score + source_score + freshness_score + authority_score + duplicate_penalty
            results.append({
                "id": page["id"], "title": page["title"], "url": page["url"],
                "description": make_snippet(page["content"], terms), "score": round(final_score, 2),
                "source_quality": calculate_source_quality(page["url"]), "freshness": calculate_freshness(page["crawled_at"]),
                "ranking": {"bm25": round(bm25 * 18, 2), "title_relevance": title_score, "content_relevance": content_score,
                            "url_relevance": url_score, "exact_phrase": phrase_score, "source_quality": round(source_score, 2),
                            "freshness": round(freshness_score, 2), "link_authority": round(authority_score, 2),
                            "duplicate_penalty": duplicate_penalty},
                "match_summary": f"Matched {sum(term in title_lower for term in terms)} title term(s) and {sum(term in content_lower for term in terms)} content term(s).",
            })
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"query": processed["normalized"], "total_results": len(results), "results": results[offset:offset + limit],
            "took_ms": round((time.perf_counter() - started) * 1000, 2), "suggestions": suggestions(query)}
