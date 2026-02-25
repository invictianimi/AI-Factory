"""
AI Factory — Board Review Data Gatherer
Phase 1 of board review: compile operational data with ZERO LLM API calls.
All data from local SQLite, logs, and file system.
NLSpec Section 17.4 Phase 1
"""

from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def gather_review_input(review_id: str) -> dict:
    """
    Gather all data needed for board review from local sources.
    MUST NOT make any LLM API calls.
    Returns: dict with all sections of review input.
    """
    data = {
        "review_id": review_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_calls_made": 0,  # MUST remain 0

        # Operational data
        "run_history": _get_run_history(days=7),
        "cost_analysis": _get_cost_analysis(days=7),
        "error_summary": _get_error_summary(days=7),

        # Quality metrics
        "kb_metrics": _get_kb_metrics(),
        "compliance_metrics": _get_compliance_metrics(),

        # System metrics
        "disk_usage": _get_disk_usage(),
        "cron_status": _check_cron_status(),

        # Backlog items
        "pending_boss_approvals": _get_pending_approvals(),
        "board_backlog": _get_board_backlog(),

        # Budget analysis
        "budget_analysis": _get_budget_analysis(),
    }
    return data


def _get_run_history(days: int = 7) -> list[dict]:
    try:
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT run_id, run_type, status, items_collected, items_published, total_cost_usd, started_at "
            "FROM run_log WHERE started_at >= ? ORDER BY started_at DESC",
            (cutoff,)
        ).fetchall()
        conn.close()
        return [{"run_id": r[0], "run_type": r[1], "status": r[2],
                 "items_collected": r[3], "items_published": r[4],
                 "cost": r[5], "date": r[6]} for r in rows]
    except Exception:
        return []


def _get_cost_analysis(days: int = 7) -> dict:
    try:
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            return {}
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(db)
        total = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM cost_log WHERE timestamp >= ?", (cutoff,)
        ).fetchone()[0]
        by_model = conn.execute(
            "SELECT model_used, SUM(cost_usd), COUNT(*) FROM cost_log WHERE timestamp >= ? GROUP BY model_used ORDER BY SUM(cost_usd) DESC",
            (cutoff,)
        ).fetchall()
        by_stage = conn.execute(
            "SELECT stage, SUM(cost_usd), COUNT(*) FROM cost_log WHERE timestamp >= ? GROUP BY stage ORDER BY SUM(cost_usd) DESC",
            (cutoff,)
        ).fetchall()
        conn.close()
        return {
            "total_period": total,
            "by_model": [{"model": r[0], "cost": r[1], "calls": r[2]} for r in by_model],
            "by_stage": [{"stage": r[0], "cost": r[1], "calls": r[2]} for r in by_stage],
        }
    except Exception:
        return {}


def _get_error_summary(days: int = 7) -> dict:
    log_path = REPO_ROOT / "logs/as-built.md"
    if not log_path.exists():
        return {"errors": 0, "warnings": 0}
    content = log_path.read_text()
    return {
        "errors": content.count("[ERROR"),
        "warnings": content.count("[WARNING"),
    }


def _get_kb_metrics() -> dict:
    try:
        from pipeline.src.kb.vector_store import get_item_count, get_article_count
        from pipeline.src.kb.semantic_cache import get_cache_stats
        return {
            "source_item_embeddings": get_item_count(),
            "article_embeddings": get_article_count(),
            "cache_stats": get_cache_stats(),
        }
    except Exception:
        return {}


def _get_compliance_metrics() -> dict:
    return {"note": "Compliance metrics available after pipeline runs."}


def _get_disk_usage() -> dict:
    import shutil
    disk = shutil.disk_usage("/")
    return {
        "total_gb": disk.total / (1024**3),
        "free_gb": disk.free / (1024**3),
        "used_pct": disk.used / disk.total * 100,
    }


def _check_cron_status() -> dict:
    import subprocess
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        has_pipeline = "run-pipeline.sh" in result.stdout
        return {"pipeline_cron_active": has_pipeline}
    except Exception:
        return {"pipeline_cron_active": False}


def _get_pending_approvals() -> list[str]:
    backlog = REPO_ROOT / "docs/board-reviews/backlog.md"
    if not backlog.exists():
        return []
    content = backlog.read_text()
    items = []
    for line in content.split("\n"):
        if line.startswith("## "):
            items.append(line[3:])
    return items


def _get_board_backlog() -> list[str]:
    return _get_pending_approvals()


def _get_budget_analysis() -> dict:
    try:
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            return {}
        conn = sqlite3.connect(db)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        month_cost = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM cost_log WHERE timestamp LIKE ?",
            (f"{month}%",)
        ).fetchone()[0]
        conn.close()
        monthly_cap = float(os.environ.get("BUDGET_PER_MONTH", "200"))
        return {
            "month_cost": month_cost,
            "monthly_cap": monthly_cap,
            "month_pct": month_cost / monthly_cap * 100 if monthly_cap > 0 else 0,
        }
    except Exception:
        return {}


def format_review_input_md(data: dict) -> str:
    """Format review input data as markdown for board member prompts."""
    lines = [
        f"# Board Review Input — {data['review_id']}",
        f"Generated: {data['generated_at']}",
        f"LLM calls made during data gathering: {data['llm_calls_made']} (must be 0)",
        "",
        "## Run History (Last 7 Days)",
    ]
    runs = data.get("run_history", [])
    if runs:
        for r in runs:
            lines.append(f"- {r['date'][:10]}: {r['run_type']} [{r['status']}] "
                         f"{r['items_published']} published, ${r.get('cost', 0):.4f}")
    else:
        lines.append("No runs in period.")

    lines.extend(["", "## Cost Analysis"])
    costs = data.get("cost_analysis", {})
    if costs:
        lines.append(f"Total period: ${costs.get('total_period', 0):.4f}")
        for m in costs.get("by_model", [])[:3]:
            lines.append(f"  {m['model']}: ${m['cost']:.4f} ({m['calls']} calls)")
    else:
        lines.append("No cost data.")

    lines.extend(["", "## Error Summary"])
    errors = data.get("error_summary", {})
    lines.append(f"Errors: {errors.get('errors', 0)}, Warnings: {errors.get('warnings', 0)}")

    lines.extend(["", "## Pending Boss Approvals"])
    pending = data.get("pending_boss_approvals", [])
    if pending:
        for item in pending:
            lines.append(f"- {item}")
    else:
        lines.append("None")

    return "\n".join(lines)
