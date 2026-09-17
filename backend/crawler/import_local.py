from pathlib import Path
from bs4 import BeautifulSoup

from database.database import create_database, save_page


def import_html_file(file_path):

    html = Path(file_path).read_text(
        encoding="utf-8"
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for element in soup(
        ["script", "style", "noscript"]
    ):
        element.decompose()

    title = (
        soup.title.string.strip()
        if soup.title and soup.title.string
        else "No Title"
    )

    text = soup.get_text(
        separator=" ",
        strip=True
    )

    save_page(
        f"local://{Path(file_path).name}",
        title,
        text
    )

    print(
        f"Saved: {title}"
    )


if __name__ == "__main__":


    create_database()

    files = [
        "test_pages/flutter.html",
        "test_pages/python.html",
        "test_pages/ai.html"
    ]

    for file in files:
        import_html_file(file)

    print("\nAll test pages imported successfully.")