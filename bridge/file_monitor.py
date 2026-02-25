"""
AI Factory — Bridge File Drop Monitor
Polls bridge/inbox/ for .md files and processes them as Boss directives.
Active hours: poll every 15 min. Off-hours: poll every 60 min.
NLSpec Section 16.2.2
"""

from __future__ import annotations
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

INBOX_DIR = Path(
    os.environ.get("BRIDGE_INBOX",
    str(Path(__file__).parent.parent / "bridge/inbox"))
)
OUTBOX_DIR = Path(
    os.environ.get("BRIDGE_OUTBOX",
    str(Path(__file__).parent.parent / "bridge/outbox"))
)
PROCESSED_DIR = Path(
    os.environ.get("BRIDGE_PROCESSED",
    str(Path(__file__).parent.parent / "bridge/processed"))
)
BRIDGE_LOG_DIR = Path(
    os.environ.get("BRIDGE_LOG_DIR",
    str(Path(__file__).parent.parent / "logs/bridge"))
)

ACTIVE_HOURS_START = int(os.environ.get("BRIDGE_ACTIVE_HOURS_START", "6").replace(":00", ""))
ACTIVE_HOURS_END = int(os.environ.get("BRIDGE_ACTIVE_HOURS_END", "22").replace(":00", ""))


def is_active_hours() -> bool:
    hour = datetime.now().hour
    return ACTIVE_HOURS_START <= hour < ACTIVE_HOURS_END


def get_poll_interval() -> int:
    """Return poll interval in seconds based on time of day."""
    active_interval = int(os.environ.get("BRIDGE_INBOX_POLL_INTERVAL_ACTIVE", "900"))
    inactive_interval = int(os.environ.get("BRIDGE_INBOX_POLL_INTERVAL_INACTIVE", "3600"))
    return active_interval if is_active_hours() else inactive_interval


def scan_inbox() -> list[Path]:
    """Return list of unprocessed .md files in inbox."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(INBOX_DIR.glob("*.md"))


def process_inbox_file(file_path: Path) -> str:
    """
    Process a single inbox file.
    1. Read the file content
    2. Classify intent
    3. Route to appropriate handler
    4. Write response to outbox
    5. Move original to processed

    Returns: response text
    """
    from bridge.intent_classifier import classify
    from bridge.directive_processor import process_directive
    from bridge.cli_commands import get_status_text

    content = file_path.read_text(encoding="utf-8")
    classification = classify(content)
    intent = classification["intent"]

    # Route based on intent
    if intent == "STATUS":
        response = get_status_text()
    elif intent == "DIRECTIVE":
        result = process_directive(content, source=f"file_drop:{file_path.name}")
        response = (
            f"Directive received.\n\n"
            f"Classification: {result['level']}\n"
            f"Action: {result['action']}\n"
            f"ID: {result['directive_id']}"
        )
    elif intent == "EMERGENCY":
        response = "Emergency acknowledged. Use `factory kill` or `factory pause` for immediate action."
    else:
        response = f"Input received (intent: {intent}).\n\n{_generate_inquiry_response(content)}"

    # Write response to outbox
    _write_response(file_path.name, response)

    # Move to processed
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = PROCESSED_DIR / f"{timestamp}-{file_path.name}"
    shutil.move(str(file_path), str(dest))

    # Log interaction
    _log_interaction(file_path.name, content, intent, response)

    return response


def _write_response(original_filename: str, response: str) -> None:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M")
    base = original_filename.replace(".md", "")
    response_file = OUTBOX_DIR / f"{now}-response-to-{base}.md"
    response_file.write_text(
        f"# Response to: {original_filename}\n\n"
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n\n"
        f"---\n\n{response}\n"
    )


def _generate_inquiry_response(inquiry: str) -> str:
    """Generate a basic response to an inquiry using available data."""
    # For non-LLM responses, return status + hint
    from bridge.cli_commands import get_status_text
    return f"{get_status_text()}\n\n*(For detailed inquiries, use `factory bridge` for interactive session)*"


def _log_interaction(filename: str, input_text: str, intent: str, response: str) -> None:
    BRIDGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = BRIDGE_LOG_DIR / f"{date}-bridge.log"
    with open(log_file, "a") as f:
        f.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] FILE_DROP\n"
            f"File: {filename}\n"
            f"Intent: {intent}\n"
            f"Input: {input_text[:200]}...\n"
            f"Response: {response[:200]}...\n"
        )


def run_once() -> int:
    """Scan inbox and process all pending files. Returns count processed."""
    files = scan_inbox()
    processed = 0
    for f in files:
        try:
            process_inbox_file(f)
            processed += 1
        except Exception as e:
            # Write error response and move to processed anyway
            _write_response(f.name, f"Error processing file: {e}")
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            shutil.move(str(f), str(PROCESSED_DIR / f"{timestamp}-error-{f.name}"))
    return processed
