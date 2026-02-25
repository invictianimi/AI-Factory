"""
The LLM Report — Semantic Cache
Caches LLM query-response pairs. Checks similarity before making new LLM calls.
Threshold: 0.92 cosine similarity
TTL: 7 days for factual queries, 1 day for news-dependent queries
"""

from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

CACHE_DB_PATH = Path(
    os.environ.get(
        "CACHE_DB_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data/kb.sqlite"),
    )
)
SIMILARITY_THRESHOLD = 0.92
TTL_FACTUAL_DAYS = 7
TTL_NEWS_DAYS = 1

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS semantic_cache (
    id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding TEXT NOT NULL,
    response TEXT NOT NULL,
    cache_type TEXT NOT NULL DEFAULT 'factual',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON semantic_cache(expires_at);
"""


@contextmanager
def _conn():
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        for stmt in CACHE_SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(s)
        conn.commit()
        yield conn
    finally:
        conn.close()


def _embed(text: str) -> list[float]:
    """Get embedding for a text using the local embedding model."""
    from pipeline.src.kb.vector_store import _get_embed_fn
    fn = _get_embed_fn()
    result = fn([text])[0]
    # Convert numpy array to plain list for JSON serialization
    if hasattr(result, "tolist"):
        return result.tolist()
    return list(result)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def check_cache(query: str, cache_type: str = "factual") -> Optional[str]:
    """
    Check if a semantically similar query has been answered recently.
    Returns cached response string if hit (>= 0.92 similarity, within TTL), else None.
    Cost: $0 on hit.
    """
    query_embedding = _embed(query)
    now_iso = datetime.now(timezone.utc).isoformat()

    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, query_text, query_embedding, response, hit_count
            FROM semantic_cache
            WHERE expires_at > ? AND cache_type = ?
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (now_iso, cache_type),
        ).fetchall()

        for row in rows:
            cached_embedding = json.loads(row["query_embedding"])
            sim = _cosine_similarity(query_embedding, cached_embedding)
            if sim >= SIMILARITY_THRESHOLD:
                # Update hit count
                conn.execute(
                    "UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE id = ?",
                    (row["id"],),
                )
                conn.commit()
                return row["response"]
    return None


def store_cache(query: str, response: str, cache_type: str = "factual") -> None:
    """Store an LLM response in the semantic cache."""
    ttl_days = TTL_FACTUAL_DAYS if cache_type == "factual" else TTL_NEWS_DAYS
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)
    cache_id = hashlib.sha256(query.encode()).hexdigest()[:16]
    embedding = _embed(query)

    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO semantic_cache
                (id, query_text, query_embedding, response, cache_type, created_at, expires_at, hit_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                cache_id,
                query,
                json.dumps(embedding),
                response,
                cache_type,
                now.isoformat(),
                expires.isoformat(),
            ),
        )
        conn.commit()


def purge_expired() -> int:
    """Remove expired cache entries. Returns count deleted."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute("DELETE FROM semantic_cache WHERE expires_at <= ?", (now_iso,))
        deleted = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        return deleted


def get_cache_stats() -> dict:
    """Return cache statistics for health monitoring."""
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM semantic_cache").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM semantic_cache WHERE expires_at > datetime('now')"
        ).fetchone()[0]
        hits = conn.execute("SELECT COALESCE(SUM(hit_count), 0) FROM semantic_cache").fetchone()[0]
        return {"total_entries": total, "active_entries": active, "total_hits": hits}
