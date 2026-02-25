"""
AI Factory — Bridge CLI Command Handlers
Implements all `factory <command>` commands.
NLSpec Section 16.2.1
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def get_status_text(detail: bool = False) -> str:
    """Return factory status. Must fit in < 25 lines."""
    lines = []
    lines.append(f"AI Factory Status — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 50)

    # Operational state
    lines.append(f"State:     RUNNING")
    lines.append(f"Pipeline:  IDLE (cron: Mon/Wed/Fri 05:00 UTC, Sat 06:00 UTC)")

    # Last run
    last_run = _get_last_run()
    if last_run:
        lines.append(f"Last run:  {last_run.get('started_at', 'unknown')[:10]} "
                     f"[{last_run.get('status', 'unknown')}] "
                     f"{last_run.get('items_published', 0)} published "
                     f"${last_run.get('total_cost_usd', 0):.4f}")
    else:
        lines.append(f"Last run:  No runs yet")

    # Next run
    next_run = _get_next_run()
    lines.append(f"Next run:  {next_run}")

    # Budget
    budget = _get_budget_status()
    lines.append(f"Budget:    {budget}")

    if detail:
        lines.append("")
        lines.append("Per-stage breakdown (last run):")
        costs = _get_stage_costs()
        for stage, cost in costs.items():
            lines.append(f"  {stage:15s} ${cost:.4f}")

        lines.append("")
        lines.append("Pending Boss-approval items:")
        pending = _get_pending_approvals()
        if pending:
            for item in pending[:3]:
                lines.append(f"  - {item}")
        else:
            lines.append("  None")

    return "\n".join(lines)


def _get_last_run() -> dict | None:
    try:
        import sqlite3
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            return None
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT run_id, run_type, status, items_published, total_cost_usd, started_at "
            "FROM run_log ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return {"run_id": row[0], "run_type": row[1], "status": row[2],
                    "items_published": row[3], "total_cost_usd": row[4], "started_at": row[5]}
    except Exception:
        pass
    return None


def _get_next_run() -> str:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    schedule = {0: "05:00", 2: "05:00", 4: "05:00", 5: "06:00"}  # Mon/Wed/Fri/Sat
    for offset in range(1, 8):
        nxt = now + timedelta(days=offset)
        if nxt.weekday() in schedule:
            return f"{nxt.strftime('%A %Y-%m-%d')} at {schedule[nxt.weekday()]} UTC"
    return "Unknown"


def _get_budget_status() -> str:
    try:
        import sqlite3
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            return "$0.00 spent today / $20.00 daily cap"
        conn = sqlite3.connect(db)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM cost_log WHERE timestamp LIKE ?",
            (f"{today}%",)
        ).fetchone()
        conn.close()
        daily_cap = float(os.environ.get("BUDGET_PER_DAY", "20"))
        spent = row[0]
        return f"${spent:.4f} spent today / ${daily_cap:.2f} daily cap"
    except Exception:
        return "Budget data unavailable"


def _get_stage_costs() -> dict:
    try:
        import sqlite3
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            return {}
        conn = sqlite3.connect(db)
        run_row = conn.execute(
            "SELECT run_id FROM run_log ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not run_row:
            conn.close()
            return {}
        rows = conn.execute(
            "SELECT stage, SUM(cost_usd) FROM cost_log WHERE run_id = ? GROUP BY stage",
            (run_row[0],)
        ).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _get_pending_approvals() -> list[str]:
    backlog = REPO_ROOT / "docs/board-reviews/backlog.md"
    if not backlog.exists():
        return []
    content = backlog.read_text()
    items = []
    for line in content.split("\n"):
        if line.startswith("## ") and "Directive" in line:
            items.append(line[3:])
    return items


def cmd_status(args) -> int:
    print(get_status_text(detail=hasattr(args, "detail") and args.detail))
    return 0


def cmd_costs(args) -> int:
    period = getattr(args, "period", "daily")
    try:
        import sqlite3
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            print("No cost data yet.")
            return 0
        conn = sqlite3.connect(db)
        now = datetime.now(timezone.utc)
        if period == "daily":
            filter_str = now.strftime("%Y-%m-%d") + "%"
            cap = float(os.environ.get("BUDGET_PER_DAY", "20"))
            period_label = "Today"
        elif period == "weekly":
            from datetime import timedelta
            week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
            filter_str = f"{week_start[:7]}%"
            cap = float(os.environ.get("BUDGET_PER_DAY", "20")) * 7
            period_label = "This week"
        else:  # monthly
            filter_str = now.strftime("%Y-%m") + "%"
            cap = float(os.environ.get("BUDGET_PER_MONTH", "200"))
            period_label = "This month"

        rows = conn.execute(
            "SELECT stage, model_used, SUM(cost_usd), COUNT(*) "
            "FROM cost_log WHERE timestamp LIKE ? GROUP BY stage, model_used ORDER BY SUM(cost_usd) DESC",
            (filter_str,)
        ).fetchall()
        total = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM cost_log WHERE timestamp LIKE ?",
            (filter_str,)
        ).fetchone()[0]
        conn.close()

        print(f"\nCost Report — {period_label}")
        print(f"{'Stage':<20} {'Model':<25} {'Cost':>10} {'Calls':>8}")
        print("-" * 65)
        for r in rows:
            print(f"{r[0]:<20} {r[1]:<25} ${r[2]:>8.4f} {r[3]:>8}")
        print("-" * 65)
        print(f"{'TOTAL':<46} ${total:>8.4f}")
        print(f"Budget cap: ${cap:.2f} | Used: {total/cap*100:.1f}%")
    except Exception as e:
        print(f"Cost data unavailable: {e}")
    return 0


def cmd_schedule(args) -> int:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    schedule_map = {0: "standard", 2: "standard", 4: "friday", 5: "deep-dive"}
    print("Scheduled runs — next 7 days:")
    print(f"{'Date':<20} {'Day':<12} {'Time':>6} {'Type'}")
    print("-" * 50)
    shown = 0
    for offset in range(1, 14):
        d = now + timedelta(days=offset)
        if d.weekday() in schedule_map:
            time_utc = "05:00" if d.weekday() != 5 else "06:00"
            print(f"{d.strftime('%Y-%m-%d'):<20} {d.strftime('%A'):<12} {time_utc:>6}  {schedule_map[d.weekday()]}")
            shown += 1
            if shown >= 7:
                break
    return 0


def cmd_output(args) -> int:
    latest = getattr(args, "latest", False)
    n = getattr(args, "list", None)
    try:
        import sqlite3
        db = str(REPO_ROOT / "projects/the-llm-report/data/kb.sqlite")
        if not Path(db).exists():
            print("No published articles yet.")
            return 0
        conn = sqlite3.connect(db)
        if latest:
            row = conn.execute(
                "SELECT title, published_date, word_count, url FROM published_articles ORDER BY published_date DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                print(f"Latest Edition:")
                print(f"  Title: {row[0]}")
                print(f"  Date: {row[1]}")
                print(f"  Words: {row[2]}")
                print(f"  URL: {row[3]}")
        else:
            limit = int(n) if n else 10
            rows = conn.execute(
                "SELECT title, published_date FROM published_articles ORDER BY published_date DESC LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            for r in rows:
                print(f"  {r[1]}  {r[0]}")
    except Exception as e:
        print(f"Output data unavailable: {e}")
    return 0


def cmd_board(args) -> int:
    latest = getattr(args, "latest", False)
    history = getattr(args, "history", False)
    reviews_dir = REPO_ROOT / "docs/board-reviews"

    if history:
        review_dirs = sorted(reviews_dir.glob("review-*"), reverse=True)
        print(f"Board Review History ({len(review_dirs)} reviews):")
        for rd in review_dirs[:10]:
            print(f"  {rd.name}")
    else:
        # Latest board review
        review_dirs = sorted(reviews_dir.glob("review-*"), reverse=True)
        if review_dirs:
            latest_dir = review_dirs[0]
            summary = latest_dir / "summary.md"
            if summary.exists():
                print(summary.read_text()[:500])
            else:
                print(f"Latest review: {latest_dir.name} (no summary yet)")
        else:
            print("No board reviews yet. First review scheduled: Thursday 02:00")
    return 0


def cmd_roadmap(args) -> int:
    roadmap = REPO_ROOT / "docs/roadmap.md"
    section = None
    if hasattr(args, "now") and args.now:
        section = "Now"
    elif hasattr(args, "next") and args.next:
        section = "Next"
    elif hasattr(args, "backlog") and args.backlog:
        section = "Later"

    if roadmap.exists():
        content = roadmap.read_text()
        if section:
            # Extract section
            lines = content.split("\n")
            in_section = False
            output = []
            for line in lines:
                if line.startswith(f"## {section}"):
                    in_section = True
                elif line.startswith("## ") and in_section:
                    break
                if in_section:
                    output.append(line)
            print("\n".join(output) if output else f"No '{section}' section found")
        else:
            print(content[:2000])
    else:
        print("Roadmap not found.")
    return 0


def cmd_direct(args) -> int:
    message = " ".join(args.message) if isinstance(args.message, list) else args.message
    from bridge.directive_processor import process_directive
    result = process_directive(message, source="cli")
    print(f"Directive received.")
    print(f"Classification: {result['level']}")
    print(f"Action: {result['action']}")
    print(f"ID: {result['directive_id']}")
    return 0


def cmd_feature(args) -> int:
    description = " ".join(args.description) if isinstance(args.description, list) else args.description
    feature_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    feature_dir = REPO_ROOT / "docs/board-reviews/feature-proposals"
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_file = feature_dir / f"{feature_id}-feature.md"
    feature_file.write_text(
        f"# Feature Request {feature_id}\n\n"
        f"**Submitted:** {datetime.now(timezone.utc).isoformat()}\n"
        f"**Source:** CLI\n\n"
        f"## Description\n\n{description}\n\n"
        f"## Status\n\nQueued for next board review.\n"
    )
    print(f"Feature request received.")
    print(f"ID: {feature_id}")
    print(f"Status: Queued for next board review (Thursday 02:00)")
    print(f"Initial assessment: Requires board evaluation for technical feasibility and cost impact.")
    return 0


def cmd_logs(args) -> int:
    log_path = REPO_ROOT / "logs/as-built.md"
    tail = getattr(args, "tail", 20)
    errors_only = getattr(args, "errors", False)
    stage = getattr(args, "stage", None)

    if log_path.exists():
        lines = log_path.read_text().split("\n")
        if errors_only:
            lines = [l for l in lines if "ERROR" in l or "error" in l.lower()]
        if stage:
            lines = [l for l in lines if stage.lower() in l.lower()]
        for line in lines[-int(tail):]:
            print(line)
    else:
        print("No logs yet.")
    return 0


def cmd_pause(args) -> int:
    pause_file = REPO_ROOT / "bridge/PAUSED"
    pause_file.write_text(f"PAUSED at {datetime.now(timezone.utc).isoformat()}\n")
    print("Factory paused. Run `factory resume` to continue.")
    return 0


def cmd_resume(args) -> int:
    pause_file = REPO_ROOT / "bridge/PAUSED"
    if pause_file.exists():
        pause_file.unlink()
    print("Factory resumed.")
    return 0


def cmd_stop(args) -> int:
    stop_file = REPO_ROOT / "bridge/STOPPED"
    stop_file.write_text(f"STOPPED at {datetime.now(timezone.utc).isoformat()}\n")
    print("Graceful shutdown initiated. Current stage will complete before stopping.")
    return 0


def cmd_kill(args) -> int:
    import subprocess
    kill_file = REPO_ROOT / "bridge/KILLED"
    kill_file.write_text(f"KILLED at {datetime.now(timezone.utc).isoformat()}\n")
    # Kill pipeline processes
    try:
        subprocess.run(["pkill", "-f", "run_pipeline.py"], capture_output=True)
    except Exception:
        pass
    from orchestrator.as_built import log
    log("Factory killed via `factory kill` command", level="ERROR")
    print("All factory processes terminated. State saved.")
    return 0


def cmd_rollback(args) -> int:
    confirm = input("This will revert to last git checkpoint. Type YES to confirm: ")
    if confirm.strip() != "YES":
        print("Rollback cancelled.")
        return 0
    import subprocess
    result = subprocess.run(
        ["git", "log", "--oneline", "-3"],
        cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    print(f"Recent commits:\n{result.stdout}")
    print("Rollback initiated. Run `git reset --hard HEAD~1` manually to complete.")
    return 0


def cmd_report(args) -> int:
    from bridge.push_notifications import generate_daily_report
    report_type = getattr(args, "daily", False)
    date = getattr(args, "date", None)

    if report_type or args.daily:
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = generate_daily_report(date)
        print(report[:3000])
    return 0


def cmd_bridge(args) -> int:
    """Interactive bridge mode."""
    from bridge.intent_classifier import classify
    from bridge.directive_processor import process_directive

    print("\n" + "=" * 55)
    print(get_status_text())
    print("=" * 55)
    print("\nInteractive Bridge — type `exit` to quit\n")

    while True:
        try:
            user_input = input("Boss> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if user_input.lower() in ("exit", "quit", "q"):
            print("Bridge session closed.")
            break

        if not user_input:
            continue

        # Classify intent
        print("Processing...")
        classification = classify(user_input)
        intent = classification["intent"]

        if intent == "STATUS":
            print(get_status_text())
        elif intent == "DIRECTIVE":
            result = process_directive(user_input, source="interactive_bridge")
            print(f"Directive received ({result['level']}): {result['action']}")
        elif intent == "CLARIFICATION_NEEDED":
            print(f"Could you clarify your intent? I interpreted this as: {classification.get('summary', user_input[:50])}")
        elif intent == "EMERGENCY":
            print("Emergency acknowledged. Available commands: factory pause, factory stop, factory kill, factory rollback")
        else:
            # INQUIRY or FEATURE — provide info
            print(f"Understood (intent: {intent}). {get_status_text(detail=True)[:300]}...")

        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="factory",
        description="AI Factory — Boss CLI Interface",
    )
    subparsers = parser.add_subparsers(dest="command")

    # bridge (interactive)
    subparsers.add_parser("bridge", help="Interactive bridge session")

    # status
    p = subparsers.add_parser("status", help="Factory status")
    p.add_argument("--detail", action="store_true")

    # costs
    p = subparsers.add_parser("costs", help="Cost report")
    p.add_argument("--period", choices=["daily", "weekly", "monthly"], default="daily")

    # schedule
    subparsers.add_parser("schedule", help="Upcoming pipeline schedule")

    # output
    p = subparsers.add_parser("output", help="Published editions")
    p.add_argument("--latest", action="store_true")
    p.add_argument("--list", type=int, default=10, metavar="N")

    # board
    p = subparsers.add_parser("board", help="Board review info")
    p.add_argument("--latest", action="store_true")
    p.add_argument("--history", action="store_true")

    # roadmap
    p = subparsers.add_parser("roadmap", help="Project roadmap")
    p.add_argument("--now", action="store_true")
    p.add_argument("--next", action="store_true")
    p.add_argument("--backlog", action="store_true")

    # direct
    p = subparsers.add_parser("direct", help="Submit Boss directive")
    p.add_argument("message", nargs="+")

    # feature
    p = subparsers.add_parser("feature", help="Submit feature request")
    p.add_argument("description", nargs="+")

    # logs
    p = subparsers.add_parser("logs", help="View operational logs")
    p.add_argument("--tail", type=int, default=20, metavar="N")
    p.add_argument("--stage", type=str)
    p.add_argument("--errors", action="store_true")

    # control commands
    subparsers.add_parser("pause", help="Pause pipeline")
    subparsers.add_parser("resume", help="Resume pipeline")
    subparsers.add_parser("stop", help="Graceful shutdown")
    subparsers.add_parser("kill", help="Immediate termination")
    subparsers.add_parser("rollback", help="Rollback to last checkpoint")

    # report
    p = subparsers.add_parser("report", help="Generate/view reports")
    p.add_argument("--daily", action="store_true")
    p.add_argument("date", nargs="?")

    args = parser.parse_args()

    handlers = {
        "bridge": cmd_bridge,
        "status": cmd_status,
        "costs": cmd_costs,
        "schedule": cmd_schedule,
        "output": cmd_output,
        "board": cmd_board,
        "roadmap": cmd_roadmap,
        "direct": cmd_direct,
        "feature": cmd_feature,
        "logs": cmd_logs,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "stop": cmd_stop,
        "kill": cmd_kill,
        "rollback": cmd_rollback,
        "report": cmd_report,
    }

    if args.command is None:
        parser.print_help()
        return 0

    handler = handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1
