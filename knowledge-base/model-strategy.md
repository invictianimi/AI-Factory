# AI Factory — Model Strategy Knowledge Base

## Model Selection Philosophy

**Core rule:** Match model capability to task complexity. Over-spending on cheap tasks is waste. Under-spending on quality-critical tasks is risk.

## Model Cost Comparison (per 1K tokens, approximate)

| Model | Input | Output | Relative Cost |
|-------|-------|--------|---------------|
| Claude Haiku 4.5 | $0.00025 | $0.00125 | 1x (baseline) |
| DeepSeek V3 | $0.00027 | $0.00110 | ~1x |
| DeepSeek R1 | $0.00055 | $0.00219 | ~2x |
| Claude Sonnet 4.5 | $0.003 | $0.015 | ~12x |
| Gemini 2.5 Pro | $0.00125 | $0.005 | ~5x |
| GPT-5.2 Pro | $0.010 | $0.030 | ~40x |
| Claude Opus 4.6 | $0.015 | $0.075 | ~60x |

## Task Routing Logic

### Cheap Tasks → Haiku/DeepSeek V3
- Collection: RSS parsing, web scraping, content hashing
- Extraction: Pulling structured data from unstructured text
- Bridge intent classification: 6-category classification
- Formatting: HTML/Markdown conversion, newsletter assembly

### Mid Tasks → Sonnet/DeepSeek R1
- Triage scoring: 4-dimension significance scoring
- Compliance checking: Rule-following against editorial guidelines
- Code review: Bug finding, edge case identification
- Daily report summary: Structured summarization with $0.05 cap

### Heavy Tasks → Opus/GPT-5.2
- Architecture: System design, milestone planning
- Analysis: Multi-source synthesis, historical context integration
- Editorial: Journalist-quality prose generation
- Board review: Strategic synthesis, adversarial review

## Anti-Patterns to Avoid

1. **Same model builds AND reviews** — Blind spots compound
2. **Opus for extraction tasks** — 60x more expensive than Haiku for no quality gain
3. **No KB context injection** — Forces LLM to explain what it already "knows"
4. **Direct API calls bypassing LiteLLM** — Breaks cost tracking and budget enforcement
5. **Skipping semantic cache** — Repeating answered questions

## Cost Optimization Stack

1. Semantic cache (0.92 similarity, 7-day TTL) → 10-20% reduction
2. KB context injection → 30-50% token reduction on analysis/editorial
3. Prompt caching (Anthropic) → 90% reduction on repeated system prompts
4. Tiered routing → 5-10x cost reduction vs. using Opus for everything
5. Local dedup ($0) → prevents re-analyzing duplicate stories
6. 4-day schedule → vs. daily, saves 3/7 = 43% of recurring costs
