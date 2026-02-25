# AI Factory

Private autonomous AI Factory. Multi-model orchestration platform built using the StrongDM Software Factory methodology.

**First project:** [The LLM Report](https://theLLMreport.com) — autonomous AI news intelligence pipeline.

## Quick Start

See `docs/BOSS-SETUP-GUIDE.md` for complete setup instructions.

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Master context — Claude Code reads this first every session |
| `CLAUDE-CODE-BUILD-PROMPT.md` | Paste into Claude Code to kick off the build |
| `docs/BOSS-SETUP-GUIDE.md` | Human setup guide (one-time, 2-4 hours) |
| `docs/EMERGENCY-PROCEDURES.md` | Pause, stop, kill, rollback procedures |
| `docs/DECISIONS.md` | Architectural decision log |
| `projects/the-llm-report/nlspec.md` | Master specification (1,006 lines) |
| `projects/the-llm-report/scenarios.md` | 39 holdout test scenarios |

## Architecture

```
Boss (Vit) → Claude Code → Orchestrator → LLM Pool → Pipeline → Publish
                              ↓
                    Router | Logger | Budget
                              ↓
              Claude Opus | Sonnet | Haiku | GPT-5.2 | DeepSeek | Gemini
```

## Status

**Phase:** Pre-build — scaffold and specs ready, awaiting Claude Code launch.
