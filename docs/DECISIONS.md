# ARCHITECTURAL DECISIONS LOG

All major decisions recorded here with context and reasoning.

---

## ADR-001: Build The LLM Report THROUGH the orchestrator
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Don't build the general AI Factory platform first. Build The LLM Report as the first factory project through the orchestration layer. This validates both simultaneously.
**Reasoning:** Avoids abstracting in a vacuum. Orchestrator becomes real infrastructure tested by real work.

## ADR-002: Claude Code initially → evolve to fully autonomous
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Start with Claude Code as orchestrator (Option B), evolve toward standalone Python service (Option C). Prefer local infrastructure, markdown files, local services over paid MCP/APIs.
**Components:** Lightweight Python orchestrator, Git-based task queue, SQLite + ChromaDB, LiteLLM proxy local.

## ADR-003: 4 newsletters per week
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Mon/Wed/Fri standard editions + Saturday deep-dive. Cron-triggered until revenue justifies event-driven.
**Cost impact:** ~16 runs/month, $47-130/month LLM estimated.

## ADR-004: Attractor from day one
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Fork amolstrongdm Python implementation as pipeline execution engine. DOT-graph definitions, multi-agent orchestration, satisfaction scoring.

## ADR-005: CXDB + Leash from day one
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** CXDB (Rust/Go) for immutable DAG audit trail. Leash (Go) wraps all agent execution with Cedar policies.
**Impact:** VM minimum 4 vCPU, 8GB RAM.

## ADR-006: Website hosting — agent decides
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** NLSpec stands — coding agent evaluates Vercel/Netlify/Cloudflare Pages and picks the best fit.

## ADR-007: Substack from day one
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Cross-post after Buttondown publish. Website is source of truth, Substack is distribution channel.

## ADR-008: Google Drive (personal) + Outlook (factory)
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Use invicti.animi@gmail.com Google Drive with dedicated AI-Factory folder for Claude.ai bridge sync. Use aifactory.ops@outlook.com for factory alert emails via SMTP.
**Reasoning:** Cannot create new Google accounts (phone verification limit). Personal GDrive preserves Claude.ai native search capability. Outlook provides clean factory email without Google dependency.

## ADR-009: Porkbun API for DNS, NOT Porkbun hosting
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Enable Porkbun API for programmatic DNS management. Do NOT use Porkbun web hosting. DNS points to chosen hosting platform (Vercel/Netlify/CF Pages).

## ADR-011: Dedup threshold 0.82 (not 0.85 as NLSpec specified)
**Date:** 2026-02-25
**Status:** ACCEPTED
**Decision:** Use 0.82 cosine similarity threshold for story deduplication instead of NLSpec-specified 0.85.
**Reasoning:** Empirically tested all-MiniLM-L6-v2 on realistic same-story article pairs (GPT-5.3 release covered by OpenAI Blog, TechCrunch, The Verge). Observed similarities of 0.831-0.849 — below 0.85 but genuinely the same story. Threshold 0.82 correctly clusters same-story items while maintaining separation from unrelated stories (e.g., A vs C = 0.24). NLSpec was written before empirical model testing.

## ADR-010: Security as Tier 1 priority
**Date:** 2026-02-24
**Status:** ACCEPTED
**Decision:** Private repos, deploy keys (not PATs), .env for secrets, Docker isolation, network allowlist, budget caps, full audit trail, quarterly key rotation.
