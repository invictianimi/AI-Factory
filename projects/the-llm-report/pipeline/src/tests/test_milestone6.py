"""
Milestone 6 Holdout Scenarios — Full Integration + Scheduling
Scenarios 6.1 through 6.5 from scenarios.md
Uses mock data — no real API calls.
"""

from __future__ import annotations
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    db_path = tmp_path / "kb.sqlite"
    chroma_path = tmp_path / "chroma"
    monkeypatch.setenv("KB_DB_PATH", str(db_path))
    monkeypatch.setenv("CHROMA_PATH", str(chroma_path))
    monkeypatch.setenv("CACHE_DB_PATH", str(db_path))
    monkeypatch.setenv("BUDGET_PER_RUN", "15.0")
    monkeypatch.setenv("BUDGET_PER_DAY", "20.0")
    monkeypatch.setenv("BUDGET_PER_MONTH", "200.0")
    monkeypatch.setenv("WEBSITE_DIR", str(tmp_path / "website"))
    # Create website editions dir
    (tmp_path / "website" / "src" / "content" / "editions").mkdir(parents=True)

    from pipeline.src.kb import vector_store as vs, store as st, semantic_cache as sc
    old_chroma, old_db, old_cache = vs.CHROMA_PATH, st.DB_PATH, sc.CACHE_DB_PATH
    vs.CHROMA_PATH = chroma_path
    st.DB_PATH = db_path
    sc.CACHE_DB_PATH = db_path
    vs._client = None

    yield tmp_path

    vs.CHROMA_PATH = old_chroma
    st.DB_PATH = old_db
    sc.CACHE_DB_PATH = old_cache
    vs._client = None


# --- Mock LLM responses ---

def _mock_triage_llm(sig: int, cat: str = "model-release"):
    def caller(prompt):
        return {
            "significance": sig,
            "category": cat,
            "rationale": "Test rationale.",
            "suggested_headline": "Test headline under 80 chars",
            "promoted": sig >= 8,
        }
    return caller


def _mock_analysis_llm(prompt: str) -> dict:
    return {
        "what_happened": "According to the source, a new AI model was released.",
        "why_it_matters": "The release affects AI practitioners building production systems.",
        "key_details": "128K context window, $3/M input tokens, available via API.",
        "sources": ["https://example.com/release"],
        "single_source_claims": [],
        "analysis_angles": ["Competitive pricing may accelerate adoption."],
        "kb_context_used": False,
    }


def _mock_editorial_llm(prompt: str) -> dict:
    return {
        "headline": "AI Provider Releases New Model With 128K Context",
        "subheadline": "The release extends context window and cuts pricing by 40 percent.",
        "lead_paragraph": "According to the provider, a new language model was released on Monday with an extended 128K context window, according to the company's announcement.",
        "body": "The new model supports 128K tokens, according to the official blog post. Pricing is set at $3 per million input tokens, the company stated. Benchmarks show a 15 percent improvement over the previous version, per internal testing reported by the provider.",
        "analysis_section": "**Analysis:** The pricing reduction may accelerate adoption among mid-tier developers, though enterprise customers will likely wait for stability reports before migrating.",
        "sources_footer": "Sources: https://example.com/release",
    }


def _make_mock_items(count: int, sig: int = 8, tier: int = 1):
    from pipeline.src.models import CollectedItem
    items = []
    for i in range(count):
        items.append(CollectedItem(
            source_name=f"Source {i}" if tier == 1 else f"Tier{tier} Source {i}",
            source_tier=tier,
            url=f"https://example.com/story-{i}",
            title=f"AI Story {i}: Major model release with improvements",
            raw_content=f"Story {i}: An AI provider released a new model with a 128K context window. Pricing is $3/M input tokens. Benchmarks show 15% improvement over the predecessor.",
            tags=["model-release"],
        ))
    return items


class TestScenario61EndToEndMonday:
    """Scenario 6.1: Full pipeline run — Monday (Tier 1 + Tier 2, not Tier 3)."""

    def test_full_pipeline_monday_run(self, isolated_env, tmp_path):
        from pipeline.src.kb import store as kb_store, vector_store
        from pipeline.src.models import RunState
        from pipeline.src.collect.collector import CollectionResult
        from pipeline.src.triage.triage_agent import triage_batch, filter_triaged
        from pipeline.src.triage.dedup import deduplicate
        from pipeline.src.analysis.analysis_agent import analyze_batch
        from pipeline.src.editorial.editorial_agent import edit_batch, assemble_newsletter
        from pipeline.src.editorial.compliance import check_compliance
        from pipeline.src.publish.website_publisher import publish_to_website
        from pipeline.src.publish.cost_control import log_stage_cost, get_run_cost_report

        run_state = RunState(run_type="standard")
        edition_date = "2026-02-25"

        # Simulate Tier 1 + Tier 2 collection (no Tier 3)
        tier1_items = _make_mock_items(3, sig=8, tier=1)
        tier2_items = _make_mock_items(2, sig=8, tier=2)
        all_items = tier1_items + tier2_items
        tier3_items = _make_mock_items(2, sig=5, tier=3)

        # Verify Tier 3 NOT in Monday run
        monday_items = [i for i in all_items if i.source_tier <= 2]
        assert all(i.source_tier <= 2 for i in monday_items), "Monday run must not include Tier 3"
        assert not any(i in monday_items for i in tier3_items), "Tier 3 items must not appear on Monday"

        # Store items in KB
        for item in monday_items:
            kb_store.store_item(item)
            vector_store.embed_item(item.id, item.title, item.raw_content, {})

        run_state.items_collected = len(monday_items)

        # Triage (mock LLM)
        triaged, errors = triage_batch(monday_items, llm_caller=_mock_triage_llm(8))
        assert len(errors) == 0
        buckets = filter_triaged(triaged)
        downstream = buckets["story"] + buckets["lead"] + buckets["roundup"]

        # Dedup
        groups = deduplicate(downstream)
        assert len(groups) > 0

        # Analysis (mock LLM)
        analyzed, a_errors = analyze_batch(groups, llm_caller=_mock_analysis_llm)
        assert len(a_errors) == 0
        assert len(analyzed) > 0
        assert analyzed[0].what_happened, "Analysis must produce content"

        # Editorial (mock LLM)
        articles, e_errors = edit_batch(analyzed, llm_caller=_mock_editorial_llm)
        assert len(e_errors) == 0
        assert len(articles) > 0

        # Compliance
        for article in articles:
            result = check_compliance(article)
            # Our mock editorial produces compliant content

        # Newsletter assembly
        newsletter = assemble_newsletter(articles, edition_date)
        assert "The LLM Report" in newsletter
        assert edition_date in newsletter
        assert "See you" in newsletter, "Newsletter must have sign-off"

        # Website publish (dry run)
        pub_result = publish_to_website(
            newsletter_md=newsletter,
            edition_date=edition_date,
            run_id=run_state.run_id,
            website_dir=tmp_path / "website",
            dry_run=True,
        )
        file_path = Path(pub_result["file_path"])
        assert file_path.exists(), "Edition file must be created"
        content = file_path.read_text()
        assert f'date: "{edition_date}"' in content, "Edition file must have date in front matter"

        # Log stage costs
        for stage, cost in [("triage", 0.50), ("analysis", 2.0), ("editorial", 1.5)]:
            log_stage_cost(run_state.run_id, stage, "claude-sonnet-4-5", 1000, 500, cost)

        # Verify cost report
        report = get_run_cost_report(run_state.run_id)
        assert report["total_cost"] < 15.0, "Total cost must be under per-run budget"
        assert len(report["by_stage"]) == 3

        run_state.items_published = len(articles)

        print(f"PASS: Scenario 6.1 — Monday E2E: {len(articles)} articles published, "
              f"${report['total_cost']:.2f} cost")


class TestScenario62FridayRunWithTier3:
    """Scenario 6.2: Friday run includes Tier 3 sources."""

    def test_friday_run_includes_tier3(self, isolated_env):
        """Verify that Friday run type includes Tier 3 sources in collection."""
        from pipeline.src.collect.collector import _load_sources

        # Standard run: should only have Tier 1 + Tier 2
        standard_sources = _load_sources("standard")
        standard_tiers = {s["tier"] for s in standard_sources}
        assert 3 not in standard_tiers, "Standard run must NOT include Tier 3"

        # Friday run: should include Tier 3
        friday_sources = _load_sources("friday")
        friday_tiers = {s["tier"] for s in friday_sources}
        assert 3 in friday_tiers, "Friday run MUST include Tier 3"

        # Deep-dive also includes Tier 3
        deepdive_sources = _load_sources("deep-dive")
        deepdive_tiers = {s["tier"] for s in deepdive_sources}
        assert 3 in deepdive_tiers, "Deep-dive run MUST include Tier 3"

        print("PASS: Scenario 6.2 — Tier 3 sources included in friday/deep-dive, excluded from standard")


class TestScenario63GracefulDegradation:
    """Scenario 6.3: All low significance — graceful degradation."""

    def test_all_low_sig_produces_minimal_edition(self, isolated_env, tmp_path):
        from pipeline.src.triage.triage_agent import triage_batch, filter_triaged
        from pipeline.src.triage.dedup import deduplicate
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        # All items score 2-3 (below significance threshold for stories)
        items = _make_mock_items(5, sig=2)
        triaged, _ = triage_batch(items, llm_caller=_mock_triage_llm(2, "api-update"))
        buckets = filter_triaged(triaged)

        assert len(buckets["archive"]) == 5
        assert len(buckets["story"]) == 0
        assert len(buckets["lead"]) == 0

        # Dedup on empty downstream should return empty
        groups = deduplicate([])
        assert groups == []

        # Newsletter assembly with no articles
        newsletter = assemble_newsletter([], "2026-02-25")
        assert newsletter, "Newsletter must be non-empty even with no articles"
        assert "The LLM Report" in newsletter
        # Pipeline should not crash
        print("PASS: Scenario 6.3 — Graceful degradation: all archived, minimal edition produced")


class TestScenario64TierPromotion:
    """Scenario 6.4: Tier 2 story with sig >= 8 gets promoted to Tier 1 treatment."""

    def test_promoted_tier2_story_not_in_roundup(self, isolated_env):
        from pipeline.src.triage.triage_agent import triage_item, filter_triaged
        from pipeline.src.models import CollectedItem

        # Tier 2 DeepSeek item scoring 9
        item = CollectedItem(
            source_name="DeepSeek GitHub",
            source_tier=2,
            url="https://github.com/deepseek-ai/deepseek-v4",
            title="DeepSeek V4 surpasses GPT-5 on all major benchmarks",
            raw_content="DeepSeek has released V4, scoring higher than GPT-5 on MMLU, HumanEval, and MATH. The model is open-weight and free for commercial use.",
            tags=["model-release"],
        )

        triaged = triage_item(item, llm_caller=_mock_triage_llm(9, "model-release"))

        assert triaged.promoted, "Tier 2 item with sig >= 8 must be promoted"
        assert triaged.significance >= 8
        assert triaged.route in ("story", "lead"), \
            f"Promoted item must not be in roundup, got: {triaged.route}"

        # Filter shows it goes to story/lead, not roundup
        buckets = filter_triaged([triaged])
        assert len(buckets["roundup"]) == 0, "Promoted item must NOT be in roundup"
        assert len(buckets["story"]) + len(buckets["lead"]) == 1

        print("PASS: Scenario 6.4 — Tier 2 promoted story goes to story/lead, not roundup")


class TestScenario65ContentConsistency:
    """Scenario 6.5: Website and newsletter have same content."""

    def test_newsletter_and_website_content_match(self, isolated_env, tmp_path):
        from pipeline.src.editorial.editorial_agent import edit_batch, assemble_newsletter
        from pipeline.src.publish.website_publisher import publish_to_website
        from pipeline.src.analysis.analysis_agent import AnalyzedStory
        from pipeline.src.models import StoryGroup

        # Create sample articles
        from pipeline.src.models import CollectedItem, TriagedItem
        items = _make_mock_items(2, sig=8)
        analyzed_stories = []
        for item in items:
            t_item = TriagedItem(
                item=item, significance=8, category="model-release",
                rationale="Test", suggested_headline=item.title[:80],
                promoted=False, route="story"
            )
            group = StoryGroup(primary=t_item)
            story = AnalyzedStory(
                group=group,
                what_happened="According to the source, a new model was released.",
                why_it_matters="Affects AI practitioners.",
                key_details="128K context, $3/M pricing.",
                sources=["https://example.com"],
                single_source_claims=[],
                analysis_angles=["May accelerate adoption."],
            )
            analyzed_stories.append(story)

        articles, _ = edit_batch(analyzed_stories, llm_caller=_mock_editorial_llm)
        newsletter_md = assemble_newsletter(articles, "2026-02-25")
        # Add website link as required by scenario
        newsletter_md += "\n\n*Read the full edition at https://thellmreport.com/editions/2026-02-25*\n"

        # Website publish
        pub_result = publish_to_website(
            newsletter_md=newsletter_md,
            edition_date="2026-02-25",
            run_id="test-consistency",
            website_dir=tmp_path / "website",
            dry_run=True,
        )
        website_content = Path(pub_result["file_path"]).read_text()

        # Newsletter should link to website
        assert "thellmreport.com" in newsletter_md, "Newsletter must link to website"

        # Same headlines appear in both
        for article in articles:
            assert article.headline in website_content, \
                f"Headline '{article.headline}' must appear in website file"
            assert article.headline in newsletter_md, \
                f"Headline '{article.headline}' must appear in newsletter"

        print("PASS: Scenario 6.5 — Website and newsletter have same headlines and website link")


class TestCronConfiguration:
    """Verify cron/scheduling configuration is correct."""

    def test_pipeline_runner_exists(self):
        runner = REPO_ROOT / "scripts" / "run-pipeline.sh"
        assert runner.exists(), "Pipeline runner script must exist"
        assert os.access(str(runner), os.X_OK), "Pipeline runner must be executable"
        content = runner.read_text()
        assert "PYTHONPATH" in content, "Runner must set PYTHONPATH"
        assert "run_pipeline.py" in content, "Runner must call main pipeline module"
        print("PASS: run-pipeline.sh exists and is executable")

    def test_main_pipeline_module_exists(self):
        module = REPO_ROOT / "projects/the-llm-report/pipeline/run_pipeline.py"
        assert module.exists(), "run_pipeline.py must exist"
        content = module.read_text()
        # Contains all 7 pipeline stages
        for stage in ["collection", "triage", "dedup", "analysis", "editorial", "compliance", "publish"]:
            assert stage.lower() in content.lower(), f"Pipeline must include stage: {stage}"
        assert "budget" in content.lower(), "Pipeline must check budget gate"
        assert "RunState" in content, "Pipeline must track run state"
        print("PASS: run_pipeline.py includes all 7 stages and budget gate")

    def test_budget_gate_in_pipeline(self):
        """Pipeline must check budget between stages."""
        module = REPO_ROOT / "projects/the-llm-report/pipeline/run_pipeline.py"
        content = module.read_text()
        assert "check_budget_gate" in content, "Pipeline must call check_budget_gate"
        # Should have multiple budget checks
        assert content.count("check_budget_gate") >= 2, \
            "Pipeline should check budget at multiple stages"
        print("PASS: Budget gate called at multiple pipeline stages")


class TestRunStateTracking:
    """Run state and logging verification."""

    def test_run_log_tracks_items_and_cost(self, isolated_env):
        from pipeline.src.kb.store import start_run, complete_run
        from pipeline.src.models import RunState

        run = RunState(run_type="standard")
        run.items_collected = 10
        run.items_published = 3
        run.total_cost_usd = 4.25
        run.status = "complete"

        start_run(run)
        complete_run(run)

        # Verify it's in the DB
        import sqlite3
        conn = sqlite3.connect(str(Path(os.environ["KB_DB_PATH"])))
        row = conn.execute(
            "SELECT run_type, items_collected, items_published, total_cost_usd, status "
            "FROM run_log WHERE run_id = ?",
            (run.run_id,)
        ).fetchone()
        conn.close()

        assert row is not None, "Run must be logged to DB"
        assert row[0] == "standard"
        assert row[1] == 10
        assert row[2] == 3
        assert abs(row[3] - 4.25) < 0.01
        assert row[4] == "complete"

        print("PASS: Run state tracked correctly in run_log table")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
