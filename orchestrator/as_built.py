"""
AI Factory — As-Built Logger
Appends significant actions to logs/as-built.md.
Every action, cost, decision, error is logged. No exceptions.
"""

from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


AS_BUILT_PATH = Path(
    os.environ.get(
        "AS_BUILT_LOG",
        str(Path(__file__).parent.parent / "logs/as-built.md"),
    )
)


def log(
    action: str,
    detail: str = "",
    level: str = "INFO",
    run_id: Optional[str] = None,
    milestone: Optional[str] = None,
    cost_usd: Optional[float] = None,
) -> None:
    """
    Append a log entry to logs/as-built.md.

    Args:
        action: Short description of what happened (e.g., "Collection complete")
        detail: Optional additional context
        level: INFO, WARNING, ERROR, MILESTONE, DECISION
        run_id: Pipeline run ID if applicable
        milestone: Milestone name if this is a milestone event
        cost_usd: Cost if applicable
    """
    AS_BUILT_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_tag = f" [run:{run_id}]" if run_id else ""
    cost_tag = f" [cost:${cost_usd:.4f}]" if cost_usd is not None else ""

    if level == "MILESTONE":
        entry = f"\n### {action}\n\n"
        entry += f"**Time:** {now}{run_tag}{cost_tag}\n"
        if detail:
            entry += f"\n{detail}\n"
        entry += "\n---\n"
    elif level == "ERROR":
        entry = f"\n**[ERROR {now}{run_tag}]** {action}"
        if detail:
            entry += f"\n\n```\n{detail}\n```"
        entry += "\n"
    elif level == "DECISION":
        entry = f"\n**[DECISION {now}]** {action}"
        if detail:
            entry += f"\n\n> {detail}"
        entry += "\n"
    else:
        entry = f"\n**[{level} {now}{run_tag}{cost_tag}]** {action}"
        if detail:
            entry += f" — {detail}"
        entry += "\n"

    with open(AS_BUILT_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def log_milestone(
    milestone: str,
    summary: str,
    scenarios_passed: Optional[int] = None,
    scenarios_total: Optional[int] = None,
    cost_usd: Optional[float] = None,
) -> None:
    """Log a milestone completion event."""
    detail_parts = [summary]
    if scenarios_passed is not None and scenarios_total is not None:
        pct = scenarios_passed / scenarios_total * 100
        detail_parts.append(
            f"**Scenarios:** {scenarios_passed}/{scenarios_total} passed ({pct:.0f}%)"
        )
    if cost_usd is not None:
        detail_parts.append(f"**Cost:** ${cost_usd:.4f}")

    log(
        action=f"Milestone Complete: {milestone}",
        detail="\n".join(detail_parts),
        level="MILESTONE",
        cost_usd=cost_usd,
    )


def log_error(action: str, error: Exception, run_id: Optional[str] = None) -> None:
    """Log an error with traceback."""
    import traceback
    detail = traceback.format_exc()
    log(action=action, detail=detail, level="ERROR", run_id=run_id)


def log_decision(decision: str, rationale: str) -> None:
    """Log an architectural or operational decision."""
    log(action=decision, detail=rationale, level="DECISION")


def log_run_start(run_id: str, run_type: str = "standard") -> None:
    """Log the start of a pipeline run."""
    log(
        action=f"Pipeline run started ({run_type})",
        run_id=run_id,
        level="INFO",
    )


def log_run_complete(
    run_id: str,
    items_collected: int,
    items_published: int,
    total_cost: float,
    errors: int = 0,
) -> None:
    """Log pipeline run completion summary."""
    log(
        action="Pipeline run complete",
        detail=(
            f"Collected: {items_collected} | Published: {items_published} | "
            f"Errors: {errors}"
        ),
        level="INFO",
        run_id=run_id,
        cost_usd=total_cost,
    )
