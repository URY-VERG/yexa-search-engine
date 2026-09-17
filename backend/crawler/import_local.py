from pathlib import Path
from bs4 import BeautifulSoup

from database.database import create_database, save_page
from indexer.index import create_index


def import_html_file(file_path: str | Path) -> str:

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

    return title


def import_html_files(file_paths: list[str | Path]) -> dict[str, int]:
    """Import local HTML files and rebuild the index once at the end."""
    create_database()
    imported = 0
    for file_path in file_paths:
        import_html_file(file_path)
        imported += 1
    index_result = create_index()
    return {"imported": imported, **index_result}


if __name__ == "__main__":


    base_directory = Path(__file__).resolve().parents[1]
    files = [
        base_directory / "test_pages/flutter.html",
        base_directory / "test_pages/python.html",
        base_directory / "test_pages/ai.html",
    ]
    print(import_html_files(files))
