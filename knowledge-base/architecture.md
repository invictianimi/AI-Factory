# AI Factory — Architecture Knowledge Base

## System Architecture

### Pipeline Architecture

```
Collection → Triage → Deduplication → Analysis → Editorial → Compliance → Publishing
    ↓           ↓          ↓              ↓          ↓           ↓            ↓
  Haiku      Sonnet     Local-only    Opus/Sonnet  Opus/Sonnet  Sonnet    Deterministic
  ($cheap)   ($mid)     ($0)          ($strong)    ($strong)    ($mid)      ($0)
```

### Key Design Decisions

1. **KB-First Query Pattern** — Check local cache/vector/structured store before any LLM call
   - Reduces LLM calls by 30-50% through context injection
   - Semantic cache catches 10-20% of repeated queries
   - Prompt caching handles repeated system prompts

2. **LiteLLM Proxy as Cost Gate** — All calls routed through single proxy
   - Budget enforcement happens before calls are made
   - Cost logging is automatic and central
   - Model swapping without code changes

3. **Local-only Deduplication** — Vector similarity clustering, zero LLM cost
   - 0.85 cosine threshold for semantic dedup
   - SHA-256 content_hash for exact dedup

4. **Tier Promotion** — Tier 2/3 stories scoring ≥8 get Tier 1 treatment
   - Prevents missing "big story from small source" scenarios

### Data Flow

```
CollectedItem → KnowledgeBase → TriagedItem → DeduplicatedCluster
    → AnalyzedStory → EditedArticle → ComplianceCheckedArticle
    → WebsiteArticle + NewsletterDraft + SocialPost
```

### Storage Architecture

- **ChromaDB** (local): Vector embeddings, semantic search
- **SQLite** (local): Structured data, metadata, cost logs, run logs
- **File system**: Published articles, newsletter HTML, website files
- **Git**: Version control for all code and content

## Infrastructure Decisions

### Why Astro for Website
- Static site = zero runtime cost
- Excellent SEO out of the box
- Node ecosystem for templating
- Auto-deploy to CDN (Vercel/Netlify/CF Pages)

### Why Buttondown for Newsletter
- Free tier covers early growth
- CAN-SPAM/GDPR compliance handled
- Subscriber data never enters pipeline (privacy)
- Good API for automated publishing

### Why Docker for Isolation
- Reproducible environment
- Network allowlist enforcement
- Resource limits (4 CPU, 8GB RAM)
- Easy rollback

## Performance Characteristics

### Per-Run Resource Profile
- CPU: 1-2 cores during collection/triage; peaks during analysis
- RAM: ~2GB for ChromaDB + sentence-transformers + pipeline
- Disk: ~50MB per run (articles, logs, embeddings)
- Network: ~10MB per run (source scraping + LLM API calls)

### Expected Run Duration
- Standard run (Mon/Wed/Fri): 15-30 minutes
- Deep-dive run (Saturday): 30-45 minutes
- Board review (weekly): 20-40 minutes
