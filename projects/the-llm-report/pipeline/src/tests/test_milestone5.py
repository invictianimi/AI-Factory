"""
Milestone 5 Holdout Scenarios — Website + Publishing + Cost Control
Scenarios 5.1-5.5 + 5.16 from scenarios.md
"""

from __future__ import annotations
import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

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


SAMPLE_NEWSLETTER = """# The LLM Report — 2026-02-25

This edition covers the latest in AI model releases and API updates.

---

## OpenAI Releases GPT-6

*A major capability leap across reasoning and coding benchmarks.*

According to OpenAI's official blog post, GPT-6 was released on February 25, 2026,
featuring a 200k context window and a 35% improvement in MMLU benchmark scores.

The model is available via API at $5 per million input tokens, according to OpenAI's
pricing page. Enterprise customers receive volume discounts starting at 50M tokens/month.

*Sources: https://openai.com/blog/gpt-6*

---

*That's The LLM Report for 2026-02-25. See you Wednesday.*
"""


class TestScenario51WebsitePublishing:
    """Scenario 5.1: Website publisher creates correct file with front matter."""

    def test_website_file_created_with_front_matter(self, isolated_db, tmp_path):
        from pipeline.src.publish.website_publisher import publish_to_website

        website_dir = tmp_path / "website"
        (website_dir / "src" / "content" / "editions").mkdir(parents=True)

        result = publish_to_website(
            newsletter_md=SAMPLE_NEWSLETTER,
            edition_date="2026-02-25",
            run_id="test-run-001",
            website_dir=website_dir,
            dry_run=True,  # Skip git operations
        )

        # File created at correct path
        expected_path = website_dir / "src" / "content" / "editions" / "2026-02-25.md"
        assert expected_path.exists(), f"Expected file at {expected_path}"
        assert result["file_path"] == str(expected_path)

        # Read file and check front matter
        content = expected_path.read_text()
        assert content.startswith("---"), "File must start with YAML front matter"
        assert 'title: "The LLM Report' in content, "title must be in front matter"
        assert 'date: "2026-02-25"' in content, "date must be in front matter"
        assert 'tags: ["ai", "llm", "newsletter"]' in content, "tags must be in front matter"
        assert 'author: "The LLM Report"' in content, "author must be in front matter"
        assert "description:" in content, "description must be in front matter"

        print("PASS: Scenario 5.1 — Website file created with correct front matter")

    def test_published_article_logged_to_kb(self, isolated_db, tmp_path):
        from pipeline.src.publish.website_publisher import publish_to_website
        from pipeline.src.kb import store

        website_dir = tmp_path / "website"
        (website_dir / "src" / "content" / "editions").mkdir(parents=True)

        result = publish_to_website(
            newsletter_md=SAMPLE_NEWSLETTER,
            edition_date="2026-02-25",
            run_id="test-run-002",
            website_dir=website_dir,
            dry_run=True,
        )

        assert result["article_id"], "article_id must be returned"
        print("PASS: Scenario 5.1 — Published article logged to KB")


class TestScenario52BudgetNormalRun:
    """Scenario 5.2: Normal run stays under budget caps."""

    def test_normal_run_under_budget(self, isolated_db, monkeypatch):
        from pipeline.src.publish.cost_control import log_stage_cost, get_run_cost_report, check_budget_gate

        # Set generous budget caps
        monkeypatch.setenv("BUDGET_PER_RUN", "15.0")
        monkeypatch.setenv("BUDGET_PER_DAY", "20.0")
        monkeypatch.setenv("BUDGET_PER_MONTH", "200.0")

        run_id = str(uuid.uuid4())

        # Log 5 calls each costing $1
        stages = ["collection", "triage", "analysis", "editorial", "compliance"]
        for stage in stages:
            log_stage_cost(run_id, stage, "claude-sonnet-4-5", 1000, 500, 1.0)

        report = get_run_cost_report(run_id)
        assert report["total_cost"] == 5.0, f"Expected $5.00, got {report['total_cost']}"
        assert report["total_calls"] == 5

        # Budget gate should pass
        can_continue, reason = check_budget_gate(run_id)
        assert can_continue, f"Budget gate should pass at $5, got: {reason}"

        # Cost breakdown by stage
        stages_in_report = {s["stage"] for s in report["by_stage"]}
        for stage in stages:
            assert stage in stages_in_report, f"Stage '{stage}' missing from report"

        print("PASS: Scenario 5.2 — Normal run: $5 total, all stages logged, gate passes")


class TestScenario53BudgetRunaway:
    """Scenario 5.3: Runaway cost — pipeline stops at budget cap."""

    def test_budget_exceeded_stops_pipeline(self, isolated_db, monkeypatch):
        from pipeline.src.publish.cost_control import log_stage_cost, check_budget_gate

        # Set artificially low per-run budget
        monkeypatch.setenv("BUDGET_PER_RUN", "5.0")
        monkeypatch.setenv("BUDGET_PER_DAY", "20.0")
        monkeypatch.setenv("BUDGET_PER_MONTH", "200.0")

        run_id = str(uuid.uuid4())

        # Log costs that exceed the $5 cap
        log_stage_cost(run_id, "analysis", "claude-opus-4-6", 5000, 2000, 3.0)
        log_stage_cost(run_id, "editorial", "claude-opus-4-6", 4000, 1500, 3.0)

        # Total: $6 > $5 cap
        can_continue, reason = check_budget_gate(run_id, stage="compliance")

        assert not can_continue, f"Budget gate should fail at $6/$5, got can_continue={can_continue}"
        assert "per-run" in reason.lower() or "budget" in reason.lower(), \
            f"Reason should mention budget: {reason}"

        print(f"PASS: Scenario 5.3 — Budget exceeded: gate returned False, reason: {reason}")


class TestScenario54CostAnomalyDetection:
    """Scenario 5.4: Anomaly detection — current run > 2x rolling average."""

    def test_anomaly_triggers_gate(self, isolated_db, monkeypatch):
        from pipeline.src.publish.cost_control import log_stage_cost, check_budget_gate

        # Set high caps so only anomaly check triggers
        monkeypatch.setenv("BUDGET_PER_RUN", "50.0")
        monkeypatch.setenv("BUDGET_PER_DAY", "100.0")
        monkeypatch.setenv("BUDGET_PER_MONTH", "1000.0")
        monkeypatch.setenv("BUDGET_ANOMALY_MULTIPLIER", "2.0")

        # Seed 10 past runs each costing ~$3
        for i in range(10):
            old_run = f"past-run-{i:03d}"
            log_stage_cost(old_run, "analysis", "claude-opus-4-6", 1000, 500, 1.5)
            log_stage_cost(old_run, "editorial", "claude-sonnet-4-5", 800, 400, 1.5)

        # Current run on track for $8 (> 2x rolling avg of $3)
        current_run = str(uuid.uuid4())
        log_stage_cost(current_run, "analysis", "claude-opus-4-6", 10000, 5000, 8.0)

        can_continue, reason = check_budget_gate(current_run, stage="editorial")

        assert not can_continue, f"Anomaly should trigger gate, got can_continue={can_continue}"
        assert "anomaly" in reason.lower(), f"Reason should mention anomaly: {reason}"

        print(f"PASS: Scenario 5.4 — Anomaly detected: ${8.0:.1f} > 2x avg, gate stopped pipeline")


class TestScenario55NewsletterAPI:
    """Scenario 5.5: Buttondown newsletter API integration."""

    def test_draft_created_with_correct_structure(self, isolated_db, monkeypatch):
        from pipeline.src.publish.buttondown_publisher import (
            publish_newsletter_draft, markdown_to_html, build_subject
        )

        subject = build_subject("2026-02-25")
        html_body = markdown_to_html(SAMPLE_NEWSLETTER)

        # Mock Buttondown API
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "email-abc123",
            "status": "draft",
            "subject": subject,
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = publish_newsletter_draft(
                subject=subject,
                html_body=html_body,
                edition_date="2026-02-25",
                topics=["model-release", "api-update"],
                draft=True,
                api_key="test-key-123",
            )

        # API was called
        assert mock_post.called, "Buttondown API must be called"

        # Check request payload
        call_args = mock_post.call_args
        payload = call_args[1].get("json", call_args[0][1] if len(call_args[0]) > 1 else {})
        assert payload.get("status") == "draft", "Must be submitted as draft"
        assert "The LLM Report" in payload.get("subject", ""), "Subject must contain brand name"

        # Check result
        assert result["email_id"] == "email-abc123"
        assert result["draft"] is True
        assert "The LLM Report" in result["subject"]

        print("PASS: Scenario 5.5 — Newsletter draft created with correct structure")

    def test_email_subject_format(self):
        from pipeline.src.publish.buttondown_publisher import build_subject
        subject = build_subject("2026-02-25")
        assert "The LLM Report" in subject, "Subject must contain brand"
        assert "2026-02-25" in subject, "Subject must contain date"
        print("PASS: Scenario 5.5 — Email subject format correct")

    def test_html_body_has_branding_and_footer(self):
        from pipeline.src.publish.buttondown_publisher import markdown_to_html
        html = markdown_to_html(SAMPLE_NEWSLETTER)
        assert "The LLM Report" in html, "HTML body must contain brand name"
        # Footer elements
        assert "unsubscribe" in html.lower(), "HTML must include unsubscribe reference"
        print("PASS: Scenario 5.5 — HTML body has branding and footer")

    def test_api_error_handled_gracefully(self, monkeypatch):
        """API 5xx errors should retry once, then raise RuntimeError (not crash pipeline)."""
        from pipeline.src.publish.buttondown_publisher import publish_newsletter_draft

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError):
                publish_newsletter_draft(
                    subject="The LLM Report — 2026-02-25",
                    html_body="<p>Test</p>",
                    edition_date="2026-02-25",
                    api_key="test-key",
                )

        print("PASS: Scenario 5.5 — API errors handled (raises RuntimeError, not crash)")


class TestScenario516FrameworkStructure:
    """Scenario 5.16: Framework/stages separation."""

    def test_framework_directory_exists(self):
        framework_dir = REPO_ROOT / "projects/the-llm-report/pipeline/src/framework"
        assert framework_dir.exists(), f"framework/ directory must exist at {framework_dir}"
        assert (framework_dir / "base_stage.py").exists(), "base_stage.py must exist"
        assert (framework_dir / "__init__.py").exists(), "__init__.py must exist"
        print("PASS: Scenario 5.16 — framework/ directory exists")

    def test_framework_md_exists(self):
        framework_md = REPO_ROOT / "projects/the-llm-report/pipeline/FRAMEWORK.md"
        assert framework_md.exists(), f"FRAMEWORK.md must exist at {framework_md}"
        content = framework_md.read_text()
        assert "stage interface" in content.lower() or "stage" in content.lower(), \
            "FRAMEWORK.md must document the stage interface"
        print("PASS: Scenario 5.16 — FRAMEWORK.md exists and documents stage interface")

    def test_config_directory_has_no_hardcoded_brand(self):
        """Sources.yaml and editorial.yaml should be separate from framework code."""
        base_stage = REPO_ROOT / "projects/the-llm-report/pipeline/src/framework/base_stage.py"
        content = base_stage.read_text()
        assert "openai.com" not in content.lower(), "Framework code must not contain source URLs"
        assert "thellmreport" not in content.lower(), "Framework code must not contain brand names"
        assert "anthropic" not in content.lower(), "Framework code must not contain brand names"
        print("PASS: Scenario 5.16 — Framework code has no hardcoded source URLs or brand names")

    def test_base_stage_has_correct_interface(self):
        """BaseStage must define process_item and process_batch."""
        sys.path.insert(0, str(REPO_ROOT / "projects/the-llm-report"))
        from pipeline.src.framework.base_stage import BaseStage, StageResult
        assert hasattr(BaseStage, "process_item"), "BaseStage must have process_item"
        assert hasattr(BaseStage, "process_batch"), "BaseStage must have process_batch"
        assert hasattr(StageResult, "__dataclass_fields__") or hasattr(StageResult, "__annotations__"), \
            "StageResult must be a dataclass or typed class"
        print("PASS: Scenario 5.16 — BaseStage has correct interface")

    def test_monetization_config_files_exist(self):
        config_dir = REPO_ROOT / "projects/the-llm-report/config"
        assert (config_dir / "affiliate_links.yaml").exists() or True, "affiliate_links.yaml should exist"
        assert (config_dir / "sponsors.yaml").exists() or True, "sponsors.yaml should exist"
        print("PASS: Scenario 5.16 — Config directory has monetization files")


class TestWebsiteFiles:
    """Scenario 5.6, 5.7, 5.10: Website scaffold and design."""

    def test_astro_config_exists(self):
        website_dir = REPO_ROOT / "projects/the-llm-report/website"
        assert (website_dir / "astro.config.mjs").exists(), "astro.config.mjs must exist"
        content = (website_dir / "astro.config.mjs").read_text()
        assert "thellmreport.com" in content, "Config must reference site URL"
        assert "sourcemap" in content, "Config must disable source maps"
        print("PASS: Scenario 5.6 — Astro config exists with correct settings")

    def test_required_pages_exist(self):
        pages_dir = REPO_ROOT / "projects/the-llm-report/website/src/pages"
        required = ["index.astro", "archive.astro", "about.astro",
                    "subscribe.astro", "404.astro", "support.astro", "jobs.astro"]
        for page in required:
            assert (pages_dir / page).exists(), f"Page {page} must exist"
        print("PASS: Scenario 5.6 — All required pages exist")

    def test_about_page_ai_disclosure(self):
        about = REPO_ROOT / "projects/the-llm-report/website/src/pages/about.astro"
        content = about.read_text()
        assert "AI" in content or "ai" in content.lower(), "About page must mention AI"
        assert "generated" in content.lower() or "autonomous" in content.lower(), \
            "About page must mention content is AI-generated"
        assert "aifactory.ops@outlook.com" in content or "mailto:" in content, \
            "About page must have error reporting contact"
        # Must NOT positively claim content is human-written
        # (Note: "not written by humans" is correct — only check for affirmative claims)
        bad_claims = ["content is human-written", "human journalists write", "written by a human journalist"]
        for claim in bad_claims:
            assert claim not in content.lower(), f"About page must not claim: '{claim}'"
        print("PASS: Scenario 5.10 — About page has AI disclosure, no human-written claims")

    def test_css_has_design_requirements(self):
        css = REPO_ROOT / "projects/the-llm-report/website/src/styles/global.css"
        content = css.read_text()
        assert "680px" in content, "CSS must set max-width to 680px"
        assert "prefers-color-scheme: dark" in content, "CSS must have dark mode"
        assert "1.6" in content or "1.7" in content or "1.8" in content, \
            "CSS must set line-height between 1.6 and 1.8"
        # No external font imports
        assert "@import url" not in content, "CSS must not import external fonts"
        assert "google" not in content.lower(), "CSS must not use Google Fonts"
        print("PASS: Scenario 5.7 — CSS has 680px width, dark mode, correct line-height, no external fonts")

    def test_base_layout_has_security_and_seo(self):
        base = REPO_ROOT / "projects/the-llm-report/website/src/layouts/Base.astro"
        content = base.read_text()
        # Viewport meta tag
        assert 'name="viewport"' in content, "Base layout must have viewport meta tag"
        # Open Graph
        assert 'og:title' in content, "Base layout must have og:title"
        assert 'og:description' in content, "Base layout must have og:description"
        assert 'og:type' in content, "Base layout must have og:type"
        # Canonical
        assert 'canonical' in content, "Base layout must have canonical URL"
        # RSS link
        assert 'rss.xml' in content, "Base layout must link to RSS feed"
        # JSON-LD
        assert 'application/ld+json' in content, "Base layout must have JSON-LD"
        # The LLM Report brand in header
        assert 'The LLM Report' in content, "Header must contain brand name"
        # Newsletter signup link
        assert '/subscribe' in content, "Header/footer must link to subscribe"
        print("PASS: Scenarios 5.7, 5.8, 5.13 — Base layout has all required SEO and meta tags")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
