"""
The LLM Report — Deduplication Stage
Clusters triaged items that cover the same story using vector similarity.
Local-only: zero LLM cost. Uses ChromaDB embeddings.
Threshold: >= 0.85 cosine similarity → same cluster.
NLSpec Section 5.3
"""

from __future__ import annotations
from pipeline.src.models import TriagedItem, StoryGroup
from pipeline.src.kb.vector_store import compute_similarity

DEDUP_THRESHOLD = 0.85  # Items with similarity >= this are clustered together


def deduplicate(items: list[TriagedItem]) -> list[StoryGroup]:
    """
    Cluster triaged items by semantic similarity.
    Items with pairwise cosine similarity >= 0.85 are grouped.
    Within each group, the highest-significance item is designated primary.

    Cost: $0 (local vector computation only)

    Args:
        items: Triaged items to cluster (should be significance >= 4)

    Returns:
        List of StoryGroups, each with a primary item and supporting items.
    """
    if not items:
        return []

    # Union-Find for efficient clustering
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Compare all pairs — O(n²) but n is small (< 50 items per run)
    texts = [f"{item.item.title} {item.item.raw_content[:300]}" for item in items]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            sim = compute_similarity(texts[i], texts[j])
            if sim >= DEDUP_THRESHOLD:
                union(i, j)

    # Collect clusters
    clusters: dict[int, list[int]] = {}
    for i in range(len(items)):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    # Build StoryGroups
    groups = []
    for cluster_indices in clusters.values():
        cluster_items = [items[i] for i in cluster_indices]

        # Sort by significance descending — highest significance is primary
        cluster_items.sort(key=lambda x: x.significance, reverse=True)
        primary = cluster_items[0]
        supporting = cluster_items[1:]

        group = StoryGroup(primary=primary, supporting=supporting)
        groups.append(group)

    # Sort groups by max_significance descending
    groups.sort(key=lambda g: g.max_significance, reverse=True)
    return groups


def get_dedup_stats(groups: list[StoryGroup]) -> dict:
    """Return deduplication statistics for logging."""
    total_items = sum(1 + len(g.supporting) for g in groups)
    clustered = sum(len(g.supporting) for g in groups)
    return {
        "total_groups": len(groups),
        "total_items": total_items,
        "items_merged": clustered,
        "dedup_rate": clustered / total_items if total_items > 0 else 0,
    }
