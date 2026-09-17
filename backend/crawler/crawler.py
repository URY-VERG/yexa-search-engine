"""A small, polite, same-domain crawler used to feed the YEXA index."""

from collections import deque
from dataclasses import asdict, dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from database.database import create_database, save_page
from indexer.index import create_index


USER_AGENT = "YEXA-Crawler/1.0 (+https://yexa.local)"
REQUEST_TIMEOUT = 10


@dataclass
class CrawlReport:
    start_url: str
    max_pages: int
    max_depth: int
    pages_crawled: int = 0
    pages_discovered: int = 0
    robots_blocked: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def canonicalize_url(url: str) -> str:
    """Drop fragments and normalize a URL enough for crawl de-duplication."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower()).geturl()


def is_html_response(response: requests.Response) -> bool:
    return "text/html" in response.headers.get("Content-Type", "").lower()


def extract_page(url: str, response: requests.Response) -> tuple[str, str, list[str]]:
    """Extract readable title/content and absolute HTTP(S) links from HTML."""
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "header", "footer", "nav", "svg"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else url
    text = soup.get_text(separator=" ", strip=True)
    links = []
    for anchor in soup.find_all("a", href=True):
        absolute_url = canonicalize_url(urljoin(url, anchor["href"]))
        if urlparse(absolute_url).scheme in {"http", "https"}:
            links.append(absolute_url)
    return title, text, list(dict.fromkeys(links))


class RobotsCache:
    """Fetch each domain's robots.txt once per crawl."""

    def __init__(self) -> None:
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allows(self, url: str) -> bool:
        parsed = urlparse(url)
        key = f"{parsed.scheme}://{parsed.netloc}"
        if key not in self._parsers:
            parser = RobotFileParser()
            parser.set_url(f"{key}/robots.txt")
            try:
                parser.read()
                self._parsers[key] = parser
            except OSError:
                # A missing robots file does not prohibit crawling.
                self._parsers[key] = None
        parser = self._parsers[key]
        return parser.can_fetch(USER_AGENT, url) if parser else True


def crawl_website(start_url: str, *, max_pages: int = 20, max_depth: int = 2) -> dict:
    """Crawl one domain within the supplied page/depth limits and rebuild the index."""
    start_url = canonicalize_url(start_url)
    start_domain = urlparse(start_url).netloc
    report = CrawlReport(start_url=start_url, max_pages=max_pages, max_depth=max_depth)
    queue = deque([(start_url, 0)])
    queued = {start_url}
    visited: set[str] = set()
    robots = RobotsCache()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    create_database()
    while queue and report.pages_crawled < max_pages:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        if not robots.allows(current_url):
            report.robots_blocked += 1
            continue

        try:
            response = session.get(current_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        except requests.RequestException as error:
            report.errors.append(f"{current_url}: {error}")
            continue

        final_url = canonicalize_url(response.url)
        if response.status_code != 200 or not is_html_response(response):
            report.skipped += 1
            continue
        if urlparse(final_url).netloc != start_domain:
            report.skipped += 1
            continue

        title, content, links = extract_page(final_url, response)
        if not content:
            report.skipped += 1
            continue

        save_page(final_url, title, content, crawl_depth=depth, http_status=response.status_code)
        report.pages_crawled += 1

        if depth >= max_depth:
            continue
        for link in links:
            if urlparse(link).netloc == start_domain and link not in queued and link not in visited:
                queued.add(link)
                queue.append((link, depth + 1))
                report.pages_discovered += 1

    if report.pages_crawled:
        create_index()
    return report.to_dict()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawl one website into the YEXA index.")
    parser.add_argument("url", help="Starting HTTP(S) URL")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args()
    print(crawl_website(args.url, max_pages=args.max_pages, max_depth=args.max_depth))
