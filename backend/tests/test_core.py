import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from crawler.crawler import canonicalize_url, crawl_website, extract_page
from crawler.import_local import import_html_files
from database import database
from database.database import create_database, index_stats, save_page, search_pages
from indexer.index import create_index


class SearchEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self.temporary_directory.name) / "yexa-test.db"
        create_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_indexed_documents_return_explainable_result(self):
        save_page("https://example.org/python", "Python for data work", "Python makes data processing clear and practical.")
        save_page("https://example.org/flutter", "Flutter apps", "Flutter uses Dart to build mobile applications.")
        create_index()

        results = search_pages("python data")

        self.assertEqual(results[0]["title"], "Python for data work")
        self.assertGreater(results[0]["score"], 0)
        self.assertIn("ranking", results[0])
        self.assertGreater(results[0]["ranking"]["title_relevance"], 0)
        self.assertEqual(index_stats()["documents"], 2)

    def test_local_html_import_rebuilds_index(self):
        html_path = Path(self.temporary_directory.name) / "search.html"
        html_path.write_text("<html><title>YEXA local search</title><body>Local document indexing</body></html>")

        report = import_html_files([html_path])

        self.assertEqual(report["imported"], 1)
        self.assertEqual(search_pages("local")[0]["title"], "YEXA local search")

    def test_controlled_same_domain_crawl(self):
        pages = {
            "https://example.org/": SimpleNamespace(
                url="https://example.org/",
                status_code=200,
                headers={"Content-Type": "text/html"},
                text="<title>Home</title><body>YEXA home <a href='/guide'>Guide</a><a href='https://other.org'>Other</a></body>",
            ),
            "https://example.org/guide": SimpleNamespace(
                url="https://example.org/guide",
                status_code=200,
                headers={"Content-Type": "text/html"},
                text="<title>Guide</title><body>Search engine guide</body>",
            ),
        }

        with patch("crawler.crawler.RobotsCache.allows", return_value=True), patch(
            "crawler.crawler.requests.Session.get", side_effect=lambda url, **_: pages[url]
        ):
            report = crawl_website("https://example.org/", max_pages=5, max_depth=1)

        self.assertEqual(report["pages_crawled"], 2)
        self.assertEqual(report["pages_discovered"], 1)
        self.assertEqual(search_pages("guide")[0]["title"], "Guide")
        self.assertEqual(canonicalize_url("HTTPS://EXAMPLE.ORG/page#section"), "https://example.org/page")

        title, content, links = extract_page("https://example.org/", pages["https://example.org/"])
        self.assertEqual(title, "Home")
        self.assertIn("YEXA home", content)
        self.assertIn("https://example.org/guide", links)


if __name__ == "__main__":
    unittest.main()
