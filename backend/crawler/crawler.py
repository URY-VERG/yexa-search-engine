import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from collections import deque
from indexer.index import create_index
from database.database import create_database, save_page


USER_AGENT = "YEXA-Crawler/1.0"

MAX_PAGES = 20
MAX_DEPTH = 2
REQUEST_TIMEOUT = 10


def can_crawl(url):
    try:
        parsed = urlparse(url)

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        robot_parser = RobotFileParser()
        robot_parser.set_url(robots_url)
        robot_parser.read()

        return robot_parser.can_fetch(USER_AGENT, url)

    except Exception:
        return True


def crawl_page(url):

    try:

        headers = {
            "User-Agent": USER_AGENT
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            print(f"Skipped {url} - Status {response.status_code}")
            return None

        content_type = response.headers.get(
            "Content-Type",
            ""
        )

        if "text/html" not in content_type:
            print(f"Skipped non-HTML: {url}")
            return None

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for element in soup([
            "script",
            "style",
            "noscript",
            "header",
            "footer",
            "nav"
        ]):
            element.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url

        text = soup.get_text(
            separator=" ",
            strip=True
        )

        links = []

        for link in soup.find_all("a", href=True):

            absolute_url = urljoin(
                url,
                link["href"]
            )

            parsed = urlparse(absolute_url)

            if parsed.scheme in ["http", "https"]:

                clean_url = absolute_url.split("#")[0]

                if clean_url not in links:
                    links.append(clean_url)

        return {
            "url": url,
            "title": title,
            "content": text,
            "links": links
        }

    except requests.RequestException as error:

        print(f"Request error: {url}")
        print(error)

        return None

    except Exception as error:

        print(f"Error processing: {url}")
        print(error)

        return None


def crawl_website(start_url):

    parsed_start = urlparse(start_url)

    base_domain = parsed_start.netloc

    queue = deque()

    queue.append(
        (start_url, 0)
    )

    visited = set()

    pages_crawled = 0

    print("\n==============================")
    print("       YEXA WEB CRAWLER")
    print("==============================\n")

    while queue and pages_crawled < MAX_PAGES:

        current_url, depth = queue.popleft()

        if current_url in visited:
            continue

        if depth > MAX_DEPTH:
            continue

        visited.add(current_url)

        print(
            f"[{pages_crawled + 1}/{MAX_PAGES}] Crawling: {current_url}"
        )

        if not can_crawl(current_url):

            print("Blocked by robots.txt\n")

            continue

        page = crawl_page(current_url)

        if page is None:
            continue

        save_page(
            page["url"],
            page["title"],
            page["content"]
        )

        pages_crawled += 1

        print(
            f"Saved: {page['title']}"
        )

        print(
            f"Found links: {len(page['links'])}\n"
        )

        for link in page["links"]:

            parsed_link = urlparse(link)

            if parsed_link.netloc == base_domain:

                if link not in visited:

                    queue.append(
                        (link, depth + 1)
                    )

    print("==============================")
    print(
        f"YEXA crawled {pages_crawled} pages."
    )
    print("==============================\n")


if __name__ == "__main__":

    create_database()

    start_url = "https://example.com"

    crawl_website(start_url)

    print("Updating YEXA search index...")

    create_index()

    print("YEXA indexing completed.")