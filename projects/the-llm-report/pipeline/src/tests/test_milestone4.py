"""
Milestone 4 Holdout Scenarios — Editorial + Compliance Pipeline
Scenarios 4.1 through 4.5 from scenarios.md
LLM calls are mocked to avoid API costs during testing.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Isolated SQLite and ChromaDB for each test."""
    db_path = tmp_path / "kb.sqlite"
    chroma_path = tmp_path / "chroma"
    monkeypatch.setenv("KB_DB_PATH", str(db_path))
    monkeypatch.setenv("CHROMA_PATH", str(chroma_path))
    monkeypatch.setenv("CACHE_DB_PATH", str(db_path))

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collected(title, content, source="Test Source", tier=1, url=None):
    from pipeline.src.models import CollectedItem
    return CollectedItem(
        source_name=source,
        source_tier=tier,
        url=url or f"https://example.com/{title[:20].replace(' ', '-').lower()}",
        title=title,
        raw_content=content,
        tags=[],
    )


def _make_triaged(title, content, source="Test Source", tier=1, sig=7):
    from pipeline.src.models import TriagedItem
    item = _make_collected(title, content, source=source, tier=tier)
    return TriagedItem(
        item=item,
        significance=sig,
        category="model-release",
        rationale="test",
        suggested_headline=title[:80],
        promoted=False,
        route="story",
    )


def _make_analyzed_story(
    title="Test Story",
    content="Test content about AI developments.",
    significance=8,
    analysis_angles=None,
    single_source_claims=None,
    sources=None,
):
    from pipeline.src.models import CollectedItem, TriagedItem, StoryGroup, AnalyzedStory
    item = CollectedItem(
        source_name="Test Source",
        source_tier=1,
        url="https://example.com/test",
        title=title,
        raw_content=content,
        tags=[],
    )
    triaged = TriagedItem(
        item=item,
        significance=significance,
        category="model-release",
        rationale="test",
        suggested_headline=title[:80],
        promoted=False,
        route="story",
    )
    group = StoryGroup(primary=triaged)
    return AnalyzedStory(
        group=group,
        what_happened=f"{title} — summary.",
        why_it_matters="Significant for AI practitioners.",
        key_details="Key fact: version 2.0.",
        sources=sources or ["https://example.com/test"],
        single_source_claims=single_source_claims or [],
        analysis_angles=analysis_angles or [],
        kb_context_used=False,
        llm_call_made=True,
        analysis_cost_usd=0.001,
    )


def _make_llm_caller(
    headline="AI Model Released With New Capabilities",
    subheadline="The release marks a notable update to the AI ecosystem.",
    lead_paragraph="A major AI provider released a new model on Wednesday, according to the company.",
    body="The model demonstrates improved capabilities across multiple benchmarks, according to the provider. Independent researchers confirmed the results match the announced specifications.",
    analysis_section=None,
    sources_footer="Sources: https://example.com/test",
):
    """Return a mock LLM caller that returns a clean, compliant article."""
    def caller(prompt):
        return {
            "headline": headline,
            "subheadline": subheadline,
            "lead_paragraph": lead_paragraph,
            "body": body,
            "analysis_section": analysis_section,
            "sources_footer": sources_footer,
        }
    return caller


# ---------------------------------------------------------------------------
# Scenario 4.1 — Journalist Voice: No First Person, No Promo, No Emoji, No Bullets
# ---------------------------------------------------------------------------

class TestScenario41JournalistVoice:
    """Scenario 4.1: Editorial agent produces journalist-quality voice."""

    def test_clean_article_passes_compliance(self, isolated_db):
        """Mock LLM returns clean article — compliance check passes."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=8)
        clean_caller = _make_llm_caller(
            headline="OpenAI Releases New Language Model",
            lead_paragraph="OpenAI released a new language model on Tuesday, according to the company's blog post.",
            body=(
                "The model demonstrates improved reasoning capabilities, "
                "according to OpenAI. Benchmark results show a 15% improvement "
                "over the previous version, the company stated. "
                "Third-party researchers confirmed the results."
            ),
            analysis_section=None,
        )

        article = edit_article(story, llm_caller=clean_caller)
        result = check_compliance(article)

        assert result.passed, f"Clean article should pass compliance. Failures: {result.failures}"
        assert len(result.failures) == 0
        print("PASS: Scenario 4.1 — Clean article passes all compliance checks")

    def test_first_person_fails_compliance(self, isolated_db):
        """Article with first-person language fails compliance."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=7)
        bad_caller = _make_llm_caller(
            headline="We Think AI Is Changing Everything",
            lead_paragraph="I believe this new model changes the landscape of AI. We think it is remarkable.",
            body="Our analysis shows the model is amazing and revolutionary.",
        )

        article = edit_article(story, llm_caller=bad_caller)
        result = check_compliance(article)

        assert not result.passed, "Article with first person should fail compliance"
        # Should detect first-person violations
        failure_text = " ".join(result.failures).lower()
        assert "first person" in failure_text or "i" in failure_text or "we" in failure_text or "our" in failure_text, \
            f"Expected first-person failure. Got: {result.failures}"
        print("PASS: Scenario 4.1b — First-person article correctly fails compliance")

    def test_promo_language_fails_compliance(self, isolated_db):
        """Article with promotional language fails compliance."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=7)
        promo_caller = _make_llm_caller(
            headline="AI Model Released",
            lead_paragraph="A new model was released on Monday.",
            body=(
                "The model is revolutionary and game-changing for the industry. "
                "The unprecedented performance is amazing and exciting to researchers."
            ),
        )

        article = edit_article(story, llm_caller=promo_caller)
        result = check_compliance(article)

        assert not result.passed, "Article with promotional language should fail"
        assert len(result.promotional_phrases) > 0, "Promotional phrases must be listed"
        print("PASS: Scenario 4.1c — Promotional language correctly fails compliance")

    def test_no_bullet_points_in_body(self, isolated_db):
        """Article with bullet points in body fails compliance."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=7)
        bullet_caller = _make_llm_caller(
            headline="AI Update Released",
            lead_paragraph="An AI update was released on Thursday.",
            body="Key improvements include:\n- Faster inference\n- Better accuracy\n* Lower cost",
        )

        article = edit_article(story, llm_caller=bullet_caller)
        result = check_compliance(article)

        assert not result.passed, "Article with bullet points should fail compliance"
        failure_text = " ".join(result.failures).lower()
        assert "bullet" in failure_text, f"Expected bullet point failure. Got: {result.failures}"
        print("PASS: Scenario 4.1d — Bullet points correctly fail compliance")

    def test_emoji_fails_compliance(self, isolated_db):
        """Article with emoji fails compliance."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=7)
        emoji_caller = _make_llm_caller(
            headline="AI Model Released",
            lead_paragraph="A new model was released \U0001F680 on Monday.",
            body="Performance improved by 15% according to the provider.",
        )

        article = edit_article(story, llm_caller=emoji_caller)
        result = check_compliance(article)

        assert not result.passed, "Article with emoji should fail compliance"
        failure_text = " ".join(result.failures).lower()
        assert "emoji" in failure_text, f"Expected emoji failure. Got: {result.failures}"
        print("PASS: Scenario 4.1e — Emoji correctly fails compliance")


# ---------------------------------------------------------------------------
# Scenario 4.2 — Copyright Quote Limits
# ---------------------------------------------------------------------------

class TestScenario42CopyrightQuotes:
    """Scenario 4.2: Quote under 14 words passes; over 14 words fails."""

    def test_short_ceo_quote_passes(self, isolated_db):
        """A CEO quote under 14 words passes compliance."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=7)
        # Quote: "We are committed to safety" — 5 words
        short_quote_caller = _make_llm_caller(
            headline="CEO Addresses AI Safety Commitments",
            lead_paragraph=(
                'The CEO stated "We are committed to safety" during the conference, '
                "according to the company."
            ),
            body=(
                "The executive outlined three safety principles at the event, "
                "according to a company spokesperson."
            ),
        )

        article = edit_article(story, llm_caller=short_quote_caller)
        result = check_compliance(article)

        assert result.passed, f"Short quote should pass compliance. Failures: {result.failures}"
        assert len(result.long_quotes) == 0, f"No long quotes expected. Got: {result.long_quotes}"
        print("PASS: Scenario 4.2 — Short CEO quote (<14 words) passes compliance")

    def test_long_quote_fails(self, isolated_db):
        """A direct quote over 14 words fails compliance."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance

        story = _make_analyzed_story(significance=7)
        # 20-word quote
        long_quote_caller = _make_llm_caller(
            headline="AI Company Announces Strategy",
            lead_paragraph=(
                'The CEO stated "We are fully committed to building the safest and most capable '
                'AI systems that the world has ever seen at this scale" at the annual conference.'
            ),
            body="The company plans to release further updates this quarter, according to reports.",
        )

        article = edit_article(story, llm_caller=long_quote_caller)
        result = check_compliance(article)

        assert not result.passed, "Article with 20-word quote should fail compliance"
        assert len(result.long_quotes) > 0, "Long quotes should be listed"
        print("PASS: Scenario 4.2b — Long quote (>14 words) fails compliance")


# ---------------------------------------------------------------------------
# Scenario 4.3 — Compliance Rejection and Rewrite
# ---------------------------------------------------------------------------

class TestScenario43ComplianceRewrite:
    """Scenario 4.3: Rewrite loop fixes violations within max_loops."""

    def test_rewrite_loop_fixes_violations(self, isolated_db):
        """First call returns bad article; second fixes it. Loop terminates at attempt 2."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import check_compliance, rewrite_loop

        story = _make_analyzed_story(significance=7)

        # First editorial call returns bad article (20-word quote + promo phrase)
        bad_body = (
            'The CEO stated "We believe this model is the most advanced and capable system '
            'our team has ever developed in our history" at the conference. '
            "The revolutionary update changes everything for AI practitioners."
        )
        good_body = (
            "The model demonstrates improved capabilities across multiple benchmarks, "
            "according to the provider. Independent researchers confirmed the results."
        )

        call_count = [0]

        def counted_caller(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "headline": "AI Model Released",
                    "subheadline": "New model shows capability improvements.",
                    "lead_paragraph": "A new model was released on Monday, according to the company.",
                    "body": bad_body,
                    "analysis_section": None,
                    "sources_footer": "Sources: https://example.com/test",
                }
            else:
                return {
                    "headline": "AI Model Released",
                    "subheadline": "New model shows capability improvements.",
                    "lead_paragraph": "A new model was released on Monday, according to the company.",
                    "body": good_body,
                    "analysis_section": None,
                    "sources_footer": "Sources: https://example.com/test",
                }

        # First article — should fail compliance
        bad_article = edit_article(story, llm_caller=counted_caller)
        first_check = check_compliance(bad_article)
        assert not first_check.passed, "First article should fail compliance"
        assert len(first_check.long_quotes) > 0 or len(first_check.promotional_phrases) > 0, \
            "Should detect long quote or promo phrase"

        # Run rewrite loop starting from bad article
        def llm_rewriter(article, failures):
            return edit_article(story, llm_caller=counted_caller)

        final_article, final_result, loops_used = rewrite_loop(
            bad_article, llm_rewriter, max_loops=3
        )

        assert final_result.passed, f"Rewritten article should pass. Failures: {final_result.failures}"
        assert loops_used <= 3, f"Should not exceed max_loops. Used: {loops_used}"
        print(f"PASS: Scenario 4.3 — Compliance rewrite loop fixed violations in {loops_used} attempt(s)")

    def test_rewrite_loop_respects_max_loops(self, isolated_db):
        """Rewrite loop stops at max_loops even if still failing."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.editorial.compliance import rewrite_loop

        story = _make_analyzed_story(significance=7)
        # Always return bad article
        always_bad = _make_llm_caller(
            body="The revolutionary, game-changing model is amazing and exciting to everyone.",
        )
        bad_article = edit_article(story, llm_caller=always_bad)

        call_count = [0]
        def always_bad_rewriter(article, failures):
            call_count[0] += 1
            return edit_article(story, llm_caller=always_bad)

        _, final_result, loops_used = rewrite_loop(bad_article, always_bad_rewriter, max_loops=2)

        assert loops_used <= 2, f"Should not exceed max_loops=2. Got: {loops_used}"
        assert not final_result.passed, "Should still be failing after max loops"
        print(f"PASS: Scenario 4.3b — Rewrite loop respects max_loops={2}, stopped at {loops_used}")


# ---------------------------------------------------------------------------
# Scenario 4.4 — Analysis Section Placement
# ---------------------------------------------------------------------------

class TestScenario44AnalysisSection:
    """Scenario 4.4: High-significance story has Analysis section after body."""

    def test_high_sig_analysis_label_present(self, isolated_db):
        """Story with significance>=7 and analysis_angles produces Analysis section."""
        from pipeline.src.editorial.editorial_agent import edit_article

        story = _make_analyzed_story(
            significance=9,
            analysis_angles=[
                "This development may accelerate enterprise adoption of multimodal AI.",
                "Pricing adjustments could pressure competitors to respond.",
            ],
        )

        analysis_caller = _make_llm_caller(
            headline="Major AI Provider Releases Flagship Model",
            lead_paragraph=(
                "A major AI provider released its flagship model on Thursday, "
                "according to a company announcement."
            ),
            body=(
                "The model achieves state-of-the-art results on several benchmarks, "
                "according to the company. Pricing was set at $15 per million output tokens, "
                "the provider stated."
            ),
            analysis_section=(
                "**Analysis:** The release may accelerate enterprise adoption of multimodal AI "
                "as providers compete on capability. Pricing adjustments could pressure competitors "
                "to respond with their own pricing reductions, analysts suggest."
            ),
        )

        article = edit_article(story, llm_caller=analysis_caller)

        assert article.analysis_section is not None, "Analysis section must be present for high-significance story"
        assert "**Analysis:**" in article.analysis_section, \
            f"Analysis section must start with '**Analysis:**'. Got: {article.analysis_section[:80]}"
        print("PASS: Scenario 4.4 — Analysis section present with '**Analysis:**' label")

    def test_analysis_uses_qualified_language(self, isolated_db):
        """Analysis section must use 'may' or 'could', not definitive 'will'."""
        from pipeline.src.editorial.editorial_agent import edit_article

        story = _make_analyzed_story(
            significance=8,
            analysis_angles=["Market shift may follow this announcement."],
        )

        qualified_caller = _make_llm_caller(
            headline="AI Company Announces Major Partnership",
            lead_paragraph="An AI company announced a major partnership on Wednesday, according to sources.",
            body="The partnership covers joint model development, the companies stated.",
            analysis_section=(
                "**Analysis:** The partnership may signal a shift in how AI companies approach "
                "enterprise customers. This could reduce development costs for both parties, "
                "according to industry analysts."
            ),
        )

        article = edit_article(story, llm_caller=qualified_caller)

        assert article.analysis_section is not None
        analysis_text = article.analysis_section.lower()
        has_qualified = "may" in analysis_text or "could" in analysis_text or "suggests" in analysis_text
        assert has_qualified, \
            f"Analysis must use qualified language (may/could/suggests). Got: {article.analysis_section}"
        print("PASS: Scenario 4.4b — Analysis uses qualified language (may/could)")

    def test_low_sig_no_analysis_section(self, isolated_db):
        """Story with significance < 7 should not have analysis section."""
        from pipeline.src.editorial.editorial_agent import edit_article

        # significance=5, no analysis_angles
        story = _make_analyzed_story(significance=5, analysis_angles=[])

        no_analysis_caller = _make_llm_caller(
            headline="Minor AI Update Released",
            lead_paragraph="A minor AI update was released on Friday.",
            body="The update improves stability, according to the release notes.",
            analysis_section="**Analysis:** This will dominate the market.",
        )

        article = edit_article(story, llm_caller=no_analysis_caller)

        # Even if LLM returns analysis, agent should suppress it for low-significance
        assert article.analysis_section is None, \
            f"Low-significance story should have no analysis section. Got: {article.analysis_section}"
        print("PASS: Scenario 4.4c — Low-significance story correctly has no analysis section")

    def test_analysis_after_body_in_newsletter(self, isolated_db):
        """In assembled newsletter, analysis section appears after body."""
        from pipeline.src.editorial.editorial_agent import edit_article, assemble_newsletter

        story = _make_analyzed_story(significance=9, analysis_angles=["May reshape the market."])

        caller = _make_llm_caller(
            headline="Flagship Model Released",
            lead_paragraph="The company released its flagship model on Tuesday.",
            body="The model achieves strong results, according to the company.",
            analysis_section="**Analysis:** This may reshape the competitive landscape.",
        )

        article = edit_article(story, llm_caller=caller)
        newsletter = assemble_newsletter([article], "2026-02-25")

        body_pos = newsletter.find(article.body[:20])
        analysis_pos = newsletter.find("**Analysis:**")

        assert body_pos != -1, "Body must appear in newsletter"
        assert analysis_pos != -1, "Analysis must appear in newsletter"
        assert analysis_pos > body_pos, \
            "Analysis section must appear after body in newsletter"
        print("PASS: Scenario 4.4d — Analysis section appears after body in newsletter")


# ---------------------------------------------------------------------------
# Scenario 4.5 — Newsletter Assembly
# ---------------------------------------------------------------------------

class TestScenario45NewsletterAssembly:
    """Scenario 4.5: Newsletter assembles with correct structure."""

    def _build_articles(self):
        """Build 8 test articles: 1 lead (sig=10), 2 standard (sig=7-8), 5 roundup (sig=4-6)."""
        from pipeline.src.editorial.editorial_agent import edit_article
        from pipeline.src.models import EditedArticle

        articles = []

        # Lead story (sig=10)
        lead_story = _make_analyzed_story(
            title="OpenAI Releases GPT-6 With Breakthrough Reasoning",
            significance=10,
            analysis_angles=["May accelerate AGI timeline debates."],
        )
        lead_caller = _make_llm_caller(
            headline="OpenAI Releases GPT-6 With Breakthrough Reasoning",
            lead_paragraph=(
                "OpenAI released GPT-6 on Monday, claiming a major advance in reasoning, "
                "according to the company."
            ),
            body=(
                "The model achieves 95% accuracy on the MMLU benchmark, according to OpenAI. "
                "Pricing was set at $30 per million output tokens, the company stated. "
                "Independent evaluators confirmed the results match published benchmarks."
            ),
            analysis_section=(
                "**Analysis:** The release may accelerate industry debates about the timeline "
                "to artificial general intelligence, analysts suggest."
            ),
        )
        articles.append(edit_article(lead_story, llm_caller=lead_caller))

        # Standard stories (sig=7-8)
        for i, sig in enumerate([8, 7]):
            std_story = _make_analyzed_story(
                title=f"Standard AI Story {i+1}",
                significance=sig,
            )
            std_caller = _make_llm_caller(
                headline=f"Standard AI Development Story {i+1}",
                lead_paragraph=f"An AI development was reported on Tuesday, according to sources {i+1}.",
                body=f"Details of development {i+1} confirmed by researchers.",
            )
            articles.append(edit_article(std_story, llm_caller=std_caller))

        # Roundup stories (sig=4-6)
        for i, sig in enumerate([6, 5, 5, 4, 4]):
            roundup_story = _make_analyzed_story(
                title=f"Roundup Story {i+1}",
                significance=sig,
            )
            roundup_caller = _make_llm_caller(
                headline=f"Brief AI Update {i+1}",
                lead_paragraph=f"A brief update was noted on Wednesday, according to reports {i+1}.",
                body=f"Minor detail {i+1} confirmed.",
            )
            articles.append(edit_article(roundup_story, llm_caller=roundup_caller))

        return articles

    def test_newsletter_has_overview(self, isolated_db):
        """Newsletter starts with 2-3 sentence overview."""
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        articles = self._build_articles()
        newsletter = assemble_newsletter(articles, "2026-02-25")

        # Overview appears near the top (before first ---)
        first_divider = newsletter.find("---")
        preamble = newsletter[:first_divider] if first_divider != -1 else newsletter[:500]
        # Should have a sentence or two as overview
        assert len(preamble.strip()) > 20, "Newsletter must have opening overview"
        print("PASS: Scenario 4.5a — Newsletter has opening overview")

    def test_lead_story_appears_first(self, isolated_db):
        """Lead story (highest significance) appears before standard stories."""
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        articles = self._build_articles()
        newsletter = assemble_newsletter(articles, "2026-02-25")

        lead_pos = newsletter.find("GPT-6")
        standard_pos = newsletter.find("Standard AI Development Story 1")

        assert lead_pos != -1, "Lead story headline must appear in newsletter"
        assert standard_pos != -1, "Standard story must appear in newsletter"
        assert lead_pos < standard_pos, \
            "Lead story must appear before standard stories"
        print("PASS: Scenario 4.5b — Lead story appears first in newsletter")

    def test_roundup_section_present(self, isolated_db):
        """Newsletter has a Roundup section for low-significance stories."""
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        articles = self._build_articles()
        newsletter = assemble_newsletter(articles, "2026-02-25")

        assert "Roundup" in newsletter, "Newsletter must have Roundup section"
        # Roundup stories appear in the roundup section
        roundup_pos = newsletter.find("Roundup")
        brief_pos = newsletter.find("Brief AI Update 1")
        assert brief_pos > roundup_pos, \
            "Roundup stories must appear after the Roundup heading"
        print("PASS: Scenario 4.5c — Roundup section present with low-significance stories")

    def test_newsletter_sign_off(self, isolated_db):
        """Newsletter ends with the canonical sign-off."""
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        articles = self._build_articles()
        newsletter = assemble_newsletter(articles, "2026-02-25")

        assert "That's The LLM Report for 2026-02-25" in newsletter, \
            "Newsletter must contain canonical sign-off with date"
        print("PASS: Scenario 4.5d — Newsletter has correct sign-off with date")

    def test_all_8_stories_included(self, isolated_db):
        """All 8 stories appear in the assembled newsletter."""
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        articles = self._build_articles()
        assert len(articles) == 8, f"Expected 8 articles, got {len(articles)}"

        newsletter = assemble_newsletter(articles, "2026-02-25")

        # Check each article's headline appears
        for article in articles:
            assert article.headline in newsletter, \
                f"Article headline '{article.headline}' missing from newsletter"
        print("PASS: Scenario 4.5e — All 8 articles present in newsletter")

    def test_newsletter_structure_order(self, isolated_db):
        """Newsletter: overview → lead → standard → roundup → sign-off."""
        from pipeline.src.editorial.editorial_agent import assemble_newsletter

        articles = self._build_articles()
        newsletter = assemble_newsletter(articles, "2026-02-25")

        overview_pos = newsletter.find("This edition")
        lead_pos = newsletter.find("GPT-6")
        roundup_pos = newsletter.find("Roundup")
        signoff_pos = newsletter.find("That's The LLM Report")

        assert overview_pos < lead_pos, "Overview must precede lead story"
        assert lead_pos < roundup_pos, "Lead story must precede roundup"
        assert roundup_pos < signoff_pos, "Roundup must precede sign-off"
        print("PASS: Scenario 4.5f — Newsletter structure order is correct")


# ---------------------------------------------------------------------------
# Additional unit tests for editorial_agent helpers
# ---------------------------------------------------------------------------

class TestEditBatch:
    """Tests for edit_batch helper."""

    def test_batch_continues_on_error(self, isolated_db):
        """Batch editing continues when one story fails."""
        from pipeline.src.editorial.editorial_agent import edit_batch

        stories = [_make_analyzed_story(title=f"Story {i}", significance=7) for i in range(3)]

        call_count = [0]

        def failing_on_second(prompt):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Simulated LLM failure")
            return {
                "headline": "Test Headline",
                "subheadline": "Test subheadline.",
                "lead_paragraph": "Test lead paragraph about AI developments.",
                "body": "Test body with details according to sources.",
                "analysis_section": None,
                "sources_footer": "Sources: https://example.com",
            }

        articles, errors = edit_batch(stories, llm_caller=failing_on_second)
        assert len(errors) == 1, f"Expected 1 error, got {len(errors)}"
        assert len(articles) == 2, f"Expected 2 successful articles, got {len(articles)}"
        print("PASS: Batch edit continues after individual story failure")

    def test_all_article_fields_present(self, isolated_db):
        """All EditedArticle fields are populated after editing."""
        from pipeline.src.editorial.editorial_agent import edit_article

        story = _make_analyzed_story(significance=8)
        caller = _make_llm_caller()
        article = edit_article(story, llm_caller=caller)

        assert article.headline, "Headline must be non-empty"
        assert article.subheadline, "Subheadline must be non-empty"
        assert article.lead_paragraph, "Lead paragraph must be non-empty"
        assert article.body, "Body must be non-empty"
        assert article.sources_footer, "Sources footer must be non-empty"
        assert article.word_count > 0, "Word count must be > 0"
        print("PASS: All EditedArticle fields populated")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
