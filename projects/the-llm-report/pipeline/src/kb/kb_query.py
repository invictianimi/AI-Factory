"""
The LLM Report — KB-First Query Pattern
Before ANY LLM call: cache → vector → structured → assess sufficiency → LLM only if needed → cache.
NLSpec Section 4.3
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional

from pipeline.src.kb import store, vector_store, semantic_cache


@dataclass
class KBContext:
    """Assembled local context from KB sources."""
    cache_hit: bool = False
    cached_response: Optional[str] = None
    similar_items: list[dict] = field(default_factory=list)
    similar_articles: list[dict] = field(default_factory=list)
    entity_metadata: dict = field(default_factory=dict)
    is_sufficient: bool = False
    context_text: str = ""

    @property
    def cost_usd(self) -> float:
        """KB queries cost $0."""
        return 0.0


def query(
    query_text: str,
    n_results: int = 5,
    entity_names: Optional[list[str]] = None,
    cache_type: str = "factual",
    sufficiency_check: Optional[Callable[[KBContext], bool]] = None,
) -> KBContext:
    """
    Execute the KB-First Query Pattern.

    Step 1: Check semantic cache (0.92 similarity, within TTL)
    Step 2: Query vector store (top-N similar items + articles)
    Step 3: Query structured store (model specs, org info)
    Step 4: Assess sufficiency
    Step 5: Return context (caller decides whether to call LLM)

    Args:
        query_text: The query to search for
        n_results: Number of vector search results to retrieve
        entity_names: Optional list of model/org names to look up
        cache_type: "factual" (7-day TTL) or "news" (1-day TTL)
        sufficiency_check: Optional callable to determine if context is sufficient

    Returns:
        KBContext with all retrieved context. Cache hit = $0 guaranteed.
    """
    ctx = KBContext()

    # Step 1: Semantic cache check
    cached = semantic_cache.check_cache(query_text, cache_type=cache_type)
    if cached:
        ctx.cache_hit = True
        ctx.cached_response = cached
        ctx.is_sufficient = True
        return ctx

    # Step 2: Vector store search
    ctx.similar_items = vector_store.search_similar_items(query_text, n_results=n_results)
    ctx.similar_articles = vector_store.search_similar_articles(query_text, n_results=n_results)

    # Step 3: Structured store — entity metadata
    if entity_names:
        for name in entity_names:
            model_info = store.get_model_info(name)
            if model_info:
                ctx.entity_metadata[f"model:{name}"] = model_info
            org_info = store.get_org_info(name)
            if org_info:
                ctx.entity_metadata[f"org:{name}"] = org_info

    # Step 4: Assemble context text
    parts = []
    if ctx.similar_items:
        parts.append("## Related Previous Items\n")
        for item in ctx.similar_items[:3]:
            parts.append(
                f"- [{item['metadata'].get('source_name', 'Unknown')}] "
                f"{item['document'][:200]}... "
                f"(similarity: {item['similarity']:.2f})"
            )
    if ctx.similar_articles:
        parts.append("\n## Related Published Articles\n")
        for art in ctx.similar_articles[:3]:
            parts.append(
                f"- {art['document'][:200]}... "
                f"(similarity: {art['similarity']:.2f})"
            )
    if ctx.entity_metadata:
        parts.append("\n## Entity Metadata\n")
        for key, val in ctx.entity_metadata.items():
            parts.append(f"**{key}:** {val}")
    ctx.context_text = "\n".join(parts)

    # Step 4: Assess sufficiency
    if sufficiency_check:
        ctx.is_sufficient = sufficiency_check(ctx)
    else:
        # Default: sufficient if we have at least 3 highly similar results
        high_sim = [
            r for r in ctx.similar_items + ctx.similar_articles
            if r["similarity"] >= 0.85
        ]
        ctx.is_sufficient = len(high_sim) >= 3

    return ctx


def cache_llm_response(query_text: str, response: str, cache_type: str = "factual") -> None:
    """Cache an LLM response for future KB-first hits. Call after every LLM response."""
    semantic_cache.store_cache(query_text, response, cache_type=cache_type)


def format_context_for_prompt(ctx: KBContext, query_text: str) -> str:
    """
    Format KB context for injection into an LLM prompt.
    Returns the context block that goes into {kb_context} template slot.
    """
    if ctx.cache_hit:
        return f"[CACHED RESPONSE from previous similar query]\n{ctx.cached_response}"
    if not ctx.context_text:
        return "[No relevant context found in knowledge base]"
    return ctx.context_text
