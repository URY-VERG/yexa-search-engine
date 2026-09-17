import sqlite3
import re
from collections import Counter

DATABASE_NAME = "yexa.db"


# Common English words that do not help search relevance
STOP_WORDS = {
    "the",
    "is",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "this",
    "that",
    "it",
    "as",
    "are",
    "was",
    "were",
    "be",
    "by",
    "from",
    "at",
    "about",
    "into",
    "your",
    "you"
}


def tokenize(text):
    """
    Convert text into searchable words.
    """

    words = re.findall(
        r"[a-zA-Z0-9]+",
        text.lower()
    )

    filtered_words = [
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 1
    ]

    return filtered_words


def create_index():

    connection = sqlite3.connect(
        DATABASE_NAME
    )

    cursor = connection.cursor()

    # Create inverted index table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inverted_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT,
            page_id INTEGER,
            frequency INTEGER,
            UNIQUE(term, page_id)
        )
    """)

    # Get crawled pages
    cursor.execute("""
        SELECT id, title, content
        FROM pages
    """)

    pages = cursor.fetchall()

    for page_id, title, content in pages:

        # Give title extra importance
        combined_text = (
            title + " " + title + " " + content
        )

        words = tokenize(
            combined_text
        )

        word_frequency = Counter(
            words
        )

        for term, frequency in word_frequency.items():

            cursor.execute("""
                INSERT OR REPLACE INTO inverted_index
                (term, page_id, frequency)
                VALUES (?, ?, ?)
            """, (
                term,
                page_id,
                frequency
            ))

    connection.commit()
    connection.close()

    print(
        f"Indexed {len(pages)} pages successfully."
    )


if __name__ == "__main__":

    create_index()