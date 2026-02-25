"""
The LLM Report — RSS Feed Collector
Fetches and parses RSS/Atom feeds.
Uses ETag/Last-Modified for conditional fetching to avoid re-fetching unchanged data.
"""

from __future__ import annotations
import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from pipeline.src.models import CollectedItem
from pipeline.src.collect.tagger import tag_item

TIMEOUT = int(os.environ.get("COLLECTION_TIMEOUT", "30"))
USER_AGENT = "TheLLMReport/1.0 (+https://thellmreport.com/about)"

# In-memory ETag/Last-Modified cache (persisted via SQLite in a full implementation)
_etag_cache: dict[str, str] = {}
_lastmod_cache: dict[str, str] = {}


def _clean_html(html: str) -> str:
    """Strip HTML tags and clean whitespace."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r'\s+', ' ', text).strip()


def _parse_date(entry) -> Optional[datetime]:
    """Parse date from feedparser entry."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, field, None)
        if t:
            import time
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except Exception:
                pass
    return None


def fetch_rss(source_name: str, url: str, tier: int) -> list[CollectedItem]:
    """
    Fetch and parse an RSS/Atom feed.
    Uses conditional GET (ETag/Last-Modified) to skip unchanged feeds.
    Returns list of CollectedItems (only new content, not dedup-checked here).
    """
    headers = {"User-Agent": USER_AGENT}
    etag = _etag_cache.get(url)
    lastmod = _lastmod_cache.get(url)
    if etag:
        headers["If-None-Match"] = etag
    if lastmod:
        headers["If-Modified-Since"] = lastmod

    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch {url}: {e}") from e

    if resp.status_code == 304:
        return []  # Not modified — skip
    if resp.status_code != 200:
        raise ConnectionError(f"HTTP {resp.status_code} from {url}")

    # Cache conditional headers for next time
    if "ETag" in resp.headers:
        _etag_cache[url] = resp.headers["ETag"]
    if "Last-Modified" in resp.headers:
        _lastmod_cache[url] = resp.headers["Last-Modified"]

    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue

        # Extract content
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = _clean_html(entry.content[0].get("value", ""))
        elif hasattr(entry, "summary"):
            content = _clean_html(entry.summary)
        elif hasattr(entry, "description"):
            content = _clean_html(entry.description)

        if not content:
            content = title  # Fallback: use title as content

        tags, _ = tag_item(title, content)
        published_at = _parse_date(entry)

        item = CollectedItem(
            source_name=source_name,
            source_tier=tier,
            url=link,
            title=title,
            raw_content=content,
            published_at=published_at,
            tags=tags,
        )
        items.append(item)

    return items
