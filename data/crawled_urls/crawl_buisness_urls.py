from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
import json
import asyncio
import aiohttp
import re

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}

SKIP_PATTERNS = [
    "/my-account",
    "/wishlist",
    "/compare",
    "/login",
    "/cart",
    "/order",
    "/search",
    "/my-account",
    "/mon-compte",
    "/contact-us",
    "/nous-contacter",
    "/recuperation-mot-de-passe",
    "/blog",
    "/personal-data-protection",
    "/protection-des-donnees-personnelles"
]

# Skip variant product URLs like:
# /home/5238-2986-phone-name.html
VARIANT_PAGE_RE = re.compile(r"/home/\d+-\d+-.*\.html$", re.IGNORECASE)

# Keep canonical product URLs like:
# /home/5238-phone-name.html
CANONICAL_HOME_RE = re.compile(r"/home/\d+-.*\.html$", re.IGNORECASE)
VARIANT_PAGE_RE = re.compile(r"/[^/]+/\d+-\d+-.*\.html$", re.IGNORECASE)
#TOP_LEVEL_LISTING_RE = re.compile(r"^/[A-Za-z]+/[a-z]{2}/\d+-[^/]+$", re.IGNORECASE)

def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)  # remove #fragment
    parsed = urlparse(url)
    if parsed.path != "/" and url.endswith("/"):
        url = url.rstrip("/")

    return url


def should_skip_url(url: str, allowed_prefix: str) -> bool:
    parsed = urlparse(url)
    url_lower = url.lower()
    allowed_prefix_lower = allowed_prefix.lower().rstrip("/")

    if parsed.netloc != "www.ooredoo.tn":
        return True

    if not url_lower.startswith(allowed_prefix_lower):
        return True

    if parsed.query:
        return True

    if url_lower.endswith((
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".pdf", ".zip", ".xml", ".css", ".js",
        ".mp4", ".mp3", ".doc", ".docx", ".xls", ".xlsx"
    )):
        return True

    for pattern in SKIP_PATTERNS:
        if pattern in url_lower:
            return True

    # skip product variant pages
    if VARIANT_PAGE_RE.search(parsed.path):
        return True

    # skip top-level listing/catalog pages like /159-samsung or /40-phones
    # if TOP_LEVEL_LISTING_RE.match(parsed.path):
        return True

    return False


async def fetch_html(session, url: str, semaphore: asyncio.Semaphore):
    try:
        async with semaphore:
            async with session.get(
                url,
                headers=HEADERS,
                timeout=15,
                ssl=False
            ) as response:
                if response.status != 200:
                    return None
                return await response.text()
    except Exception:
        print(f"✗ Error: {url}")
        return None


async def crawl_urls(start_url: str, allowed_prefix: str, session, semaphore):
    start_url = normalize_url(start_url)

    queue = deque([start_url])
    visited = set()
    discovered = {start_url}
    crawled_urls = []

    while queue:
        url = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        html = await fetch_html(session, url, semaphore)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        crawled_urls.append(url)
        print(f"✓ Crawled: {url}")

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if not href:
                continue

            # skip raw non-navigable links
            if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue

            new_url = urljoin(url, href)
            new_url = normalize_url(new_url)

            if should_skip_url(new_url, allowed_prefix):
                continue

            if new_url not in visited and new_url not in discovered:
                queue.append(new_url)
                discovered.add(new_url)

        await asyncio.sleep(0.05)

    return crawled_urls


def save_urls(urls, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted(urls), f, ensure_ascii=False, indent=4)
    print(f"URLs saved to {file_path}")


async def main():
    connector = aiohttp.TCPConnector(limit=30, limit_per_host=15)
    semaphore = asyncio.Semaphore(15)

    start_url_bs_en = "https://www.ooredoo.tn/Business/en/"
    start_url_bs_fr = "https://www.ooredoo.tn/Business/fr/"
    start_url_ps_en = "https://www.ooredoo.tn/Personal/en/"
    start_url_ps_fr = "https://www.ooredoo.tn/Personal/fr/"

    async with aiohttp.ClientSession(connector=connector) as session:
        task_bs_en = asyncio.create_task(
            crawl_urls(start_url_bs_en, start_url_bs_en, session, semaphore)
        )
        task_bs_fr = asyncio.create_task(
            crawl_urls(start_url_bs_fr, start_url_bs_fr, session, semaphore)
        )
        task_ps_en = asyncio.create_task(
            crawl_urls(start_url_ps_en, start_url_ps_en, session, semaphore)
        )
        task_ps_fr = asyncio.create_task(
            crawl_urls(start_url_ps_fr, start_url_ps_fr, session, semaphore)
        )


        urls_bs_en = await task_bs_en
        urls_bs_fr = await task_bs_fr
        urls_ps_en = await task_ps_en
        urls_ps_fr = await task_ps_fr


        save_urls(urls_bs_en, "crawled_urls_business_en.json")
        save_urls(urls_bs_fr, "crawled_urls_business_fr.json")
        save_urls(urls_ps_en, "crawled_urls_personal_en.json")
        save_urls(urls_ps_fr, "crawled_urls_personal_fr.json")


if __name__ == "__main__":
    asyncio.run(main())