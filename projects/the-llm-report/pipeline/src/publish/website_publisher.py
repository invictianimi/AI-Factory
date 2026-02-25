"""
The LLM Report — Website Publisher
Writes newsletter editions to the website repo and pushes via git.
NLSpec Section 5, Scenario 5.1
"""

from __future__ import annotations
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pipeline.src.kb import store as kb_store

WEBSITE_DIR = Path(
    os.environ.get(
        "WEBSITE_DIR",
        str(Path(__file__).parent.parent.parent.parent.parent / "website"),
    )
)

EDITIONS_DIR_RELATIVE = "src/content/editions"


def _yaml_front_matter(title: str, date: str, description: str) -> str:
    # Escape any quotes in description
    safe_desc = description.replace('"', "'")[:150]
    return (
        f"---\n"
        f'title: "{title}"\n'
        f'date: "{date}"\n'
        f'description: "{safe_desc}"\n'
        f'tags: ["ai", "llm", "newsletter"]\n'
        f'author: "The LLM Report"\n'
        f"---\n\n"
    )


def publish_to_website(
    newsletter_md: str,
    edition_date: str,
    run_id: str,
    website_dir: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Write a newsletter edition to the website repo and push.

    1. Create markdown file at website/src/content/editions/YYYY-MM-DD.md
    2. Add YAML front matter
    3. Git add + commit + push
    4. Log to KB published_articles table

    Args:
        newsletter_md: Full newsletter markdown content
        edition_date: Date string YYYY-MM-DD
        run_id: Pipeline run ID
        website_dir: Override website directory (for testing)
        dry_run: If True, write file but skip git operations

    Returns:
        dict with: file_path, commit_sha, push_success, article_id
    """
    ws_dir = website_dir or WEBSITE_DIR
    editions_dir = ws_dir / EDITIONS_DIR_RELATIVE
    editions_dir.mkdir(parents=True, exist_ok=True)

    file_path = editions_dir / f"{edition_date}.md"

    # Extract description from first non-heading line
    lines = [l.strip() for l in newsletter_md.split("\n") if l.strip() and not l.startswith("#")]
    description = lines[0][:150] if lines else f"The LLM Report — {edition_date}"

    title = f"The LLM Report \u2014 {edition_date}"
    front_matter = _yaml_front_matter(title, edition_date, description)
    full_content = front_matter + newsletter_md

    file_path.write_text(full_content, encoding="utf-8")

    commit_sha = ""
    push_success = False

    if not dry_run:
        try:
            # Git add
            subprocess.run(
                ["git", "add", str(file_path)],
                cwd=str(ws_dir), capture_output=True, check=True, timeout=30
            )
            # Git commit
            commit_result = subprocess.run(
                ["git", "commit", "-m",
                 f"content(edition): {edition_date} edition [run:{run_id[:8]}]"],
                cwd=str(ws_dir), capture_output=True, text=True, timeout=30
            )
            # Extract commit SHA
            if commit_result.returncode == 0:
                sha_result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=str(ws_dir), capture_output=True, text=True, timeout=10
                )
                commit_sha = sha_result.stdout.strip()
            # Git push
            push_result = subprocess.run(
                ["git", "push"],
                cwd=str(ws_dir), capture_output=True, text=True, timeout=60
            )
            push_success = push_result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            # Log error but don't crash — partial publish is better than no publish
            pass

    # Log to KB
    article_id = str(uuid.uuid4())
    try:
        kb_store.store_published_article(
            article_id=article_id,
            title=title,
            published_date=edition_date,
            topics=["ai", "llm", "newsletter"],
            content_hash=_content_hash(newsletter_md),
            url=f"https://thellmreport.com/editions/{edition_date}",
            edition_id=run_id,
            word_count=len(newsletter_md.split()),
        )
    except Exception:
        pass  # KB logging failure doesn't block publish

    return {
        "file_path": str(file_path),
        "commit_sha": commit_sha,
        "push_success": push_success,
        "article_id": article_id,
        "title": title,
    }


def _content_hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()
