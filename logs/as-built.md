# AI Factory — As-Built Log

Living record of all actions, decisions, and build progress.
Append-only. Never delete entries.

---

## 2026-02-25

### Session Start

**Time:** 2026-02-25T00:00 UTC
**Session:** First build session — Pre-Build scaffold

**Environment check:**
- All API keys present: ANTHROPIC, OPENAI, DEEPSEEK, GOOGLE_API, BUTTONDOWN, PORKBUN, SMTP, X_API, ALERT, BRIDGE
- Python 3.12.3 ✓
- Node v20.20.0 ✓
- Docker 28.2.2 ✓
- Git remote: git@github.com-factory:invictianimi/AI-Factory.git ✓ (push verified)
- rclone: gdrive: remote configured ✓
- Sync log shows transport sync working, git push was skipped (nothing to push at scaffold stage)

### Pre-Build: Scaffold

**Action:** Created directory structure per CLAUDE.md spec:
- projects/the-llm-report/{pipeline/src, website, newsletter, social, config, data/chroma, outputs}
- orchestrator/config/board-prompts
- bridge/{inbox, outbox, processed, cli}
- docs/{board-reviews/feature-proposals, directives, reports/daily}
- logs/bridge, tasks, handoffs, outputs, context, knowledge-base

**Action:** NLSpec merged with addendum:
- Copied Planning/Archive MDs/ai-news-pipeline-nlspec_v6.md → projects/the-llm-report/nlspec.md
- Copied Planning/Archive MDs/ai-news-pipeline-scenarios_v6.md → projects/the-llm-report/scenarios.md
- Appended NLSPEC-ADDENDUM.md to nlspec.md
- Result: 1,574 lines (1,006 original + 568 addendum) ✓
- NLSpec now includes Sections 16-21 covering Bridge and Board Review systems

**Action:** Created project config files: sources.yaml, budget.yaml, editorial.yaml

**Action:** Created as-built.md (this file), cost-log.md

**Status:** Pre-Build scaffold in progress — Python venv next

---

### Pre-Build: Python Environment

**Action:** Created .venv and installed dependencies:
- chromadb, sentence-transformers, litellm, feedparser, beautifulsoup4
- requests, httpx, pydantic, schedule, python-dotenv, tiktoken, pytest, ruff

---

### Pre-Build: Orchestrator Core

**Action:** Built orchestrator core modules:
- orchestrator/router.py — rule-based model routing (decision tree from CLAUDE.md)
- orchestrator/cost_logger.py — every LLM call logged: model, tokens, cost, task, timestamp
- orchestrator/as_built.py — append significant actions to logs/as-built.md
- orchestrator/alert.py — send email alerts via Outlook SMTP
- orchestrator/config/models.yaml — model registry
- orchestrator/config/litellm_config.yaml — LiteLLM proxy config with budget enforcement

---

### Pre-Build: Docker

**Action:** Created Docker configuration:
- docker/Dockerfile — Ubuntu 24.04 base, Python deps, Node/npm
- docker/docker-compose.yml — factory container + LiteLLM proxy container with network allowlist

---

### Pre-Build: Git Commit

**Action:** git commit: feat: factory scaffold and orchestrator core

---

**[INFO 2026-02-25T06:40:42+00:00]** Orchestrator import test passed
