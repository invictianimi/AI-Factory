# AI Factory Pipeline Framework

This framework provides the domain-agnostic scaffolding for building autonomous AI content pipelines. The LLM Report is the first project built on it.

## Architecture

```
framework/          ← Domain-agnostic pipeline code
  base_stage.py     ← Abstract base class for all stages
  StageResult       ← Typed result container

stages/             ← The LLM Report specific stage implementations
  (see pipeline/src/ for actual implementations)

config/             ← Project-specific configuration
  sources.yaml      ← Source URLs and tiers
  editorial.yaml    ← Voice, compliance rules, section structure
  budget.yaml       ← Cost caps and optimization settings
```

## Stage Interface

Every pipeline stage implements `BaseStage`:

```python
from pipeline.src.framework.base_stage import BaseStage, StageResult

class MyStage(BaseStage[InputType, OutputType]):
    def process_item(self, item: InputType, **kwargs) -> OutputType:
        # 1. Query KB (KB-First Pattern)
        # 2. Call LLM if needed
        # 3. Return output
        ...
```

## Stage Contract

1. **No hardcoded brand names** — get from config
2. **No hardcoded source URLs** — get from sources.yaml
3. **No hardcoded editorial guidelines** — get from editorial.yaml
4. **KB-First Pattern** — always check cache/vector/structured store before calling LLM
5. **Injectable LLM caller** — `llm_caller` parameter for testing without real API calls
6. **Error isolation** — individual item errors never crash the batch
7. **Cost tracking** — every LLM call logged with model, tokens, cost, timestamp

## Pipeline Stages (The LLM Report)

| Stage | Module | Model | Cost |
|-------|--------|-------|------|
| Collection | `collect/collector.py` | Haiku / regex | Low |
| Triage | `triage/triage_agent.py` | Sonnet | Medium |
| Deduplication | `triage/dedup.py` | Local | $0 |
| Analysis | `analysis/analysis_agent.py` | Opus | High |
| Editorial | `editorial/editorial_agent.py` | Opus/Sonnet | High |
| Compliance | `editorial/compliance.py` | Regex | $0 |
| Publishing | `publish/` | Deterministic | $0 |

## Knowledge Base (KB) API

```python
from pipeline.src.kb import kb_query

# KB-First Pattern
ctx = kb_query.query(query_text, entity_names=["GPT-5", "OpenAI"])
if ctx.cache_hit:
    # $0 — use cached_response
    pass
elif ctx.is_sufficient:
    # $0 — use context_text
    pass
else:
    # Call LLM with ctx.context_text injected
    response = llm(prompt_with_context)
    kb_query.cache_llm_response(query_text, response)
```

## Extending to a New Project

1. Create `projects/<project-name>/config/sources.yaml`
2. Create `projects/<project-name>/config/editorial.yaml`
3. Create `projects/<project-name>/config/budget.yaml`
4. Subclass relevant `BaseStage` implementations
5. The KB, cost tracking, and orchestration layers are shared
