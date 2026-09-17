import math
from collections import Counter

from database.database import get_connection, tokenize


def create_index() -> dict[str, int]:
    """Rebuild the inverted and TF-IDF indexes from every stored page."""
    with get_connection() as connection:
        cursor = connection.cursor()
        pages = cursor.execute("SELECT id, title, content FROM pages").fetchall()
        cursor.execute("DELETE FROM inverted_index")
        cursor.execute("DELETE FROM tfidf_index")

        for page in pages:
            terms = Counter(tokenize(f"{page['title']} {page['title']} {page['content']}"))
            cursor.executemany(
                "INSERT INTO inverted_index (term, page_id, frequency) VALUES (?, ?, ?)",
                [(term, page["id"], frequency) for term, frequency in terms.items()],
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
    return {"documents": total_documents, "terms": len(terms)}
