"""
AI Factory — Alert System
Sends email alerts via SMTP when failures or threshold breaches occur.
Only triggers after 3 self-recovery attempts have failed.
"""

from __future__ import annotations
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional


def _load_env() -> dict:
    """Force-load .env file, overriding any inherited shell environment variables."""
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    return env


def send_alert(
    subject_suffix: str,
    body: str,
    severity: str = "ERROR",
    project_name: str = "The LLM Report",
) -> bool:
    """
    Send an email alert via SMTP (Gmail or any STARTTLS provider).

    Args:
        subject_suffix: Short description (e.g., "Collection stage failed")
        body: Full alert body text
        severity: ERROR, WARNING, CRITICAL, INFO
        project_name: Project name for subject line

    Returns:
        True if sent successfully, False otherwise.
    """
    # Force-load from .env to avoid stale shell env vars
    env = _load_env()
    smtp_host = env.get("SMTP_HOST", os.environ.get("SMTP_HOST", ""))
    smtp_port = int(env.get("SMTP_PORT", os.environ.get("SMTP_PORT", "587")))
    smtp_user = env.get("SMTP_USER", os.environ.get("SMTP_USER", ""))
    smtp_pass = env.get("SMTP_PASS", os.environ.get("SMTP_PASS", ""))
    alert_from_addr = env.get("ALERT_FROM", os.environ.get("ALERT_FROM", smtp_user))
    alert_from_name = env.get("ALERT_FROM_NAME", os.environ.get("ALERT_FROM_NAME", ""))
    alert_to = env.get("ALERT_TO", os.environ.get("ALERT_TO", ""))

    if not all([smtp_host, smtp_user, smtp_pass, alert_to]):
        # Log to stderr but don't crash — alert infrastructure shouldn't kill pipeline
        import sys
        print(
            f"[ALERT SKIPPED] Missing SMTP config. Subject would have been: "
            f"[AI-FACTORY] [{severity}] {subject_suffix}",
            file=sys.stderr,
        )
        return False

    # Format From header with optional display name: "AI-Factory <addr@domain.com>"
    from email.utils import formataddr
    alert_from = formataddr((alert_from_name, alert_from_addr)) if alert_from_name else alert_from_addr

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"[AI-FACTORY] [{severity}] {subject_suffix}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = alert_from
    msg["To"] = alert_to

    text_body = f"""AI Factory Alert — {project_name}

Time: {now}
Severity: {severity}

{body}

— AI Factory Orchestrator
"""
    msg.attach(MIMEText(text_body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        import sys
        print(f"[ALERT FAILED] Could not send alert: {e}", file=sys.stderr)
        return False


def alert_budget_threshold(
    cap_name: str,
    used: float,
    cap: float,
    pct: float,
    run_id: Optional[str] = None,
) -> bool:
    """Alert when a budget threshold is hit (50%, 80%, 100%)."""
    level = "CRITICAL" if pct >= 100 else "WARNING"
    run_tag = f" (run: {run_id})" if run_id else ""
    body = f"""Budget threshold reached{run_tag}:

Cap: {cap_name.upper()}
Limit: ${cap:.2f}
Used: ${used:.4f}
Percentage: {pct:.1f}%

{'⚠️ OVER BUDGET — pipeline paused.' if pct >= 100 else f'At {pct:.0f}% of {cap_name} budget.'}

WHAT WAS TRIED: Budget enforcement via LiteLLM proxy
RECOMMENDATION: Review cost_log.sqlite for high-cost stages.
  Consider increasing budget cap or optimizing model routing.
LOGS: See logs/as-built.md and projects/the-llm-report/data/cost_log.sqlite
"""
    return send_alert(
        subject_suffix=f"{cap_name} budget at {pct:.0f}% (${used:.4f}/${cap:.2f})",
        body=body,
        severity=level,
    )


def alert_pipeline_failure(
    stage: str,
    failure_description: str,
    recovery_attempts: str,
    ai_recommendation: str,
    run_id: Optional[str] = None,
) -> bool:
    """Alert when pipeline stage fails after 3 recovery attempts."""
    run_tag = f" [run: {run_id}]" if run_id else ""
    body = f"""Pipeline stage failure{run_tag}:

STAGE: {stage}
WHAT FAILED: {failure_description}

WHAT WE TRIED:
{recovery_attempts}

RECOMMENDATION:
{ai_recommendation}

LOGS: See logs/as-built.md
"""
    return send_alert(
        subject_suffix=f"{stage} stage failed after 3 attempts",
        body=body,
        severity="ERROR",
    )


def alert_anomaly(
    run_id: str,
    current_cost: float,
    rolling_avg: float,
    multiplier: float,
) -> bool:
    """Alert when cost anomaly is detected (>2x rolling average)."""
    body = f"""Cost anomaly detected for run {run_id}:

Current run cost: ${current_cost:.4f}
Rolling average: ${rolling_avg:.4f}
Threshold: {multiplier}x average = ${rolling_avg * multiplier:.4f}

Pipeline paused pending review.

RECOMMENDATION: Check logs/as-built.md for unusual LLM call patterns.
"""
    return send_alert(
        subject_suffix=f"Cost anomaly: ${current_cost:.4f} vs ${rolling_avg:.4f} avg",
        body=body,
        severity="WARNING",
    )
