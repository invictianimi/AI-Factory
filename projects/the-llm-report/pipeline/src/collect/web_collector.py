"""
The LLM Report — Web Scraper Collector
Scrapes web pages for content when RSS is not available.
Extracts title, date, and main body text.
"""

from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pipeline.src.models import CollectedItem
from pipeline.src.collect.tagger import tag_item

TIMEOUT = int(os.environ.get("COLLECTION_TIMEOUT", "30"))
USER_AGENT = "TheLLMReport/1.0 (+https://thellmreport.com/about)"
MAX_CONTENT_LENGTH = 5000  # chars — truncate very long pages


def _extract_date(soup: BeautifulSoup) -> Optional[datetime]:
    """Try to extract publication date from common meta tags."""
    for meta_name in [
        "article:published_time", "og:article:published_time",
        "datePublished", "DC.date", "pubdate",
    ]:
        tag = soup.find("meta", property=meta_name) or soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            try:
                from dateutil.parser import parse as parse_date
                return parse_date(tag["content"]).astimezone(timezone.utc).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    # Try time[datetime] tags
    time_tag = soup.find("time", datetime=True)
    if time_tag:
        try:
            from dateutil.parser import parse as parse_date
            return parse_date(time_tag["datetime"]).astimezone(timezone.utc).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _extract_main_content(soup: BeautifulSoup) -> str:
    """Extract main article text from a page."""
    # Remove boilerplate
    for tag in soup.find_all(["nav", "footer", "aside", "script", "style", "header"]):
        tag.decompose()

    # Try common article containers
    for selector in ["article", "main", '[role="main"]', ".post-content", ".entry-content", ".article-body"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator=" ")
            return re.sub(r'\s+', ' ', text).strip()[:MAX_CONTENT_LENGTH]

    # Fallback: all paragraph text
    paras = soup.find_all("p")
    text = " ".join(p.get_text() for p in paras)
    return re.sub(r'\s+', ' ', text).strip()[:MAX_CONTENT_LENGTH]


def fetch_page(source_name: str, url: str, tier: int) -> list[CollectedItem]:
    """
    Scrape a web page and return CollectedItems.
    For changelog/listing pages, may return multiple items.
    For article pages, returns one item.
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch {url}: {e}") from e

    if resp.status_code != 200:
        raise ConnectionError(f"HTTP {resp.status_code} from {url}")

    soup = BeautifulSoup(resp.content, "html.parser")

    # Extract title
    title_tag = soup.find("title") or soup.find("h1")
    title = title_tag.get_text().strip() if title_tag else source_name

    # Clean title
    title = re.sub(r'\s+', ' ', title)[:200]

    content = _extract_main_content(soup)
    if not content:
        content = title

    published_at = _extract_date(soup)
    tags, _ = tag_item(title, content)

    item = CollectedItem(
        source_name=source_name,
        source_tier=tier,
        url=url,
        title=title,
        raw_content=content,
        published_at=published_at,
        tags=tags,
    )
    return [item]


def fetch_changelog_entries(source_name: str, url: str, tier: int) -> list[CollectedItem]:
    """
    Scrape a changelog page and extract individual entries as separate items.
    Each dated section becomes one CollectedItem.
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch {url}: {e}") from e

    if resp.status_code != 200:
        raise ConnectionError(f"HTTP {resp.status_code} from {url}")

    soup = BeautifulSoup(resp.content, "html.parser")
    items = []

    # Try to find dated sections (h2/h3 with dates, common in changelogs)
    date_pattern = re.compile(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}\b'
        r'|\b\d{4}-\d{2}-\d{2}\b',
        re.IGNORECASE
    )
    sections = soup.find_all(["h2", "h3"])
    found_sections = False

    for header in sections[:10]:  # Limit to 10 most recent
        header_text = header.get_text().strip()
        if not date_pattern.search(header_text) and not any(
            c.isdigit() for c in header_text
        ):
            continue

        # Extract content until next header
        content_parts = []
        for sibling in header.next_siblings:
            if sibling.name in ["h2", "h3"]:
                break
            if hasattr(sibling, "get_text"):
                text = sibling.get_text(separator=" ").strip()
                if text:
                    content_parts.append(text)
        content = " ".join(content_parts)[:MAX_CONTENT_LENGTH]
        if not content:
            continue

        found_sections = True
        tags, _ = tag_item(header_text, content)
        item = CollectedItem(
            source_name=source_name,
            source_tier=tier,
            url=url,
            title=f"{source_name}: {header_text}",
            raw_content=content,
            published_at=None,
            tags=tags,
        )
        items.append(item)

    if not found_sections:
        # Fallback: treat whole page as one item
        return fetch_page(source_name, url, tier)

    return items
