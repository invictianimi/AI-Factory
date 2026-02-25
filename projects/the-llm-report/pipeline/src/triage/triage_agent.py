"""
The LLM Report — Triage Agent
Scores each collected item for significance (1-10) across 4 dimensions,
classifies into categories, applies tier promotion rule.
Model: Claude Sonnet (mid-range — good judgment, not deepest reasoning)
NLSpec Section 5.2
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Optional

from pipeline.src.models import CollectedItem, TriagedItem
from pipeline.src.kb import kb_query

LITELLM_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "claude-sonnet-4-5")

VALID_CATEGORIES = {
    "model-release", "api-update", "security-patch", "acquisition",
    "partnership", "research-paper", "framework-release", "methodology",
    "policy-regulatory", "benchmark", "pricing-change",
}

TRIAGE_PROMPT_TEMPLATE = """You are a senior technology news editor assessing incoming stories for an AI industry newsletter.

CONTEXT FROM KNOWLEDGE BASE:
{kb_context}

NEW ITEM TO ASSESS:
Title: {title}
Source: {source_name} (Tier {source_tier})
Published: {published_at}
Content: {raw_content}

Score this item 1-10 for significance and classify it.

Scoring dimensions:
- Novelty: Is this genuinely new, or an incremental update?
- Impact: Does this affect how practitioners build or deploy AI?
- Breadth: Does this affect one product or the whole industry?
- Timeliness: Is this breaking, or background context?

Valid categories: model-release, api-update, security-patch, acquisition, partnership, research-paper, framework-release, methodology, policy-regulatory, benchmark, pricing-change

Return ONLY valid JSON, no markdown:
{{"significance": <1-10 integer>, "category": "<category>", "rationale": "<one sentence>", "suggested_headline": "<max 80 chars>", "promoted": <true if tier 2/3 AND significance >= 8, else false>}}"""


def _call_triage_llm(prompt: str) -> dict:
    """Call the triage LLM via LiteLLM proxy. Returns parsed JSON dict."""
    try:
        import litellm
        litellm.api_base = LITELLM_URL

        response = litellm.completion(
            model=TRIAGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"Triage LLM returned invalid JSON: {text[:200]}")
    except Exception as e:
        raise RuntimeError(f"Triage LLM call failed: {e}") from e


def _route_item(significance: int) -> str:
    """Map significance score to pipeline route."""
    if significance <= 3:
        return "archive"
    elif significance <= 6:
        return "roundup"
    elif significance <= 8:
        return "story"
    else:
        return "lead"


def triage_item(
    item: CollectedItem,
    llm_caller=None,  # Injectable for testing
) -> TriagedItem:
    """
    Triage a single CollectedItem.
    1. Query KB for context (KB-First Pattern)
    2. Call LLM for significance scoring
    3. Apply tier promotion rule
    4. Return TriagedItem

    Args:
        item: The item to triage
        llm_caller: Optional callable(prompt) -> dict for testing injection
    """
    # Step 1: KB context query
    ctx = kb_query.query(
        f"{item.title} {item.raw_content[:200]}",
        n_results=3,
        cache_type="news",
    )

    # Step 2: Build prompt
    prompt = TRIAGE_PROMPT_TEMPLATE.format(
        kb_context=kb_query.format_context_for_prompt(ctx, item.title),
        title=item.title,
        source_name=item.source_name,
        source_tier=item.source_tier,
        published_at=item.published_at.isoformat() if item.published_at else "unknown",
        raw_content=item.raw_content[:1000],
    )

    # Step 3: Call LLM (or injected mock)
    caller = llm_caller or _call_triage_llm
    result = caller(prompt)

    # Step 4: Validate and normalize
    significance = int(result.get("significance", 5))
    significance = max(1, min(10, significance))

    category = result.get("category", "").lower().strip()
    if category not in VALID_CATEGORIES:
        # Best-effort mapping
        for valid_cat in VALID_CATEGORIES:
            if valid_cat.replace("-", " ") in category or category in valid_cat:
                category = valid_cat
                break
        else:
            category = "research-paper"  # safe default

    rationale = result.get("rationale", "").strip() or "No rationale provided."
    suggested_headline = result.get("suggested_headline", item.title)[:80]

    # Tier promotion: Tier 2/3 with significance >= 8
    promoted = bool(result.get("promoted", False)) or (
        item.source_tier >= 2 and significance >= 8
    )

    route = _route_item(significance)

    return TriagedItem(
        item=item,
        significance=significance,
        category=category,
        rationale=rationale,
        suggested_headline=suggested_headline,
        promoted=promoted,
        route=route,
    )


def triage_batch(
    items: list[CollectedItem],
    llm_caller=None,
    max_errors: int = 3,
) -> tuple[list[TriagedItem], list[str]]:
    """
    Triage a batch of items. Returns (triaged_items, errors).
    Continues on individual item errors up to max_errors.
    """
    results = []
    errors = []

    for item in items:
        try:
            triaged = triage_item(item, llm_caller=llm_caller)
            results.append(triaged)
        except Exception as e:
            errors.append(f"{item.id} ({item.title[:40]}): {e}")
            if len(errors) >= max_errors:
                break

    return results, errors


def filter_triaged(triaged: list[TriagedItem]) -> dict[str, list[TriagedItem]]:
    """
    Split triaged items into routing buckets.
    Returns dict with keys: "archive", "roundup", "story", "lead"
    """
    buckets: dict[str, list[TriagedItem]] = {
        "archive": [],
        "roundup": [],
        "story": [],
        "lead": [],
    }
    for item in triaged:
        buckets[item.route].append(item)
    return buckets
