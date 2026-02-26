"""
The LLM Report — SQLite Structured Store
Manages: models, organizations, published_articles, source_items, run_log, cost_log
"""

from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pipeline.src.models import CollectedItem, RunState

DB_PATH = Path(
    os.environ.get(
        "KB_DB_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data/kb.sqlite"),
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_items (
    id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_tier INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    published_at TEXT,
    collected_at TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    significance_score REAL,
    promoted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_source_items_hash ON source_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_source_items_source ON source_items(source_name);
CREATE INDEX IF NOT EXISTS idx_source_items_collected ON source_items(collected_at);

CREATE TABLE IF NOT EXISTS published_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    published_date TEXT NOT NULL,
    topics TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT NOT NULL,
    url TEXT,
    edition_id TEXT,
    word_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_published_hash ON published_articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_published_date ON published_articles(published_date);

CREATE TABLE IF NOT EXISTS models (
    name TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    release_date TEXT,
    parameter_count TEXT,
    context_window INTEGER,
    key_benchmarks TEXT DEFAULT '{}',
    pricing TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organizations (
    name TEXT PRIMARY KEY,
    type TEXT,
    key_people TEXT DEFAULT '[]',
    recent_events TEXT DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_log (
    run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL DEFAULT 'standard',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_cost_usd REAL DEFAULT 0.0,
    items_collected INTEGER DEFAULT 0,
    items_published INTEGER DEFAULT 0,
    errors TEXT DEFAULT '[]',
    status TEXT DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    model_used TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    task_description TEXT,
    timestamp TEXT NOT NULL,
    cached INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cost_run ON cost_log(run_id);
CREATE INDEX IF NOT EXISTS idx_cost_time ON cost_log(timestamp);
"""


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        for statement in SCHEMA.strip().split(";"):
            s = statement.strip()
            if s:
                conn.execute(s)
        conn.commit()
        yield conn
    finally:
        conn.close()


def item_exists(content_hash: str) -> bool:
    """Check if an item with this content_hash already exists."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM source_items WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is not None


def store_item(item: CollectedItem) -> bool:
    """
    Store a CollectedItem. Returns True if inserted, False if already existed.
    """
    with _conn() as conn:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO source_items
                    (id, source_name, source_tier, url, title, raw_content,
                     content_hash, published_at, collected_at, tags,
                     significance_score, promoted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.source_name,
                    item.source_tier,
                    item.url,
                    item.title,
                    item.raw_content,
                    item.content_hash,
                    item.published_at.isoformat() if item.published_at else None,
                    item.collected_at.isoformat(),
                    json.dumps(item.tags),
                    item.significance_score,
                    int(item.promoted),
                ),
            )
            inserted = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
            return inserted > 0
        except Exception:
            conn.rollback()
            raise


def update_item_significance(item_id: str, score: float, promoted: bool) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE source_items SET significance_score = ?, promoted = ? WHERE id = ?",
            (score, int(promoted), item_id),
        )
        conn.commit()


def get_recent_items(limit: int = 100, days: int = 7) -> list[dict]:
    """Get recently collected items for KB context."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM source_items
            WHERE collected_at >= datetime('now', ?)
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (f"-{days} days", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def start_run(run: RunState) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_log
                (run_id, run_type, started_at, status)
            VALUES (?, ?, ?, 'running')
            """,
            (run.run_id, run.run_type, run.started_at.isoformat()),
        )
        conn.commit()


def complete_run(run: RunState) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE run_log SET
                completed_at = ?,
                total_cost_usd = ?,
                items_collected = ?,
                items_published = ?,
                errors = ?,
                status = ?
            WHERE run_id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                run.total_cost_usd,
                run.items_collected,
                run.items_published,
                json.dumps(run.errors),
                run.status,
                run.run_id,
            ),
        )
        conn.commit()


def upsert_model(name: str, provider: str, **kwargs) -> None:
    """Upsert an AI model entry."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO models (name, provider, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                provider = excluded.provider,
                updated_at = excluded.updated_at
            """,
            (name, provider, now),
        )
        for key, val in kwargs.items():
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            conn.execute(
                f"UPDATE models SET {key} = ? WHERE name = ?", (val, name)
            )
        conn.commit()


def upsert_org(name: str, **kwargs) -> None:
    """Upsert an organization entry."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO organizations (name, updated_at)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (name, now),
        )
        for key, val in kwargs.items():
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            conn.execute(
                f"UPDATE organizations SET {key} = ? WHERE name = ?", (val, name)
            )
        conn.commit()


def store_published_article(
    article_id: str,
    title: str,
    published_date: str,
    topics: list[str],
    content_hash: str,
    url: Optional[str] = None,
    edition_id: Optional[str] = None,
    word_count: Optional[int] = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO published_articles
                (id, title, published_date, topics, content_hash, url, edition_id, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                title,
                published_date,
                json.dumps(topics),
                content_hash,
                url,
                edition_id,
                word_count,
            ),
        )
        conn.commit()


def get_untriaged_items(days: int = 3) -> list[CollectedItem]:
    """
    Return items collected in the last N days that have never been triaged
    (significance_score IS NULL). Used to recover items from runs where
    triage failed (e.g., LiteLLM was down).
    """
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM source_items
            WHERE significance_score IS NULL
              AND collected_at >= datetime('now', ?)
            ORDER BY source_tier ASC, collected_at DESC
            """,
            (f"-{days} days",),
        ).fetchall()

    items = []
    for r in rows:
        try:
            published_at = None
            if r["published_at"]:
                try:
                    published_at = datetime.fromisoformat(r["published_at"]).astimezone(timezone.utc)
                except Exception:
                    pass
            collected_at = datetime.fromisoformat(r["collected_at"]).astimezone(timezone.utc)

            item = CollectedItem(
                id=r["id"],
                source_name=r["source_name"],
                source_tier=r["source_tier"],
                url=r["url"],
                title=r["title"],
                raw_content=r["raw_content"],
                published_at=published_at,
                collected_at=collected_at,
                tags=json.loads(r["tags"] or "[]"),
                significance_score=None,
                promoted=bool(r["promoted"]),
            )
            items.append(item)
        except Exception:
            continue

    return items


def get_model_info(name: str) -> Optional[dict]:
    """Get stored metadata for an AI model."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM models WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None


def get_org_info(name: str) -> Optional[dict]:
    """Get stored metadata for an organization."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM organizations WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None
