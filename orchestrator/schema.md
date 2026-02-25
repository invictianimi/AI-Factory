# AI Factory — Task Protocol Definition

## Task Schema

Every task passed between pipeline stages follows this schema:

```json
{
  "task_id": "uuid4",
  "run_id": "uuid4",
  "stage": "collection|triage|dedup|analysis|editorial|compliance|publishing",
  "task_type": "TaskType enum value",
  "input": {},
  "output": null,
  "status": "pending|in_progress|complete|failed|skipped",
  "model_used": "litellm model id or null",
  "cost_usd": 0.0,
  "input_tokens": 0,
  "output_tokens": 0,
  "created_at": "ISO8601",
  "completed_at": "ISO8601 or null",
  "error": "string or null",
  "retry_count": 0
}
```

## Stage Hand-off Protocol

1. Each stage reads its input from the previous stage's output (in-memory or SQLite queue)
2. Each stage writes its output before marking itself complete
3. Failures: retry up to 3x with exponential backoff, then mark failed + alert
4. Cost check after every LLM call — abort if budget exceeded

## Inter-Agent Handoff Files

For async handoffs (e.g., board review to main pipeline):
- Written to: `handoffs/<from_agent>_to_<to_agent>_<timestamp>.md`
- Format: structured markdown with YAML front-matter
- Processed then archived with timestamp suffix

## Bridge Task Protocol

Boss directives received via Bridge are classified and queued:
- `config-level`: immediate implementation by orchestrator
- `spec-level`: added to board backlog for next review cycle
- All logged in `docs/directives/`
