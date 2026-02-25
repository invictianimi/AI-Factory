"""
AI Factory — Cost Logger
Every LLM call logged: model, tokens, cost, task, timestamp.
Enforces budget caps and triggers alerts when thresholds are exceeded.
"""

from __future__ import annotations
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Budget caps from CLAUDE.md
BUDGET_PER_RUN = float(os.environ.get("BUDGET_PER_RUN", "15.00"))
BUDGET_PER_DAY = float(os.environ.get("BUDGET_PER_DAY", "20.00"))
BUDGET_PER_MONTH = float(os.environ.get("BUDGET_PER_MONTH", "200.00"))
ANOMALY_MULTIPLIER = float(os.environ.get("BUDGET_ANOMALY_MULTIPLIER", "2.0"))

DB_PATH = Path(
    os.environ.get(
        "COST_LOG_DB",
        str(Path(__file__).parent.parent / "projects/the-llm-report/data/cost_log.sqlite"),
    )
)


@dataclass
class LLMCall:
    run_id: str
    stage: str
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    task_description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cached: bool = False  # True if served from semantic cache


@dataclass
class BudgetStatus:
    run_cost: float
    day_cost: float
    month_cost: float
    run_cap: float
    day_cap: float
    month_cap: float
    run_ok: bool
    day_ok: bool
    month_ok: bool
    anomaly_detected: bool
    rolling_avg: float

    @property
    def should_stop(self) -> bool:
        return not self.run_ok or not self.day_ok or not self.month_ok or self.anomaly_detected

    def alert_level(self) -> Optional[str]:
        """Return alert level if any threshold is hit."""
        for cap_name, used, cap in [
            ("run", self.run_cost, self.run_cap),
            ("day", self.day_cost, self.day_cap),
            ("month", self.month_cost, self.month_cap),
        ]:
            pct = (used / cap * 100) if cap > 0 else 0
            if pct >= 100:
                return "CRITICAL"
            if pct >= 80:
                return "WARNING"
        if self.anomaly_detected:
            return "WARNING"
        return None


def _ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cost_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            model_used TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            task_description TEXT,
            timestamp TEXT NOT NULL,
            cached INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_run_id ON cost_log(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON cost_log(timestamp)")
    conn.commit()


@contextmanager
def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        _ensure_db(conn)
        yield conn
    finally:
        conn.close()


def log_call(call: LLMCall) -> BudgetStatus:
    """
    Log an LLM call to the cost database.
    Returns current budget status — caller should check status.should_stop.
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cost_log
                (run_id, stage, model_used, input_tokens, output_tokens,
                 cost_usd, task_description, timestamp, cached)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call.run_id,
                call.stage,
                call.model_used,
                call.input_tokens,
                call.output_tokens,
                call.cost_usd,
                call.task_description,
                call.timestamp.isoformat(),
                int(call.cached),
            ),
        )
        conn.commit()
        return _get_budget_status(conn, call.run_id)


def _get_budget_status(conn: sqlite3.Connection, current_run_id: str) -> BudgetStatus:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    # Run cost
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE run_id = ?",
        (current_run_id,),
    ).fetchone()
    run_cost = row[0]

    # Day cost
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE timestamp LIKE ?",
        (f"{today}%",),
    ).fetchone()
    day_cost = row[0]

    # Month cost
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE timestamp LIKE ?",
        (f"{month}%",),
    ).fetchone()
    month_cost = row[0]

    # Rolling average run cost (last 10 completed runs)
    rows = conn.execute(
        """
        SELECT run_id, SUM(cost_usd) as run_total
        FROM cost_log
        WHERE run_id != ?
        GROUP BY run_id
        ORDER BY MAX(timestamp) DESC
        LIMIT 10
        """,
        (current_run_id,),
    ).fetchall()
    rolling_avg = sum(r[1] for r in rows) / len(rows) if rows else 0.0
    anomaly = rolling_avg > 0 and run_cost > (rolling_avg * ANOMALY_MULTIPLIER)

    return BudgetStatus(
        run_cost=run_cost,
        day_cost=day_cost,
        month_cost=month_cost,
        run_cap=BUDGET_PER_RUN,
        day_cap=BUDGET_PER_DAY,
        month_cap=BUDGET_PER_MONTH,
        run_ok=run_cost <= BUDGET_PER_RUN,
        day_ok=day_cost <= BUDGET_PER_DAY,
        month_ok=month_cost <= BUDGET_PER_MONTH,
        anomaly_detected=anomaly,
        rolling_avg=rolling_avg,
    )


def get_budget_status(run_id: str) -> BudgetStatus:
    """Get current budget status for a run without logging a call."""
    with _get_conn() as conn:
        return _get_budget_status(conn, run_id)


def get_run_summary(run_id: str) -> dict:
    """Return a cost summary for a completed run."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT model_used, stage,
                   SUM(input_tokens) as in_tok, SUM(output_tokens) as out_tok,
                   SUM(cost_usd) as cost, COUNT(*) as calls,
                   SUM(cached) as cached_calls
            FROM cost_log
            WHERE run_id = ?
            GROUP BY model_used, stage
            ORDER BY cost DESC
            """,
            (run_id,),
        ).fetchall()

        total = conn.execute(
            "SELECT SUM(cost_usd), SUM(input_tokens), SUM(output_tokens), COUNT(*) FROM cost_log WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        return {
            "run_id": run_id,
            "total_cost": total[0] or 0,
            "total_input_tokens": total[1] or 0,
            "total_output_tokens": total[2] or 0,
            "total_calls": total[3] or 0,
            "by_model_stage": [
                {
                    "model": r[0],
                    "stage": r[1],
                    "input_tokens": r[2],
                    "output_tokens": r[3],
                    "cost": r[4],
                    "calls": r[5],
                    "cached_calls": r[6],
                }
                for r in rows
            ],
        }


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for a call before making it."""
    # Cost per 1K tokens (approximate)
    RATES = {
        "claude-opus-4-6": (0.015, 0.075),
        "claude-sonnet-4-5": (0.003, 0.015),
        "claude-haiku-4-5": (0.00025, 0.00125),
        "gpt-5.2-pro": (0.010, 0.030),
        "deepseek-r1": (0.00055, 0.00219),
        "deepseek-v3": (0.00027, 0.00110),
        "gemini-2.5-pro": (0.00125, 0.00500),
    }
    rate_in, rate_out = RATES.get(model, (0.001, 0.003))
    return (input_tokens / 1000 * rate_in) + (output_tokens / 1000 * rate_out)
