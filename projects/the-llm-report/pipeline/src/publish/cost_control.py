"""
The LLM Report — Cost Control
Budget gate, stage cost logging, anomaly detection.
Enforces per-run, per-day, per-month caps and anomaly threshold.
NLSpec: CLAUDE.md Cost Control section
"""

from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(
    os.environ.get(
        "KB_DB_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data/kb.sqlite"),
    )
)

BUDGET_PER_RUN = float(os.environ.get("BUDGET_PER_RUN", "15.0"))
BUDGET_PER_DAY = float(os.environ.get("BUDGET_PER_DAY", "20.0"))
BUDGET_PER_MONTH = float(os.environ.get("BUDGET_PER_MONTH", "200.0"))
ANOMALY_MULTIPLIER = float(os.environ.get("BUDGET_ANOMALY_MULTIPLIER", "2.0"))
ROLLING_WINDOW = int(os.environ.get("BUDGET_ROLLING_WINDOW", "10"))

COST_LOG_SCHEMA = """
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
    for stmt in COST_LOG_SCHEMA.strip().split(";"):
        s = stmt.strip()
        if s:
            conn.execute(s)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def log_stage_cost(
    run_id: str,
    stage: str,
    model: str,
    in_tok: int,
    out_tok: int,
    cost: float,
    cached: bool = False,
    task_description: str = "",
) -> None:
    """Log a single LLM call cost to the database."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO cost_log
                (run_id, stage, model_used, input_tokens, output_tokens,
                 cost_usd, task_description, timestamp, cached)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, stage, model, in_tok, out_tok, cost,
                task_description,
                datetime.now(timezone.utc).isoformat(),
                int(cached),
            ),
        )
        conn.commit()


def _get_run_cost(conn, run_id: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    return row[0]


def _get_day_cost(conn) -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE timestamp LIKE ?",
        (f"{today}%",),
    ).fetchone()
    return row[0]


def _get_month_cost(conn) -> float:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE timestamp LIKE ?",
        (f"{month}%",),
    ).fetchone()
    return row[0]


def _get_rolling_avg(conn, current_run_id: str) -> float:
    rows = conn.execute(
        """
        SELECT run_id, SUM(cost_usd) as run_total
        FROM cost_log
        WHERE run_id != ?
        GROUP BY run_id
        ORDER BY MAX(timestamp) DESC
        LIMIT ?
        """,
        (current_run_id, ROLLING_WINDOW),
    ).fetchall()
    if not rows:
        return 0.0
    return sum(r[1] for r in rows) / len(rows)


def check_budget_gate(run_id: str, stage: str = "") -> tuple[bool, str]:
    """
    Check if budget allows continuing the current run.
    Returns (can_continue: bool, reason: str).
    Checks per-run, per-day, per-month caps, and anomaly detection.
    """
    with _conn() as conn:
        run_cost = _get_run_cost(conn, run_id)
        day_cost = _get_day_cost(conn)
        month_cost = _get_month_cost(conn)
        rolling_avg = _get_rolling_avg(conn, run_id)

    per_run = float(os.environ.get("BUDGET_PER_RUN", str(BUDGET_PER_RUN)))
    per_day = float(os.environ.get("BUDGET_PER_DAY", str(BUDGET_PER_DAY)))
    per_month = float(os.environ.get("BUDGET_PER_MONTH", str(BUDGET_PER_MONTH)))

    if run_cost >= per_run:
        return False, f"per-run budget exceeded: ${run_cost:.4f} >= ${per_run:.2f}"
    if day_cost >= per_day:
        return False, f"per-day budget exceeded: ${day_cost:.4f} >= ${per_day:.2f}"
    if month_cost >= per_month:
        return False, f"per-month budget exceeded: ${month_cost:.4f} >= ${per_month:.2f}"

    anomaly_threshold = rolling_avg * ANOMALY_MULTIPLIER
    if rolling_avg > 0 and run_cost > anomaly_threshold:
        return False, (
            f"anomaly: current run ${run_cost:.4f} > {ANOMALY_MULTIPLIER}x "
            f"rolling avg ${rolling_avg:.4f}"
        )

    return True, "ok"


def get_run_cost_report(run_id: str) -> dict:
    """Return cost breakdown by stage for a run."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT stage, model_used,
                   SUM(input_tokens) as in_tok, SUM(output_tokens) as out_tok,
                   SUM(cost_usd) as cost, COUNT(*) as calls,
                   SUM(cached) as cached_calls
            FROM cost_log WHERE run_id = ?
            GROUP BY stage, model_used ORDER BY cost DESC
            """,
            (run_id,),
        ).fetchall()
        total = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(input_tokens),0), "
            "COALESCE(SUM(output_tokens),0), COUNT(*) FROM cost_log WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return {
        "run_id": run_id,
        "total_cost": total[0],
        "total_input_tokens": total[1],
        "total_output_tokens": total[2],
        "total_calls": total[3],
        "by_stage": [
            {
                "stage": r[0], "model": r[1], "input_tokens": r[2],
                "output_tokens": r[3], "cost": r[4],
                "calls": r[5], "cached_calls": r[6],
            }
            for r in rows
        ],
    }
