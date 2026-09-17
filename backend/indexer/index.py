import math
from collections import Counter

from database.database import get_connection, tokenize


def calculate_authority(cursor, pages) -> dict[int, float]:
    """Calculate a small PageRank-style score over links between indexed pages."""
    if not pages:
        return {}
    page_ids_by_url = {page["url"]: page["id"] for page in pages}
    outgoing = {page["id"]: set() for page in pages}
    for row in cursor.execute("SELECT source_page_id, target_url FROM links"):
        target_id = page_ids_by_url.get(row["target_url"])
        if target_id and target_id != row["source_page_id"]:
            outgoing[row["source_page_id"]].add(target_id)

    count = len(pages)
    scores = {page["id"]: 1 / count for page in pages}
    for _ in range(20):
        next_scores = {page_id: (1 - 0.85) / count for page_id in scores}
        dangling = sum(scores[page_id] for page_id, targets in outgoing.items() if not targets)
        for page_id in next_scores:
            next_scores[page_id] += 0.85 * dangling / count
        for source_id, targets in outgoing.items():
            if targets:
                contribution = 0.85 * scores[source_id] / len(targets)
                for target_id in targets:
                    next_scores[target_id] += contribution
        scores = next_scores
    maximum = max(scores.values(), default=1)
    return {page_id: score / maximum for page_id, score in scores.items()}


def create_index() -> dict[str, int]:
    """Rebuild the inverted and TF-IDF indexes from every stored page."""
    with get_connection() as connection:
        cursor = connection.cursor()
        pages = cursor.execute("SELECT id, title, content FROM pages").fetchall()
        cursor.execute("DELETE FROM inverted_index")
        cursor.execute("DELETE FROM tfidf_index")
        cursor.execute("DELETE FROM document_stats")

        for page in pages:
            terms = Counter(tokenize(f"{page['title']} {page['title']} {page['content']}"))
            cursor.executemany(
                "INSERT INTO inverted_index (term, page_id, frequency) VALUES (?, ?, ?)",
                [(term, page["id"], frequency) for term, frequency in terms.items()],
            )
            cursor.execute(
                "INSERT INTO document_stats (page_id, document_length, authority) VALUES (?, ?, 0)",
                (page["id"], len(tokenize(f"{page['title']} {page['content']}"))),
            )

        total_documents = len(pages)
        if not total_documents:
            return {"documents": 0, "terms": 0}

        terms = cursor.execute("SELECT DISTINCT term FROM inverted_index").fetchall()
        for term_row in terms:
            term = term_row["term"]
            document_frequency = cursor.execute(
                "SELECT COUNT(*) FROM inverted_index WHERE term = ?", (term,)
            ).fetchone()[0]
            idf = math.log(total_documents / document_frequency)
            term_pages = cursor.execute(
                "SELECT page_id, frequency FROM inverted_index WHERE term = ?", (term,)
            ).fetchall()
            cursor.executemany(
                "INSERT INTO tfidf_index (term, page_id, tfidf) VALUES (?, ?, ?)",
                [(term, row["page_id"], (1 + math.log(row["frequency"])) * idf) for row in term_pages],
            )
        authority = calculate_authority(cursor, cursor.execute("SELECT id, url FROM pages").fetchall())
        cursor.executemany(
            "UPDATE document_stats SET authority = ? WHERE page_id = ?",
            [(score, page_id) for page_id, score in authority.items()],
        )
    return {"documents": total_documents, "terms": len(terms)}
