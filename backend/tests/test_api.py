import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from database import database
from main import DocumentCreate, app, is_safe_crawl_url, lifespan


async def get_json(path: str, query_string: bytes = b"") -> tuple[int, dict]:
    """Exercise FastAPI routes as ASGI without an external test client dependency."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query_string,
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        },
        receive,
        send,
    )
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(body)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self.temporary_directory.name) / "api-test.db"

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_lifecycle_health_stats_and_search(self):
        async def exercise_api():
            async with lifespan(app):
                health_status, health_response = await get_json("/health")
                stats_status, stats_response = await get_json("/stats")
                search_status, search_response = await get_json("/search", b"query=python&limit=10")
                empty_status, _ = await get_json("/search")
                self.assertEqual(health_status, 200)
                self.assertEqual(health_response["status"], "ok")
                self.assertEqual(stats_status, 200)
                self.assertEqual(stats_response["documents"], 3)
                self.assertEqual(search_status, 200)
                self.assertEqual(search_response["total_results"], 1)
                self.assertEqual(search_response["results"][0]["title"], "Python Programming Language")
                self.assertIn("ranking", search_response["results"][0])
                self.assertEqual(empty_status, 422)

        asyncio.run(exercise_api())

    def test_crawl_url_safety(self):
        self.assertTrue(is_safe_crawl_url("https://example.org"))
        self.assertFalse(is_safe_crawl_url("http://localhost:8000"))
        self.assertFalse(is_safe_crawl_url("http://127.0.0.1:8000"))

    def test_document_request_validation(self):
        document = DocumentCreate(
            url="https://example.org/yexa",
            title="YEXA document",
            content="This document is long enough for the API validation and search index.",
        )
        self.assertEqual(str(document.url), "https://example.org/yexa")


if __name__ == "__main__":
    unittest.main()
