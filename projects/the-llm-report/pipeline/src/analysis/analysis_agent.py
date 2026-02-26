"""
The LLM Report — Analysis Agent
Synthesizes story groups into factual, multi-source briefs with verified claims.
Model: Claude Opus (strong — highest quality stage)
KB-First Pattern: always query KB before calling LLM.
NLSpec Section 5.4
"""

from __future__ import annotations
import json
import os
from typing import Callable, Optional

from pipeline.src.models import AnalyzedStory, StoryGroup, TriagedItem
from pipeline.src.kb import kb_query, store
from pipeline.src.collect.tagger import extract_model_mentions, extract_org_mentions

ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "claude-opus-4-6")
LITELLM_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")

ANALYSIS_PROMPT_TEMPLATE = """You are a senior AI industry analyst producing a factual brief for a professional newsletter.

KNOWLEDGE BASE CONTEXT:
{kb_context}

STORY GROUP TO ANALYZE:
Primary source: {primary_source} (Tier {primary_tier})
Significance: {significance}/10

PRIMARY ARTICLE:
Title: {primary_title}
Content: {primary_content}

SUPPORTING SOURCES ({supporting_count}):
{supporting_sources}

Produce a structured JSON brief with these exact keys:
- "what_happened": 2-3 sentences of factual summary. Multi-source where available.
- "why_it_matters": 1-2 sentences explaining significance to AI practitioners.
- "key_details": Specific facts — specs, benchmarks, pricing, availability. Use exact numbers.
- "sources": List of source URLs.
- "single_source_claims": List of claims that appear in only ONE source (lower confidence).
- "analysis_angles": List of forward-looking angles for the Analysis section (max 2).
- "kb_context_used": true if KB context meaningfully informed the brief.

Rules:
- Every factual claim must be attributable to a source in the brief.
- Do not invent benchmarks, prices, or dates.
- Mark claims only in one source as single_source.
- Keep what_happened under 100 words.
- Return ONLY valid JSON, no markdown.

RESPONSE:"""


def _call_analysis_llm(prompt: str) -> dict:
    """Call the analysis LLM. Returns parsed JSON dict."""
    try:
        import litellm
        litellm.api_base = LITELLM_URL
        response = litellm.completion(
            model=ANALYSIS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Analysis LLM returned invalid JSON: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Analysis LLM call failed: {e}") from e


def _build_supporting_text(supporting: list[TriagedItem]) -> str:
    if not supporting:
        return "(No supporting sources)"
    parts = []
    for i, t in enumerate(supporting, 1):
        parts.append(
            f"Source {i}: {t.item.source_name}\n"
            f"Title: {t.item.title}\n"
            f"Content: {t.item.raw_content[:500]}"
        )
    return "\n\n".join(parts)


def analyze_story(
    group: StoryGroup,
    llm_caller: Optional[Callable[[str], dict]] = None,
) -> AnalyzedStory:
    """
    Analyze a StoryGroup using the KB-First Query Pattern.
    1. Extract entities from story
    2. Query KB (cache + vector + structured)
    3. Build prompt with KB context injected
    4. Call LLM (or use cached response)
    5. Cache the LLM response
    6. Return AnalyzedStory
    """
    primary = group.primary.item
    query_text = f"{primary.title} {primary.raw_content[:300]}"

    # Extract entities for structured store lookup
    model_mentions = extract_model_mentions(f"{primary.title} {primary.raw_content}")
    org_mentions = extract_org_mentions(f"{primary.title} {primary.raw_content}")
    entity_names = list(set(model_mentions + org_mentions))

    # KB-First Query
    ctx = kb_query.query(
        query_text,
        n_results=5,
        entity_names=entity_names[:5],
        cache_type="news",
    )

    kb_context_used = False
    result = None

    # If semantic cache hit, try to use it
    if ctx.cache_hit and ctx.cached_response:
        try:
            result = json.loads(ctx.cached_response)
            result["kb_context_used"] = True
            result["llm_call_made"] = False
        except (json.JSONDecodeError, TypeError):
            result = None

    # Call LLM if no cache hit
    if result is None:
        context_text = kb_query.format_context_for_prompt(ctx, query_text)
        if ctx.context_text:
            kb_context_used = True

        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            kb_context=context_text,
            primary_source=primary.source_name,
            primary_tier=primary.source_tier,
            significance=group.primary.significance,
            primary_title=primary.title,
            primary_content=primary.raw_content[:800],
            supporting_count=len(group.supporting),
            supporting_sources=_build_supporting_text(group.supporting),
        )

        caller = llm_caller or _call_analysis_llm
        result = caller(prompt)
        result["llm_call_made"] = True

        # Cache the response
        kb_query.cache_llm_response(query_text, json.dumps(result), cache_type="news")

    # Ensure sources list includes all source URLs
    sources = result.get("sources", [])
    if not sources:
        sources = [primary.url]
    for sup in group.supporting:
        if sup.item.url not in sources:
            sources.append(sup.item.url)

    # Coerce key_details to str — LLM occasionally returns a dict or list
    raw_key_details = result.get("key_details", "")
    if isinstance(raw_key_details, dict):
        raw_key_details = "\n".join(f"{k}: {v}" for k, v in raw_key_details.items())
    elif isinstance(raw_key_details, list):
        raw_key_details = "\n".join(str(x) for x in raw_key_details)

    return AnalyzedStory(
        group=group,
        what_happened=result.get("what_happened", ""),
        why_it_matters=result.get("why_it_matters", ""),
        key_details=raw_key_details,
        sources=sources,
        single_source_claims=result.get("single_source_claims", []),
        analysis_angles=result.get("analysis_angles", [])[:2],
        kb_context_used=result.get("kb_context_used", kb_context_used),
        llm_call_made=result.get("llm_call_made", True),
        analysis_cost_usd=0.0,
    )


def analyze_batch(
    groups: list[StoryGroup],
    llm_caller=None,
    max_errors: int = 3,
) -> tuple[list[AnalyzedStory], list[str]]:
    """Analyze a batch of story groups. Returns (stories, errors)."""
    results = []
    errors = []
    for group in groups:
        try:
            story = analyze_story(group, llm_caller=llm_caller)
            results.append(story)
        except Exception as e:
            errors.append(f"StoryGroup {group.id[:8]}: {e}")
            if len(errors) >= max_errors:
                break
    return results, errors
