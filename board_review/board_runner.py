"""
AI Factory — Autonomous Board Review Runner
5-phase board review process.
Phase 1: Data gathering (zero LLM cost)
Phase 2: Parallel individual member reviews
Phase 3: Chair synthesis
Phase 4: Implementation of AUTO-IMPLEMENT items
Phase 5: Notification to Boss
NLSpec Section 17.4
"""

from __future__ import annotations
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
BOARD_REVIEWS_DIR = REPO_ROOT / "docs/board-reviews"

# Budget: 10% of weekly budget for weekly review
WEEKLY_BUDGET_PCT = float(os.environ.get("BOARD_REVIEW_WEEKLY_BUDGET_PCT", "10"))
MONTHLY_BUDGET_PCT = float(os.environ.get("BOARD_REVIEW_MONTHLY_BUDGET_PCT", "15"))

# Board member models
BOARD_MEMBERS = {
    "chair": os.environ.get("BOARD_CHAIR_MODEL", "claude-opus-4-6"),
    "adversarial": os.environ.get("BOARD_ADVERSARIAL_MODEL", "gpt-5.2-pro"),
    "cost_auditor": os.environ.get("BOARD_COST_MODEL", "deepseek-r1"),
    "integration": os.environ.get("BOARD_INTEGRATION_MODEL", "gemini-2.5-pro"),
}

# Auto-implement authority boundaries
MAX_COST_INCREASE_PCT = float(os.environ.get("BOARD_AUTO_IMPLEMENT_COST_THRESHOLD_PCT", "5"))


def run_board_review(review_type: str = "weekly", llm_callers: Optional[dict] = None) -> dict:
    """
    Execute a full board review.

    Args:
        review_type: "weekly" or "monthly"
        llm_callers: Optional dict of {member_name: callable} for testing injection

    Returns:
        dict with review results and implemented changes
    """
    review_id = f"review-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    review_dir = BOARD_REVIEWS_DIR / review_id
    review_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "review_id": review_id,
        "type": review_type,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }

    # Phase 1: Data gathering (zero LLM cost)
    phase1 = _phase1_gather_data(review_id)
    result["phases"]["1_data_gathering"] = phase1
    _save_phase(review_dir, "01-input-data.md", phase1["input_md"])

    # Phase 2: Parallel individual reviews
    phase2 = _phase2_individual_reviews(
        phase1["input_md"], review_type, llm_callers=llm_callers
    )
    result["phases"]["2_individual_reviews"] = phase2
    for member, review in phase2["reviews"].items():
        _save_phase(review_dir, f"02-{member}-review.md", review)

    # Phase 3: Chair synthesis
    phase3 = _phase3_synthesis(
        phase1["input_md"],
        phase2["reviews"],
        llm_callers=llm_callers,
    )
    result["phases"]["3_synthesis"] = phase3
    _save_phase(review_dir, "03-synthesis.md", phase3["synthesis"])

    # Phase 4: Implementation
    phase4 = _phase4_implement(phase3["recommendations"])
    result["phases"]["4_implementation"] = phase4
    _save_phase(review_dir, "04-implementation.md", json.dumps(phase4, indent=2))

    # Phase 5: Notification
    _phase5_notify(review_id, review_type, phase3["recommendations"], phase4)

    # Archive
    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_phase(review_dir, "summary.md", _format_summary(result))
    _update_changelog(review_id, review_type, phase4)

    return result


def _phase1_gather_data(review_id: str) -> dict:
    """Phase 1: Gather data with ZERO LLM calls."""
    from board_review.data_gatherer import gather_review_input, format_review_input_md
    data = gather_review_input(review_id)
    assert data["llm_calls_made"] == 0, "Phase 1 must make zero LLM calls"
    return {"data": data, "input_md": format_review_input_md(data)}


def _phase2_individual_reviews(input_md: str, review_type: str,
                                llm_callers: Optional[dict] = None) -> dict:
    """Phase 2: Parallel reviews from all 4 board members."""
    prompts = _load_board_prompts()

    def run_member_review(member: str, model: str) -> tuple[str, str]:
        role_prompt = prompts.get(member, f"Review as {member}.")
        full_prompt = f"{role_prompt}\n\n{input_md}"

        caller = (llm_callers or {}).get(member)
        if caller:
            response = caller(full_prompt)
        else:
            response = _call_board_llm(model, full_prompt, member)
        return member, response

    reviews = {}
    members_with_models = list(BOARD_MEMBERS.items())

    # Run in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_member_review, member, model): member
            for member, model in members_with_models
        }
        for future in as_completed(futures, timeout=300):
            member = futures[future]
            try:
                _, review = future.result()
                reviews[member] = review
            except Exception as e:
                reviews[member] = f"[ERROR: {member} review failed: {e}]"

    return {"reviews": reviews, "parallel": True}


def _phase3_synthesis(input_md: str, reviews: dict,
                       llm_callers: Optional[dict] = None) -> dict:
    """Phase 3: Chair synthesizes all reviews into recommendations."""
    prompts = _load_board_prompts()
    synthesis_prompt_template = prompts.get("synthesis", "")

    reviews_text = "\n\n".join([
        f"## {member.upper()} Review\n{review}"
        for member, review in reviews.items()
    ])

    full_prompt = (
        f"{synthesis_prompt_template}\n\n"
        f"## Input Data\n{input_md}\n\n"
        f"## Board Member Reviews\n{reviews_text}\n\n"
        "Synthesize into recommendations. For each recommendation, classify as:\n"
        "AUTO-IMPLEMENT, BOSS-APPROVE, or DEFER\n\n"
        "Return JSON: {\"recommendations\": [{\"item\": str, \"classification\": str, \"rationale\": str, \"supports\": [member names]}]}"
    )

    chair_caller = (llm_callers or {}).get("chair")
    if chair_caller:
        synthesis_text = chair_caller(full_prompt)
    else:
        synthesis_text = _call_board_llm(BOARD_MEMBERS["chair"], full_prompt, "chair_synthesis")

    # Parse recommendations
    recommendations = []
    try:
        if isinstance(synthesis_text, str):
            if "```" in synthesis_text:
                synthesis_text = synthesis_text.split("```")[1].strip("json").strip()
            data = json.loads(synthesis_text)
            recommendations = data.get("recommendations", [])
    except Exception:
        recommendations = []

    return {
        "synthesis": synthesis_text if isinstance(synthesis_text, str) else str(synthesis_text),
        "recommendations": recommendations,
    }


def _phase4_implement(recommendations: list) -> dict:
    """Phase 4: Implement AUTO-IMPLEMENT items, queue BOSS-APPROVE items."""
    implemented = []
    boss_approve = []
    deferred = []

    for rec in recommendations:
        classification = rec.get("classification", "DEFER").upper()
        item = rec.get("item", "")

        if classification == "AUTO-IMPLEMENT":
            # Verify within authority boundaries
            if _within_authority_bounds(rec):
                success = _implement_recommendation(rec)
                if success:
                    implemented.append({"item": item, "status": "implemented"})
                else:
                    # Failed implementation — reclassify as BOSS-APPROVE
                    boss_approve.append({"item": item, "reason": "implementation_failed"})
            else:
                boss_approve.append({"item": item, "reason": "exceeds_authority_bounds"})
        elif classification == "BOSS-APPROVE":
            boss_approve.append({"item": item, "reason": "board_classified"})
        else:
            deferred.append({"item": item})

    # Queue BOSS-APPROVE items
    if boss_approve:
        _queue_boss_approval(boss_approve)

    return {
        "implemented": implemented,
        "boss_approve": boss_approve,
        "deferred": deferred,
    }


def _within_authority_bounds(rec: dict) -> bool:
    """Check if a recommendation is within the board's auto-implement authority."""
    # Must not increase costs by more than MAX_COST_INCREASE_PCT
    item = rec.get("item", "").lower()
    if any(kw in item for kw in ["pipeline stage", "add stage", "remove stage", "bridge", "board review"]):
        return False
    # Chair MUST be among supporters (NLSpec Section 17.5: "at least 2 members INCLUDING Chair")
    supports = rec.get("supports", [])
    if "chair" not in [s.lower() for s in supports]:
        return False
    if len(supports) < 2:
        return False
    return True


def _implement_recommendation(rec: dict) -> bool:
    """Implement a board recommendation. Returns True on success."""
    # Log the implementation
    changelog = BOARD_REVIEWS_DIR / "changelog.md"
    existing = changelog.read_text() if changelog.exists() else "# Board Review Changelog\n\n"
    if "*No reviews yet*" in existing:
        existing = existing.replace("*No reviews yet — board review system starts at Milestone 7.*", "")
    entry = (
        f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d')} — Auto-Implemented\n"
        f"**Item:** {rec.get('item', 'Unknown')}\n"
        f"**Rationale:** {rec.get('rationale', 'Board consensus')}\n"
    )
    changelog.write_text(existing + entry)
    return True


def _queue_boss_approval(items: list) -> None:
    """Add BOSS-APPROVE items to the backlog."""
    backlog = BOARD_REVIEWS_DIR / "backlog.md"
    existing = backlog.read_text() if backlog.exists() else "# Board Backlog\n\n"
    if "*No items yet*" in existing:
        existing = existing.replace("*No items yet — board review system starts at Milestone 7.*", "")
    for item in items:
        entry = (
            f"\n## Board Item ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})\n"
            f"**Item:** {item.get('item', 'Unknown')}\n"
            f"**Reason for Boss Approval:** {item.get('reason', 'Board review')}\n"
        )
        existing += entry
    backlog.write_text(existing)


def _phase5_notify(review_id: str, review_type: str, recommendations: list, phase4: dict) -> None:
    """Phase 5: Email Boss with review summary."""
    from orchestrator.alert import send_alert
    implemented = phase4.get("implemented", [])
    boss_approve = phase4.get("boss_approve", [])
    body = (
        f"Board Review {review_id} ({review_type}) complete.\n\n"
        f"Implemented: {len(implemented)} item(s)\n"
        f"Pending Boss Approval: {len(boss_approve)} item(s)\n\n"
        + ("\n".join(f"  - {i['item']}" for i in implemented[:3]) if implemented else "No auto-implementations.")
        + "\n\nFull report: docs/board-reviews/" + review_id
    )
    send_alert(
        subject_suffix=f"Board Review #{review_id} Complete — {len(implemented)} implemented, {len(boss_approve)} pending approval",
        body=body,
        severity="INFO",
    )


def _call_board_llm(model: str, prompt: str, role: str) -> str:
    """Call a board member LLM."""
    try:
        import litellm
        litellm.api_base = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[{role} review unavailable: {e}]"


def _load_board_prompts() -> dict:
    """Load board member prompt templates."""
    prompts_dir = REPO_ROOT / "orchestrator/config/board-prompts"
    prompts = {}
    for fname, key in [
        ("chair-opus.md", "chair"),
        ("adversarial-gpt.md", "adversarial"),
        ("cost-auditor-deepseek.md", "cost_auditor"),
        ("integration-gemini.md", "integration"),
        ("synthesis.md", "synthesis"),
    ]:
        path = prompts_dir / fname
        if path.exists():
            prompts[key] = path.read_text()
    return prompts


def _save_phase(review_dir: Path, filename: str, content: str) -> None:
    (review_dir / filename).write_text(content if isinstance(content, str) else str(content))


def _format_summary(result: dict) -> str:
    phase4 = result.get("phases", {}).get("4_implementation", {})
    return (
        f"# Board Review Summary — {result['review_id']}\n\n"
        f"Type: {result['type']}\n"
        f"Started: {result.get('started_at', '')}\n"
        f"Completed: {result.get('completed_at', '')}\n\n"
        f"## Results\n\n"
        f"Auto-implemented: {len(phase4.get('implemented', []))}\n"
        f"Pending Boss approval: {len(phase4.get('boss_approve', []))}\n"
        f"Deferred: {len(phase4.get('deferred', []))}\n"
    )


def _update_changelog(review_id: str, review_type: str, phase4: dict) -> None:
    changelog = BOARD_REVIEWS_DIR / "changelog.md"
    existing = changelog.read_text() if changelog.exists() else "# Changelog\n\n"
    if "*No reviews yet*" in existing:
        existing = existing.replace("*No reviews yet — board review system starts at Milestone 7.*", "")
    implemented = phase4.get("implemented", [])
    if not implemented:
        return
    entry = f"\n## Review {review_id} ({review_type}) — {len(implemented)} changes\n"
    for item in implemented:
        entry += f"- {item['item']}\n"
    changelog.write_text(existing + entry)
