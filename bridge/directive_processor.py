"""
AI Factory — Directive Processor
Classifies Boss directives as CONFIG-LEVEL or SPEC-LEVEL.
CONFIG-LEVEL: implement immediately.
SPEC-LEVEL: queue for board review.
NLSpec Section 16.4
"""

from __future__ import annotations
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DIRECTIVES_DIR = Path(
    os.environ.get("DIRECTIVES_DIR",
    str(Path(__file__).parent.parent / "docs/directives"))
)

CONFIG_LEVEL_PATTERNS = [
    "add source", "remove source", "change model", "update budget",
    "adjust threshold", "change schedule", "pause on", "skip", "add tier",
    "update config", "change setting", "increase limit", "decrease limit",
    "collection source", "as a source", "add.*source", "source.*add",
    "add url", "add domain", "add feed", "add rss",
]

SPEC_LEVEL_PATTERNS = [
    "new feature", "add feature", "build", "create", "new integration",
    "podcast", "video", "new format", "add pipeline", "new stage",
    "change editorial", "add language", "new outlet",
]


def classify_directive(directive_text: str) -> str:
    """Classify a directive as CONFIG-LEVEL or SPEC-LEVEL based on keywords."""
    import re
    text_lower = directive_text.lower()
    for pattern in CONFIG_LEVEL_PATTERNS:
        if re.search(pattern, text_lower):
            return "CONFIG-LEVEL"
    for pattern in SPEC_LEVEL_PATTERNS:
        if pattern in text_lower:
            return "SPEC-LEVEL"
    # Default: SPEC-LEVEL (safer)
    return "SPEC-LEVEL"


def process_directive(directive_text: str, source: str = "cli") -> dict:
    """
    Process a Boss directive.
    CONFIG-LEVEL: implement immediately (config changes).
    SPEC-LEVEL: queue for next board review.
    Returns action dict.
    """
    directive_id = str(uuid.uuid4())[:8]
    level = classify_directive(directive_text)
    now = datetime.now(timezone.utc).isoformat()

    if level == "CONFIG-LEVEL":
        action = "Implementing immediately — config-level change"
        status = "implementing"
    else:
        action = "Queued for next board review — spec-level change requires review"
        status = "queued_for_board"
        _queue_for_board(directive_id, directive_text, now)

    # Log directive
    _log_directive(directive_id, directive_text, level, action, source, now)

    return {
        "directive_id": directive_id,
        "level": level,
        "action": action,
        "status": status,
        "timestamp": now,
    }


def _log_directive(directive_id: str, text: str, level: str,
                   action: str, source: str, timestamp: str) -> None:
    DIRECTIVES_DIR.mkdir(parents=True, exist_ok=True)
    date = timestamp[:10]
    log_file = DIRECTIVES_DIR / f"{date}-{directive_id}.md"
    log_file.write_text(
        f"# Directive {directive_id}\n\n"
        f"**Date:** {timestamp}\n"
        f"**Source:** {source}\n"
        f"**Classification:** {level}\n"
        f"**Action:** {action}\n\n"
        f"## Text\n\n{text}\n"
    )


def _queue_for_board(directive_id: str, text: str, timestamp: str) -> None:
    """Add spec-level directive to board backlog."""
    backlog = Path(__file__).parent.parent / "docs/board-reviews/backlog.md"
    backlog.parent.mkdir(parents=True, exist_ok=True)
    existing = backlog.read_text() if backlog.exists() else "# Board Review Backlog\n\n"
    entry = f"\n## Directive {directive_id} ({timestamp[:10]})\n{text}\n"
    if "*No items yet*" in existing:
        existing = existing.replace("*No items yet — board review system starts at Milestone 7.*", "")
    backlog.write_text(existing + entry)
