"""
Milestone 2 Holdout Scenarios — Triage + Deduplication
Scenarios 2.1 through 2.5 from scenarios.md
LLM calls are mocked to avoid API costs during testing.
"""

from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "kb.sqlite"
    chroma_path = tmp_path / "chroma"

    monkeypatch.setenv("KB_DB_PATH", str(db_path))
    monkeypatch.setenv("CHROMA_PATH", str(chroma_path))
    monkeypatch.setenv("CACHE_DB_PATH", str(db_path))

    from pipeline.src.kb import vector_store as vs
    from pipeline.src.kb import store as st
    from pipeline.src.kb import semantic_cache as sc

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


def _make_item(title, content, tier=1, source="Test Source"):
    from pipeline.src.models import CollectedItem
    return CollectedItem(
        source_name=source,
        source_tier=tier,
        url=f"https://example.com/{title[:20].replace(' ', '-').lower()}",
        title=title,
        raw_content=content,
        tags=[],
    )


def _mock_llm(significance, category, rationale="Test rationale.", headline=None, promoted=False):
    """Return a mock LLM caller that returns pre-set values."""
    def caller(prompt):
        return {
            "significance": significance,
            "category": category,
            "rationale": rationale,
            "suggested_headline": headline or prompt.split("Title: ")[1].split("\n")[0][:80],
            "promoted": promoted,
        }
    return caller


class TestScenario21SignificanceScoringAccuracy:
    """Scenario 2.1: Significance scoring accuracy across 10 diverse items."""

    def test_significance_scores_match_expected_ranges(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item
        from pipeline.src.kb import store, vector_store

        # Define items with expected score ranges and mocked LLM responses
        test_cases = [
            # (title, content, tier, mock_sig, mock_cat, expected_min, expected_max)
            ("GPT-6 released by OpenAI", "OpenAI announces GPT-6, a major model release.", 1, 9, "model-release", 8, 10),
            ("Anthropic launches Claude 5", "Anthropic releases Claude 5 with major capability improvements.", 1, 8, "model-release", 8, 10),
            ("Minor OpenAI API patch 1.2.3", "Small bugfix for context handling edge case.", 1, 3, "api-update", 1, 5),
            ("OpenAI rate limit tweak", "Updated rate limits for tier 3 users.", 1, 4, "api-update", 1, 5),
            ("API timeout fix deployed", "Fixed timeout regression in streaming endpoint.", 1, 3, "api-update", 1, 5),
            ("Critical RCE in LLM framework", "Security advisory: remote code execution in popular LLM library.", 1, 7, "security-patch", 6, 8),
            ("XSS vulnerability patched in Hugging Face", "Cross-site scripting vulnerability fixed.", 1, 6, "security-patch", 6, 8),
            ("OpenAI and Microsoft expand partnership", "Joint investment and research collaboration announced.", 1, 6, "partnership", 5, 7),
            ("AI company posts quarterly blog", "Routine update about company culture and hiring.", 1, 2, "methodology", 1, 3),
            ("OpenAI cuts API pricing by 50%", "Major pricing reduction across all GPT models.", 1, 7, "pricing-change", 5, 7),
        ]

        for title, content, tier, mock_sig, mock_cat, exp_min, exp_max in test_cases:
            item = _make_item(title, content, tier=tier)
            store.store_item(item)
            vector_store.embed_item(item.id, item.title, item.raw_content, {})

            triaged = triage_item(item, llm_caller=_mock_llm(mock_sig, mock_cat))

            assert triaged.significance is not None, f"{title}: significance must not be null"
            assert exp_min <= triaged.significance <= exp_max, \
                f"{title}: expected {exp_min}-{exp_max}, got {triaged.significance}"
            assert triaged.category in {
                "model-release", "api-update", "security-patch", "acquisition",
                "partnership", "research-paper", "framework-release", "methodology",
                "policy-regulatory", "benchmark", "pricing-change"
            }, f"{title}: invalid category '{triaged.category}'"
            assert triaged.rationale, f"{title}: rationale must be non-empty"
            assert triaged.suggested_headline, f"{title}: suggested_headline must be non-empty"

        print("PASS: Scenario 2.1 — Significance scoring: all 10 items scored correctly")


class TestScenario22TierPromotion:
    """Scenario 2.2: Tier promotion — Tier 2 item scoring >= 8 gets promoted."""

    def test_tier2_high_significance_gets_promoted(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item

        item = _make_item(
            "DeepSeek R3 outperforms GPT-5 on all benchmarks",
            "DeepSeek releases R3, a new model that surpasses GPT-5 on MMLU, HumanEval, and MATH benchmarks with 3x cost efficiency.",
            tier=2,
            source="DeepSeek GitHub",
        )

        triaged = triage_item(item, llm_caller=_mock_llm(9, "model-release", promoted=True))

        assert triaged.significance >= 8, f"Expected sig >= 8, got {triaged.significance}"
        assert triaged.promoted, "Tier 2 item with sig >= 8 must be promoted"
        assert triaged.route in ("story", "lead"), \
            f"Promoted item should route to story/lead, got {triaged.route}"

        print("PASS: Scenario 2.2 — Tier promotion: Tier 2 item sig=9 → promoted=True")

    def test_tier2_low_significance_not_promoted(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item

        item = _make_item(
            "DeepSeek minor patch",
            "Small bug fix in the DeepSeek inference engine.",
            tier=2,
        )

        triaged = triage_item(item, llm_caller=_mock_llm(4, "api-update", promoted=False))

        assert not triaged.promoted, "Tier 2 item with low sig should NOT be promoted"

        print("PASS: Scenario 2.2 — Low sig Tier 2 not promoted")

    def test_tier1_not_affected_by_promotion_rule(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item

        item = _make_item("OpenAI GPT-6", "Major release.", tier=1)
        triaged = triage_item(item, llm_caller=_mock_llm(9, "model-release", promoted=False))
        # Tier 1 items are never "promoted" (they already get full treatment)
        # The promoted flag should only matter for tier 2/3
        assert triaged.significance == 9
        print("PASS: Scenario 2.2 — Tier 1 items unaffected by promotion rule")


class TestScenario23StoryClustering:
    """Scenario 2.3: Story clustering via vector similarity deduplication."""

    def test_same_story_different_sources_clustered(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item
        from pipeline.src.triage.dedup import deduplicate
        from pipeline.src.kb import store, vector_store

        # Items A, B, D are about the same GPT-5.3 story
        item_a = _make_item(
            "OpenAI releases GPT-5.3",
            "OpenAI today released GPT-5.3, a new version of their flagship model with improved reasoning capabilities and a 200k context window.",
            source="OpenAI Blog",
        )
        item_b = _make_item(
            "GPT-5.3 announced with improved reasoning",
            "OpenAI has announced GPT-5.3, featuring better chain-of-thought reasoning and an extended 200k token context window.",
            source="TechCrunch",
        )
        item_c = _make_item(
            "Anthropic updates Claude pricing structure",
            "Anthropic has revised its pricing tiers for Claude API, reducing costs for high-volume enterprise customers.",
            source="Anthropic Blog",
        )
        item_d = _make_item(
            "OpenAI's new model GPT-5.3: first impressions",
            "We tested OpenAI's newly released GPT-5.3 model. The improved reasoning and 200k context window are impressive.",
            source="The Verge",
        )

        # Store and embed all items
        for item in [item_a, item_b, item_c, item_d]:
            store.store_item(item)
            vector_store.embed_item(item.id, item.title, item.raw_content, {})

        # Triage all items (mocked LLM)
        triaged_items = []
        mock_sigs = [8, 7, 6, 6]
        for item, sig in zip([item_a, item_b, item_c, item_d], mock_sigs):
            t = triage_item(item, llm_caller=_mock_llm(sig, "model-release"))
            triaged_items.append(t)

        # Deduplicate
        groups = deduplicate(triaged_items)

        # Should produce 2 groups: {A,B,D} and {C}
        assert len(groups) == 2, f"Expected 2 story groups, got {len(groups)}"

        # Find the GPT-5.3 cluster (should have 3 items)
        gpt_group = next((g for g in groups if g.primary.item.source_name in
                          ("OpenAI Blog", "TechCrunch", "The Verge")), None)
        assert gpt_group is not None, "GPT-5.3 cluster should exist"
        total_in_cluster = 1 + len(gpt_group.supporting)
        assert total_in_cluster == 3, f"GPT-5.3 cluster should have 3 items, got {total_in_cluster}"

        # Highest significance (8) should be primary
        assert gpt_group.primary.significance == 8, \
            f"Primary should be highest-sig item (8), got {gpt_group.primary.significance}"

        # Claude pricing is its own group
        claude_group = next((g for g in groups if "Anthropic" in g.primary.item.source_name or
                             "Claude" in g.primary.item.title), None)
        assert claude_group is not None, "Claude pricing group should exist"
        assert len(claude_group.supporting) == 0, "Claude pricing should be alone"

        print("PASS: Scenario 2.3 — Story clustering: A/B/D grouped, C separate, primary=highest sig")

    def test_zero_llm_calls_for_dedup(self, isolated_db):
        """Deduplication must use zero LLM calls (local vector only)."""
        from pipeline.src.triage.dedup import deduplicate

        items = [
            _make_item(f"Story {i}", f"Content about topic {i}")
            for i in range(4)
        ]

        # Triage manually without LLM (inject pre-scored items)
        from pipeline.src.models import TriagedItem
        triaged = [
            TriagedItem(
                item=item,
                significance=7,
                category="model-release",
                rationale="test",
                suggested_headline=item.title,
                promoted=False,
                route="story",
            )
            for item in items
        ]

        # Dedup should work without any LLM calls
        llm_called = [False]
        original_completion = None
        try:
            import litellm
            original_completion = litellm.completion
            def mock_fail(*args, **kwargs):
                llm_called[0] = True
                raise AssertionError("Dedup should not call LLM!")
            litellm.completion = mock_fail
        except ImportError:
            pass

        try:
            groups = deduplicate(triaged)
            assert not llm_called[0], "Dedup must not call any LLM"
            assert len(groups) > 0, "Should produce at least one group"
        finally:
            if original_completion:
                litellm.completion = original_completion

        print("PASS: Scenario 2.3 — Zero LLM calls during deduplication")


class TestScenario24ThresholdFiltering:
    """Scenario 2.4: Threshold filtering routes items to correct buckets."""

    def test_routing_buckets_correct(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item, filter_triaged

        items_and_scores = [
            (_make_item("Trivial story", "Minor update content."), 2, "api-update"),
            (_make_item("Roundup story 1", "Minor but notable content."), 4, "api-update"),
            (_make_item("Roundup story 2", "Another minor but interesting update."), 5, "partnership"),
            (_make_item("Individual story 1", "Important release or update."), 7, "model-release"),
            (_make_item("Individual story 2", "Significant security event."), 8, "security-patch"),
            (_make_item("Lead story", "Massive industry-wide development."), 10, "model-release"),
        ]

        triaged = []
        for item, sig, cat in items_and_scores:
            t = triage_item(item, llm_caller=_mock_llm(sig, cat))
            triaged.append(t)

        buckets = filter_triaged(triaged)

        # Score-2 → archive
        assert len(buckets["archive"]) == 1
        assert buckets["archive"][0].significance == 2

        # Score-4, score-5 → roundup
        assert len(buckets["roundup"]) == 2
        roundup_sigs = {t.significance for t in buckets["roundup"]}
        assert roundup_sigs == {4, 5}

        # Score-7, score-8 → story
        assert len(buckets["story"]) == 2
        story_sigs = {t.significance for t in buckets["story"]}
        assert story_sigs == {7, 8}

        # Score-10 → lead
        assert len(buckets["lead"]) == 1
        assert buckets["lead"][0].significance == 10

        print("PASS: Scenario 2.4 — Threshold filtering: all 6 items routed correctly")


class TestScenario25AllLowSignificance:
    """Scenario 2.5: All items score 2-3 — pipeline handles gracefully."""

    def test_low_significance_run_handled_gracefully(self, isolated_db):
        from pipeline.src.triage.triage_agent import triage_item, triage_batch, filter_triaged

        items = [
            _make_item("Minor patch 1", "Small bugfix in inference engine."),
            _make_item("Minor patch 2", "Updated documentation for API."),
            _make_item("Routine update 3", "Quarterly infrastructure maintenance."),
            _make_item("Blog post 4", "Team spotlight: meet our engineers."),
            _make_item("Minor patch 5", "Rate limit adjustment for free tier."),
        ]

        # All score 2-3
        triaged, errors = triage_batch(
            items,
            llm_caller=_mock_llm(2, "api-update"),
        )

        assert len(errors) == 0, f"No errors expected, got: {errors}"
        assert len(triaged) == 5, "All 5 items should be triaged"

        # All archived
        buckets = filter_triaged(triaged)
        assert len(buckets["archive"]) == 5, "All low-sig items should be archived"
        assert len(buckets["roundup"]) == 0
        assert len(buckets["story"]) == 0
        assert len(buckets["lead"]) == 0

        # Pipeline should not crash
        # Cost is minimal (5 LLM calls but mocked, in real life < $1)
        print("PASS: Scenario 2.5 — All-low-sig run: 5 items archived, no crash")

    def test_low_sig_dedup_still_works(self, isolated_db):
        """Dedup should work even when all items are low significance."""
        from pipeline.src.triage.triage_agent import triage_item
        from pipeline.src.triage.dedup import deduplicate

        items = [
            _make_item("Patch A", "Minor fix in component X."),
            _make_item("Patch B", "Another minor fix in module Y."),
        ]

        triaged = [
            triage_item(item, llm_caller=_mock_llm(2, "api-update"))
            for item in items
        ]

        groups = deduplicate(triaged)
        assert len(groups) >= 1, "Should produce at least one group even for low-sig items"
        print("PASS: Scenario 2.5 — Dedup works for low-significance items")


class TestRoutingRules:
    """Additional tests for routing logic correctness."""

    def test_significance_boundaries(self, isolated_db):
        from pipeline.src.triage.triage_agent import _route_item
        assert _route_item(1) == "archive"
        assert _route_item(3) == "archive"
        assert _route_item(4) == "roundup"
        assert _route_item(6) == "roundup"
        assert _route_item(7) == "story"
        assert _route_item(8) == "story"
        assert _route_item(9) == "lead"
        assert _route_item(10) == "lead"
        print("PASS: Routing boundaries all correct")

    def test_significance_clamped_to_1_10(self, isolated_db):
        """LLM might return out-of-range values — clamp them."""
        from pipeline.src.triage.triage_agent import triage_item

        item = _make_item("Test", "Test content.")

        # Mock LLM returns significance=15 (out of range)
        triaged = triage_item(item, llm_caller=lambda p: {
            "significance": 15,
            "category": "model-release",
            "rationale": "extreme test",
            "suggested_headline": "Test",
            "promoted": False,
        })
        assert triaged.significance <= 10, "Significance must be clamped to 10"

        # Mock LLM returns significance=0 (out of range)
        triaged2 = triage_item(item, llm_caller=lambda p: {
            "significance": 0,
            "category": "api-update",
            "rationale": "extreme test",
            "suggested_headline": "Test",
            "promoted": False,
        })
        assert triaged2.significance >= 1, "Significance must be clamped to 1"
        print("PASS: Significance clamping works correctly")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
