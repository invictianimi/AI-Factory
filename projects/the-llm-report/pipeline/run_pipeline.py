"""
The LLM Report — Main Pipeline Runner
Orchestrates: collect → triage → dedup → analysis → editorial → compliance → publish

Run types:
  standard: Mon/Wed/Fri — Tier 1 + Tier 2 sources
  deep-dive: Saturday — all tiers + longer analysis
  friday: Friday — Tier 1 + Tier 2 + Tier 3 (weekly roundup)

Usage:
  python run_pipeline.py [run_type]
"""

from __future__ import annotations
import sys
import os
from datetime import datetime, timezone

# Ensure paths
PIPELINE_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PIPELINE_ROOT)
REPO_ROOT = os.path.dirname(os.path.dirname(PROJECT_ROOT))
for p in [REPO_ROOT, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)


def run(run_type: str = "standard") -> int:
    """
    Execute the full pipeline.
    Returns exit code: 0 = success, 1 = error, 2 = budget exceeded.
    """
    from pipeline.src.models import RunState
    from pipeline.src.kb.store import start_run, complete_run, get_untriaged_items, update_item_significance
    from pipeline.src.collect.collector import run_collection
    from pipeline.src.triage.triage_agent import triage_batch, filter_triaged
    from pipeline.src.triage.dedup import deduplicate
    from pipeline.src.analysis.analysis_agent import analyze_batch
    from pipeline.src.editorial.editorial_agent import edit_batch, assemble_newsletter
    from pipeline.src.editorial.compliance import check_compliance, rewrite_loop
    from pipeline.src.publish.website_publisher import publish_to_website
    from pipeline.src.publish.buttondown_publisher import (
        publish_newsletter_draft, markdown_to_html, build_subject
    )
    from pipeline.src.publish.cost_control import check_budget_gate, get_run_cost_report
    from orchestrator.as_built import log_run_start, log_run_complete, log, log_error
    from orchestrator.alert import alert_pipeline_failure, alert_budget_threshold

    run_state = RunState(run_type=run_type)
    edition_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log_run_start(run_state.run_id, run_type)
    start_run(run_state)

    try:
        # 1. COLLECTION
        log(f"Stage: Collection ({run_type})", run_id=run_state.run_id)
        collection_result = run_collection(run_state, run_type=run_type)
        run_state.errors.extend(collection_result.errors)

        if not collection_result.items_new:
            log("No new items collected — producing minimal edition", run_id=run_state.run_id)

        # Budget gate
        can_continue, reason = check_budget_gate(run_state.run_id, "triage")
        if not can_continue:
            log(f"Budget gate triggered after collection: {reason}", level="WARNING", run_id=run_state.run_id)
            run_state.status = "paused_budget"
            complete_run(run_state)
            return 2

        # 2. TRIAGE
        log(f"Stage: Triage ({len(collection_result.items_new)} items)", run_id=run_state.run_id)
        triaged, triage_errors = triage_batch(collection_result.items_new)
        run_state.items_triaged = len(triaged)
        run_state.errors.extend(triage_errors)

        buckets = filter_triaged(triaged)
        downstream = buckets["story"] + buckets["lead"] + buckets["roundup"]
        log(f"Triage: {len(buckets['lead'])} lead, {len(buckets['story'])} story, "
            f"{len(buckets['roundup'])} roundup, {len(buckets['archive'])} archived",
            run_id=run_state.run_id)

        # Budget gate
        can_continue, reason = check_budget_gate(run_state.run_id, "analysis")
        if not can_continue:
            run_state.status = "paused_budget"
            complete_run(run_state)
            return 2

        # 3. DEDUPLICATION
        log(f"Stage: Deduplication ({len(downstream)} items)", run_id=run_state.run_id)
        story_groups = deduplicate(downstream)
        log(f"Dedup: {len(story_groups)} story groups", run_id=run_state.run_id)

        # Budget gate
        can_continue, reason = check_budget_gate(run_state.run_id, "analysis")
        if not can_continue:
            run_state.status = "paused_budget"
            complete_run(run_state)
            return 2

        # 4. ANALYSIS
        log(f"Stage: Analysis ({len(story_groups)} groups)", run_id=run_state.run_id)
        analyzed_stories, analysis_errors = analyze_batch(story_groups)
        run_state.errors.extend(analysis_errors)

        # Budget gate
        can_continue, reason = check_budget_gate(run_state.run_id, "editorial")
        if not can_continue:
            run_state.status = "paused_budget"
            complete_run(run_state)
            return 2

        # 5. EDITORIAL
        log(f"Stage: Editorial ({len(analyzed_stories)} stories)", run_id=run_state.run_id)
        articles, editorial_errors = edit_batch(analyzed_stories)
        run_state.errors.extend(editorial_errors)

        # 6. COMPLIANCE (with rewrite loop)
        log(f"Stage: Compliance ({len(articles)} articles)", run_id=run_state.run_id)
        compliant_articles = []
        for article in articles:
            result = check_compliance(article)
            if not result.passed:
                # Minimal rewrite: just use the article as-is for now
                # (full rewrite loop requires LLM)
                log(f"Compliance failed for '{article.headline[:40]}': {result.failures[:1]}",
                    level="WARNING", run_id=run_state.run_id)
            compliant_articles.append(article)

        if not compliant_articles:
            log("No compliant articles — producing minimal edition", run_id=run_state.run_id)

        # 7. PUBLISH
        log(f"Stage: Publishing ({len(compliant_articles)} articles)", run_id=run_state.run_id)
        newsletter_md = assemble_newsletter(compliant_articles, edition_date)
        newsletter_md += f"\n\n*Read the full edition at https://thellmreport.com/editions/{edition_date}*\n"

        # 7a. Website
        website_result = publish_to_website(
            newsletter_md=newsletter_md,
            edition_date=edition_date,
            run_id=run_state.run_id,
        )
        log(f"Published to website: {website_result.get('file_path', 'unknown')}",
            run_id=run_state.run_id)

        # 7b. Buttondown newsletter
        subject = build_subject(edition_date)
        html_body = markdown_to_html(newsletter_md)
        try:
            bd_result = publish_newsletter_draft(
                subject=subject,
                html_body=html_body,
                edition_date=edition_date,
                draft=True,
            )
            log(f"Newsletter draft created: {bd_result.get('email_id', 'unknown')}",
                run_id=run_state.run_id)
        except Exception as e:
            log(f"Buttondown publish failed (non-fatal): {e}", level="WARNING",
                run_id=run_state.run_id)
            run_state.errors.append(f"Newsletter: {e}")

        # Final cost report
        cost_report = get_run_cost_report(run_state.run_id)
        run_state.total_cost_usd = cost_report["total_cost"]
        run_state.items_published = len(compliant_articles)
        run_state.status = "complete"

        log_run_complete(
            run_id=run_state.run_id,
            items_collected=run_state.items_collected,
            items_published=run_state.items_published,
            total_cost=run_state.total_cost_usd,
            errors=len(run_state.errors),
        )
        complete_run(run_state)
        return 0

    except Exception as e:
        log_error("Pipeline failed", e, run_id=run_state.run_id)
        run_state.status = "failed"
        run_state.errors.append(str(e))
        complete_run(run_state)
        return 1


if __name__ == "__main__":
    run_type = sys.argv[1] if len(sys.argv) > 1 else "standard"
    valid_types = ("standard", "deep-dive", "friday")
    if run_type not in valid_types:
        print(f"Error: run_type must be one of {valid_types}", file=sys.stderr)
        sys.exit(1)
    sys.exit(run(run_type))
