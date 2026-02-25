"""
The LLM Report — Editorial Agent
Converts AnalyzedStory objects into publication-ready EditedArticle objects.
Voice: Reuters/Ars Technica register, third person, no first person.
Model: Claude Opus (editorial quality gate)
KB-First Pattern: always query KB before calling LLM.
NLSpec Section 5.5
"""

from __future__ import annotations
import json
import os
from typing import Callable, Optional

from pipeline.src.models import AnalyzedStory, EditedArticle
from pipeline.src.kb import kb_query

EDITORIAL_MODEL = os.environ.get("EDITORIAL_MODEL", "claude-opus-4-6")
LITELLM_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")

# Prohibited promotional language (NLSpec Section 5.5)
PROMO_WORDS = [
    "revolutionary", "game-changing", "groundbreaking", "unprecedented",
    "amazing", "incredible", "stunning", "exciting", "fantastic",
]

EDITORIAL_PROMPT_TEMPLATE = """You are a senior technology journalist writing for The LLM Report.
Style: Reuters/Ars Technica register. Third person only. No first person ("I", "we", "our").
No promotional language (revolutionary, game-changing, groundbreaking, unprecedented, amazing, incredible, stunning, exciting, fantastic).
No emoji. No bullet points — flowing paragraphs only.

KNOWLEDGE BASE CONTEXT (background, prior coverage, model specs):
{kb_context}

STORY BRIEF:
What happened: {what_happened}
Why it matters: {why_it_matters}
Key details: {key_details}
Sources: {sources}
Single-source claims (flag with "according to [source]"): {single_source_claims}
Analysis angles (use only if significance >= 7): {analysis_angles}
Significance: {significance}/10

ARTICLE FORMAT RULES:
- headline: max 80 characters, factual, no clickbait
- subheadline: 1 sentence expanding headline
- lead_paragraph: who/what/when, {lead_word_target} words, all claims attributed inline
- body: flowing paragraphs, no bullets, no emoji, all claims attributed inline
- analysis_section: ONLY if significance >= 7 AND analysis_angles provided.
  Must begin with "**Analysis:**". Use qualified language (may, could, suggests).
  If significance < 7 or no analysis_angles, set to null.
- sources_footer: "Sources: [url1, url2, ...]"

Return ONLY valid JSON with these exact keys:
{{
  "headline": "...",
  "subheadline": "...",
  "lead_paragraph": "...",
  "body": "...",
  "analysis_section": "**Analysis:** ..." or null,
  "sources_footer": "Sources: ..."
}}

RESPONSE:"""


def _call_editorial_llm(prompt: str) -> dict:
    """Call the editorial LLM. Returns parsed JSON dict."""
    try:
        import litellm
        litellm.api_base = LITELLM_URL
        response = litellm.completion(
            model=EDITORIAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Editorial LLM returned invalid JSON: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Editorial LLM call failed: {e}") from e


def _determine_lead_word_target(significance: int) -> str:
    """Return word count target string based on significance."""
    if significance >= 9:
        return "600-1000"
    elif significance >= 7:
        return "300-600"
    else:
        return "80-200"


def _build_kb_context(story: AnalyzedStory) -> str:
    """KB-First Pattern: query cache + vector store before calling LLM."""
    query_text = f"{story.group.primary.item.title} {story.group.primary.item.raw_content[:200]}"

    # Extract entity names from the story for structured KB lookup
    entity_names: list[str] = []
    if story.group.primary.item.tags:
        entity_names = story.group.primary.item.tags[:3]

    ctx = kb_query.query(
        query_text=query_text,
        n_results=5,
        entity_names=entity_names if entity_names else None,
        cache_type="news",
    )

    if ctx.cache_hit and ctx.cached_response:
        return f"[CACHED] {ctx.cached_response[:500]}"

    parts: list[str] = []
    if ctx.similar_articles:
        parts.append("Prior coverage:")
        for art in ctx.similar_articles[:3]:
            title = art.get("metadata", {}).get("title", art.get("id", ""))
            parts.append(f"  - {title}")
    if ctx.entity_metadata:
        parts.append("Entity metadata:")
        for name, meta in list(ctx.entity_metadata.items())[:3]:
            parts.append(f"  - {name}: {json.dumps(meta)[:200]}")
    if ctx.context_text:
        parts.append(f"Context: {ctx.context_text[:400]}")

    return "\n".join(parts) if parts else "No prior KB context available."


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split()) if text else 0


def edit_article(
    story: AnalyzedStory,
    llm_caller: Optional[Callable[[str], dict]] = None,
) -> EditedArticle:
    """
    Convert an AnalyzedStory into a publication-ready EditedArticle.

    Args:
        story: The analyzed story to edit.
        llm_caller: Optional injectable LLM caller for testing.
                    Receives the prompt string, returns a dict.

    Returns:
        EditedArticle with all fields populated.
    """
    significance = story.group.max_significance
    lead_word_target = _determine_lead_word_target(significance)

    # KB-First Pattern
    kb_context = _build_kb_context(story)

    # Build prompt
    prompt = EDITORIAL_PROMPT_TEMPLATE.format(
        kb_context=kb_context,
        what_happened=story.what_happened,
        why_it_matters=story.why_it_matters,
        key_details=story.key_details,
        sources=", ".join(story.sources) if story.sources else "No URLs provided",
        single_source_claims="; ".join(story.single_source_claims) if story.single_source_claims else "None",
        analysis_angles="; ".join(story.analysis_angles) if story.analysis_angles else "None",
        significance=significance,
        lead_word_target=lead_word_target,
    )

    # Call LLM
    caller = llm_caller if llm_caller is not None else _call_editorial_llm
    result = caller(prompt)

    # Extract fields with safe defaults
    headline = str(result.get("headline", ""))[:80]
    subheadline = str(result.get("subheadline", ""))
    lead_paragraph = str(result.get("lead_paragraph", ""))
    body = str(result.get("body", ""))
    raw_analysis = result.get("analysis_section")

    # Only attach analysis section if significance >= 7 and angles exist
    analysis_section: Optional[str] = None
    if significance >= 7 and story.analysis_angles and raw_analysis:
        analysis_text = str(raw_analysis)
        # Ensure label is present
        if not analysis_text.strip().startswith("**Analysis:**"):
            analysis_text = "**Analysis:** " + analysis_text
        analysis_section = analysis_text
    sources_footer = str(result.get("sources_footer", f"Sources: {', '.join(story.sources)}"))

    # Word count covers lead + body
    word_count = _count_words(lead_paragraph) + _count_words(body)

    return EditedArticle(
        story=story,
        headline=headline,
        subheadline=subheadline,
        lead_paragraph=lead_paragraph,
        body=body,
        analysis_section=analysis_section,
        sources_footer=sources_footer,
        word_count=word_count,
        editorial_cost_usd=0.0,  # cost tracking handled by LiteLLM
    )


def edit_batch(
    stories: list[AnalyzedStory],
    llm_caller: Optional[Callable[[str], dict]] = None,
) -> tuple[list[EditedArticle], list[str]]:
    """
    Edit a batch of analyzed stories.

    Returns:
        Tuple of (list of EditedArticle, list of error strings).
        Continues processing on individual failures.
    """
    articles: list[EditedArticle] = []
    errors: list[str] = []

    for story in stories:
        try:
            article = edit_article(story, llm_caller=llm_caller)
            articles.append(article)
        except Exception as e:
            errors.append(f"Editorial failed for '{story.group.primary.item.title}': {e}")

    return articles, errors


def _get_next_publish_day(date_str: str) -> str:
    """Return the next scheduled publishing day given a date string."""
    from datetime import datetime, timedelta
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "next edition"
    # Schedule: Mon/Wed/Fri/Sat
    schedule_days = [0, 2, 4, 5]  # Mon=0, Wed=2, Fri=4, Sat=5
    day_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
                 4: "Friday", 5: "Saturday", 6: "Sunday"}
    for offset in range(1, 8):
        next_dt = dt + timedelta(days=offset)
        if next_dt.weekday() in schedule_days:
            return day_names[next_dt.weekday()]
    return "next edition"


def assemble_newsletter(articles: list[EditedArticle], date: str) -> str:
    """
    Assemble a full newsletter edition in Markdown.

    Structure:
    1. Opening: 2-3 sentence overview
    2. Lead story (highest significance)
    3. Standard stories (significance 7-10, ordered desc)
    4. Roundup section (significance 4-6)
    5. Sign-off

    Args:
        articles: List of EditedArticle objects.
        date: Publication date string (YYYY-MM-DD).

    Returns:
        Full newsletter markdown string.
    """
    if not articles:
        return f"# The LLM Report — {date}\n\nNo stories available for this edition.\n"

    # Sort all articles by significance descending
    sorted_articles = sorted(
        articles,
        key=lambda a: a.story.group.max_significance,
        reverse=True,
    )

    lead_stories = [a for a in sorted_articles if a.story.group.max_significance >= 9]
    standard_stories = [a for a in sorted_articles
                        if 7 <= a.story.group.max_significance <= 8]
    roundup_stories = [a for a in sorted_articles
                       if a.story.group.max_significance <= 6]

    # Lead story: highest significance article
    lead = lead_stories[0] if lead_stories else (standard_stories[0] if standard_stories else sorted_articles[0])
    remaining_standard = [a for a in standard_stories if a is not lead]

    # Build overview (2-3 sentences summarizing top stories)
    top_headlines = [a.headline for a in sorted_articles[:3] if a.headline]
    if len(top_headlines) >= 2:
        overview = (
            f"This edition covers {len(articles)} stories from the AI space. "
            f"Top stories include {top_headlines[0]}"
        )
        if len(top_headlines) >= 2:
            overview += f" and {top_headlines[1]}"
        overview += "."
        if len(top_headlines) >= 3:
            overview += f" Also covered: {top_headlines[2]}."
    else:
        overview = (
            f"This edition of The LLM Report covers {len(articles)} "
            f"stories from the AI space."
        )

    next_day = _get_next_publish_day(date)

    # Assemble markdown
    lines: list[str] = []
    lines.append(f"# The LLM Report — {date}\n")
    lines.append(f"{overview}\n")
    lines.append("---\n")

    # Lead story
    lines.append(f"## {lead.headline}\n")
    lines.append(f"*{lead.subheadline}*\n")
    lines.append(f"{lead.lead_paragraph}\n")
    lines.append(f"{lead.body}\n")
    if lead.analysis_section:
        lines.append(f"{lead.analysis_section}\n")
    lines.append(f"*{lead.sources_footer}*\n")
    lines.append("---\n")

    # Standard stories
    for article in remaining_standard:
        lines.append(f"## {article.headline}\n")
        lines.append(f"*{article.subheadline}*\n")
        lines.append(f"{article.lead_paragraph}\n")
        lines.append(f"{article.body}\n")
        if article.analysis_section:
            lines.append(f"{article.analysis_section}\n")
        lines.append(f"*{article.sources_footer}*\n")
        lines.append("---\n")

    # Roundup section
    if roundup_stories:
        lines.append("## Roundup\n")
        lines.append("*Shorter takes on other notable developments.*\n")
        for article in roundup_stories:
            lines.append(f"### {article.headline}\n")
            lines.append(f"{article.lead_paragraph}\n")
            lines.append(f"*{article.sources_footer}*\n")
        lines.append("---\n")

    # Sign-off
    lines.append(
        f"*That's The LLM Report for {date}. "
        f"See you {next_day}.*\n"
    )

    return "\n".join(lines)
