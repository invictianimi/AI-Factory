"""
The LLM Report — GitHub API Collector
Fetches recent releases and discussions from GitHub repos.
Uses conditional requests (ETag) to avoid re-fetching unchanged data.
"""

from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from pipeline.src.models import CollectedItem
from pipeline.src.collect.tagger import tag_item

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TIMEOUT = int(os.environ.get("COLLECTION_TIMEOUT", "30"))
USER_AGENT = "TheLLMReport/1.0 (+https://thellmreport.com/about)"
MAX_RELEASES = 5  # Per repo per run
MAX_AGE_DAYS = 7  # Ignore releases older than this

_etag_cache: dict[str, str] = {}


def _headers() -> dict:
    h = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


def _org_from_url(url: str) -> str:
    """Extract org/user from GitHub URL."""
    # e.g., https://github.com/deepseek-ai → deepseek-ai
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _repo_from_url(url: str) -> Optional[str]:
    """Extract repo from GitHub URL if it's a specific repo, not org."""
    parts = url.rstrip("/").split("/")
    # org-level URL has 4 parts: https: '' github.com org
    # repo-level has 5: https: '' github.com org repo
    if len(parts) == 5:
        return f"{parts[-2]}/{parts[-1]}"
    return None


def fetch_github(source_name: str, url: str, tier: int) -> list[CollectedItem]:
    """
    Fetch recent releases from a GitHub org or repo.
    Returns CollectedItems for each new release.
    """
    repo = _repo_from_url(url)
    if repo:
        return _fetch_repo_releases(source_name, repo, url, tier)
    else:
        org = _org_from_url(url)
        return _fetch_org_releases(source_name, org, url, tier)


def _fetch_repo_releases(source_name: str, repo: str, source_url: str, tier: int) -> list[CollectedItem]:
    """Fetch releases for a specific repo."""
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page={MAX_RELEASES}"
    headers = _headers()
    etag = _etag_cache.get(api_url)
    if etag:
        headers["If-None-Match"] = etag

    try:
        resp = requests.get(api_url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ConnectionError(f"GitHub API failed for {repo}: {e}") from e

    if resp.status_code == 304:
        return []
    if resp.status_code == 404:
        # Repo might not have releases — try tags or commits
        return []
    if resp.status_code != 200:
        raise ConnectionError(f"GitHub API HTTP {resp.status_code} for {repo}")

    if "ETag" in resp.headers:
        _etag_cache[api_url] = resp.headers["ETag"]

    releases = resp.json()
    items = []
    for release in releases:
        tag_name = release.get("tag_name", "")
        name = release.get("name", tag_name)
        body = release.get("body", "") or ""
        html_url = release.get("html_url", source_url)
        published_at_str = release.get("published_at") or release.get("created_at")

        title = f"{source_name}: {name or tag_name}"
        content = f"Release: {tag_name}\n\n{body}"[:3000]

        tags, _ = tag_item(title, content)
        if "model-release" not in tags and "framework-release" not in tags:
            tags.append("release")
        tags.append(repo.split("/")[-1])  # Add repo name as tag

        published_at = None
        if published_at_str:
            try:
                published_at = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except Exception:
                pass

        # Skip releases older than MAX_AGE_DAYS
        if published_at and published_at < datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS):
            continue

        item = CollectedItem(
            source_name=source_name,
            source_tier=tier,
            url=html_url,
            title=title,
            raw_content=content,
            published_at=published_at,
            tags=tags,
        )
        items.append(item)

    return items


def _fetch_org_releases(source_name: str, org: str, source_url: str, tier: int) -> list[CollectedItem]:
    """Fetch releases from all repos in a GitHub org."""
    # First get org's repos, sorted by recent push
    api_url = f"https://api.github.com/orgs/{org}/repos?sort=pushed&direction=desc&per_page=10"
    headers = _headers()

    try:
        resp = requests.get(api_url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ConnectionError(f"GitHub API failed for org {org}: {e}") from e

    if resp.status_code == 404:
        # Might be a user, not org
        api_url = api_url.replace("/orgs/", "/users/")
        try:
            resp = requests.get(api_url, headers=headers, timeout=TIMEOUT)
        except requests.RequestException:
            return []

    if resp.status_code != 200:
        return []

    repos = resp.json()
    items = []
    for repo_data in repos[:5]:  # Check top 5 most recently active repos
        repo_full_name = repo_data.get("full_name", "")
        if not repo_full_name:
            continue
        repo_items = _fetch_repo_releases(source_name, repo_full_name, source_url, tier)
        items.extend(repo_items)
        if len(items) >= MAX_RELEASES:
            break

    return items[:MAX_RELEASES]
