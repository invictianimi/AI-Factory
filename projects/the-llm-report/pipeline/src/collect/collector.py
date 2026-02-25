"""
The LLM Report — Main Collection Orchestrator
Runs all sources for a given day type (standard/deep-dive/friday).
Handles errors, deduplication at ingest, and KB storage.
NLSpec Section 5.1
"""

from __future__ import annotations
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from pipeline.src.models import CollectedItem, RunState
from pipeline.src.kb import store, vector_store
from pipeline.src.collect import rss_collector, web_collector, github_collector
from pipeline.src.collect.tagger import tag_item
from orchestrator.as_built import log as aslog

SOURCES_CONFIG = Path(
    os.environ.get(
        "SOURCES_CONFIG",
        str(Path(__file__).parent.parent.parent.parent / "config/sources.yaml"),
    )
)
MAX_RETRIES = int(os.environ.get("COLLECTION_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("COLLECTION_RETRY_DELAY", "5"))


@dataclass
class CollectionResult:
    run_id: str
    items_new: list[CollectedItem] = field(default_factory=list)
    items_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    sources_attempted: int = 0
    sources_succeeded: int = 0


def _load_sources(run_type: str = "standard") -> list[dict]:
    """Load source config, filtering to appropriate tiers for this run type."""
    with open(SOURCES_CONFIG) as f:
        config = yaml.safe_load(f)

    sources = []
    # All runs: Tier 1 + Tier 2
    sources.extend(config.get("tier1", []))
    sources.extend(config.get("tier2", []))

    # Tier 3 only on deep-dive (Saturday) or friday
    if run_type in ("deep-dive", "friday"):
        sources.extend(config.get("tier3", []))

    return [s for s in sources if s.get("enabled", True)]


def _fetch_source(source: dict) -> list[CollectedItem]:
    """Fetch items from a single source based on its type."""
    name = source["name"]
    url = source["url"]
    tier = source["tier"]
    source_type = source.get("type", "web")

    if source_type == "rss":
        return rss_collector.fetch_rss(name, url, tier)
    elif source_type == "github":
        return github_collector.fetch_github(name, url, tier)
    elif source_type == "api":
        # For now, treat API sources like web scraping
        return web_collector.fetch_page(name, url, tier)
    elif source_type == "web":
        # Check if it looks like a changelog URL
        if any(kw in url.lower() for kw in ["changelog", "models", "release"]):
            return web_collector.fetch_changelog_entries(name, url, tier)
        return web_collector.fetch_page(name, url, tier)
    else:
        raise ValueError(f"Unknown source type: {source_type}")


def run_collection(run_state: RunState, run_type: str = "standard") -> CollectionResult:
    """
    Main collection entry point.
    Fetches all sources, deduplicates at ingest, stores to KB.

    Args:
        run_state: Current run state (for logging)
        run_type: "standard" | "deep-dive" | "friday"

    Returns:
        CollectionResult with new items and error summary.
    """
    result = CollectionResult(run_id=run_state.run_id)
    sources = _load_sources(run_type)
    aslog(
        f"Collection started: {len(sources)} sources ({run_type})",
        run_id=run_state.run_id,
    )

    for source in sources:
        result.sources_attempted += 1
        name = source["name"]
        items = []
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                items = _fetch_source(source)
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)

        if last_error:
            error_msg = f"{name}: {type(last_error).__name__}: {last_error}"
            result.errors.append(error_msg)
            aslog(f"Collection error (after {MAX_RETRIES} attempts)", detail=error_msg, level="WARNING", run_id=run_state.run_id)
            continue

        result.sources_succeeded += 1

        # Ingest each item: dedup check → store
        for item in items:
            if store.item_exists(item.content_hash):
                result.items_skipped += 1
                continue

            # Store in structured DB
            inserted = store.store_item(item)
            if inserted:
                # Embed in vector store
                try:
                    vector_store.embed_item(
                        item_id=item.id,
                        title=item.title,
                        content=item.raw_content,
                        metadata={
                            "source_name": item.source_name,
                            "source_tier": item.source_tier,
                            "url": item.url,
                            "tags": ",".join(item.tags),
                        },
                    )
                except Exception as e:
                    aslog(f"Embedding failed for {item.id}", detail=str(e), level="WARNING")

                result.items_new.append(item)
            else:
                result.items_skipped += 1

    run_state.items_collected = len(result.items_new)
    aslog(
        f"Collection complete: {len(result.items_new)} new, {result.items_skipped} skipped, "
        f"{len(result.errors)} errors",
        run_id=run_state.run_id,
    )
    return result
