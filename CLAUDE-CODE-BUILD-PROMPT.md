# CLAUDE CODE BUILD PROMPT

**Paste everything below the line into Claude Code after launching it in `/home/aifactory/AI-Factory`**

---

You are the Chief Architect of an autonomous AI Factory. Read `CLAUDE.md` first — it contains your identity, rules, model registry, directory structure, and all context.

## YOUR MISSION

Build **The LLM Report** — an autonomous AI news intelligence pipeline that produces journalist-quality content at theLLMreport.com. You will build it from the NLSpec at `projects/the-llm-report/nlspec.md` using the StrongDM Software Factory methodology: specs → code → holdout scenario testing → iterate until ≥90% pass → next milestone.

## ENVIRONMENT FACTS

- **Working directory:** `/home/aifactory/AI-Factory`
- **Git remote:** `git@github.com:invictianimi/AI-Factory.git` (private, deploy key configured)
- **Second repo for website:** `git@github.com:invictianimi/thellmreport-website.git` (create deploy key during Milestone 5)
- **API keys:** loaded in environment variables (check with `env | grep -E 'ANTHROPIC|OPENAI|DEEPSEEK|GOOGLE_API|BUTTONDOWN|PORKBUN|SMTP|X_API'`)
- **Google Drive sync:** rclone remote `gdrive:AI-Factory` — outputs/logs/docs synced every 15 min by cron
- **Transport share:** mounted at `/mnt/transport/AI-Factory` — synced by cron
- **Alert email:** aifactory.ops@outlook.com via SMTP (see CLAUDE.md for sending pattern)
- **DNS:** Porkbun API available — `PORKBUN_API_KEY` and `PORKBUN_API_SECRET` in env
- **VM specs:** Ubuntu 24, 4 vCPU, 8GB RAM, Docker installed

## BUILD SEQUENCE

Execute milestones in order. For each milestone: implement → run holdout scenarios → iterate until ≥90% pass → git commit → log to `logs/as-built.md` → proceed.

### Pre-Build: Scaffold & Infrastructure

Before Milestone 1, set up the foundation:

1. **Verify environment:** Check all API keys are present, Docker works, git push works, rclone works. Log any issues.

2. **Merge NLSpec + Addendum (CRITICAL — do this before any code):**
   - Find the existing NLSpec at `Planning/Archive MDs/ai-news-pipeline-nlspec_v6.md` and copy it to `projects/the-llm-report/nlspec.md`
   - Find the existing scenarios at `Planning/Archive MDs/ai-news-pipeline-scenarios_v6.md` and copy to `projects/the-llm-report/scenarios.md`
   - Find `NLSPEC-ADDENDUM.md` in the repo root
   - Append the entire contents of `NLSPEC-ADDENDUM.md` to the end of `projects/the-llm-report/nlspec.md`
   - The merged NLSpec now contains Sections 16-21 covering the Boss Interface (Bridge) and Autonomous Board Review systems — these are **core infrastructure**, not optional features
   - The test scenario suite now includes 22 additional scenarios (B-01 through B-12, BR-01 through BR-10) — total scenarios: 61
   - Create these directories as part of the scaffold:
     ```
     mkdir -p bridge/{inbox,outbox,processed,cli}
     mkdir -p orchestrator/config/board-prompts
     mkdir -p docs/{board-reviews/feature-proposals,directives,reports/daily}
     mkdir -p logs/bridge
     touch docs/roadmap.md docs/board-reviews/changelog.md docs/board-reviews/backlog.md
     ```
   - Verify: `wc -l projects/the-llm-report/nlspec.md` should be significantly more than 1,006 lines (original + addendum)
   - Log: "NLSpec merged with addendum. Bridge and Board Review sections integrated. 59 total test scenarios."

3. **Initialize Python project:**
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install chromadb sentence-transformers litellm feedparser beautifulsoup4 \
       requests httpx pydantic schedule python-dotenv tiktoken pytest ruff
   ```

4. **Set up LiteLLM proxy** with config from `orchestrator/config/litellm_config.yaml`. Budget caps must be active from the start.

5. **Implement orchestrator core:**
   - `orchestrator/router.py` — rule-based model routing (decision tree from CLAUDE.md)
   - `orchestrator/cost_logger.py` — every LLM call logged: model, tokens, cost, task, timestamp
   - `orchestrator/as_built.py` — append significant actions to `logs/as-built.md`
   - `orchestrator/alert.py` — send email alerts via Outlook SMTP when failures occur

6. **Set up Docker** for pipeline isolation:
   - `docker/Dockerfile` — Ubuntu 24.04 base, Python deps, Node/npm, Astro, Claude Code
   - `docker/docker-compose.yml` — factory container + LiteLLM proxy container
   - Network bridge with allowlist

7. **Git commit:** `feat: factory scaffold and orchestrator core`

### Milestone 1: Knowledge Base + Collection

Read NLSpec Section 4 (Knowledge Base) and Section 5.1 (Collection Stage).

Build:
- ChromaDB vector store with `all-MiniLM-L6-v2` embeddings (local, $0)
- SQLite structured store (models, organizations, published articles, source items, run log, cost log tables)
- Semantic cache layer (0.92 cosine threshold, 7-day TTL)
- KB-First Query Pattern implementation (cache → vector → structured → assess → LLM only if needed → cache response)
- Collection agent: RSS feeds, web scraping, GitHub API integration
- Source configuration from `config/sources.yaml` (Tier 1/2/3 sources per NLSpec Section 3)
- `content_hash` deduplication at collection level
- Regex tagging before LLM calls

**Holdout scenarios to pass (from scenarios.md):**
- Milestone 1 scenarios (fresh collection, incremental, malformed sources, GitHub API, dedup at collection)

**Git commit:** `feat(m1): knowledge base and collection agent`

### Milestone 2: Triage + Deduplication

Read NLSpec Section 5.2 (Triage) and Section 5.3 (Deduplication).

Build:
- Triage agent: significance scoring 1-10 across 4 dimensions (novelty, impact, breadth, timeliness)
- Category classification
- Tier promotion rule (Tier 2/3 stories scoring ≥8 get Tier 1 treatment)
- Vector similarity deduplication (≥0.85 cosine clustering) — local only, zero LLM cost
- Threshold filtering (configurable minimum significance)

**Holdout scenarios:** Milestone 2 scenarios from scenarios.md
**Git commit:** `feat(m2): triage agent and deduplication`

### Milestone 3: Analysis Agent + KB Integration

Read NLSpec Section 5.4 (Analysis Stage).

Build:
- Analysis agent: multi-source synthesis with KB context injection
- Cross-referencing claims across sources
- Single-source claim flagging
- Analysis section identification (separating factual reporting from thought leadership)
- Full KB-First Query Pattern integration (measure token reduction)

**Holdout scenarios:** Milestone 3 scenarios
**Git commit:** `feat(m3): analysis agent with KB integration`

### Milestone 4: Editorial + Compliance

Read NLSpec Section 5.5 (Editorial) and Section 5.6 (Compliance).

Build:
- Editorial agent: Reuters/Ars Technica register, journalist-quality prose
- Copyright compliance: no quotes >14 words, proper attribution
- Clear "Analysis" section demarcation (separate from factual reporting)
- Compliance check agent: automated legal/ethical verification
- 3-loop rewrite cycle with specific failure reasons
- Promotional language detection and rewriting

**Holdout scenarios:** Milestone 4 scenarios
**Git commit:** `feat(m4): editorial and compliance agents`

### Milestone 5: Website + Newsletter + Social + Cost Control

Three parallel workstreams:

**5A — Website (theLLMreport.com):**
- Astro static site generator
- Pages: Home, Archive, Article pages, About (with AI transparency disclosure), Subscribe, RSS feed, JSON feed
- Design: Stratechery/Pragmatic Engineer style, 680px content width, system fonts, dark mode, Lighthouse >95
- JSON-LD NewsArticle structured data on every article
- Google News sitemap + standard sitemap.xml
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- JavaScript obfuscation via `astro-obfuscator`
- SEO: entity names in headlines, internal linking from KB
- Evaluate and deploy to Vercel/Netlify/Cloudflare Pages (your choice — pick best fit)
- Generate SSH deploy key for `thellmreport-website` repo, configure auto-deploy

**5B — Newsletter (Buttondown):**
- Buttondown API integration
- Newsletter assembly from pipeline output (HTML email formatting)
- Draft mode initially (Boss reviews first few, then enables auto-send)
- CAN-SPAM/GDPR compliance via Buttondown

**5C — Social Media:**
- Substack cross-posting after Buttondown publish (website is source of truth, Substack is distribution)
- X/Twitter posting integration (if X_API keys are present in env — skip gracefully if not)
- Post format: headline + 1-line summary + link to article

**5D — Cost Control:**
- LiteLLM budget enforcement verified end-to-end
- Per-run, per-day, per-month caps active
- Anomaly detection: pause if >2× rolling average
- Cost dashboard (HTML page in outputs/)
- Alert emails when thresholds hit (50%, 80%, 100%)

**5E — DNS Configuration:**
- Use Porkbun API to configure DNS for theLLMreport.com
- Point to chosen hosting platform (CNAME or A record as needed)
- Verify HTTPS works after propagation

**Holdout scenarios:** Milestone 5 scenarios (Astro scaffold, responsive layout, newsletter API, budget enforcement, auto-deploy, security headers, SEO structured data, page performance)
**Git commit:** `feat(m5): website, newsletter, social, cost control, DNS`

### Milestone 6: Full Integration + Scheduling + E2E Validation

Build:
- Pipeline runner script (`scripts/run-pipeline.sh`) — end-to-end: collection → triage → dedup → analysis → editorial → compliance → website publish → newsletter send → social post → cost log
- Cron integration (Mon/Wed/Fri 05:00 UTC standard + Sat 06:00 UTC deep-dive)
- Graceful degradation (what happens when a source is down, an API fails, budget is hit mid-run)
- Status dashboard update after each run
- The "quiet week" handling — produce minimal but professional edition when no significant news
- Website/newsletter consistency check — same content appears in both
- Full sync verification — outputs appear in Google Drive and transport share

**Holdout scenarios:** Milestone 6 scenarios (end-to-end Monday run, Friday Tier 3 run, graceful degradation, tier promotion e2e, website/newsletter consistency)
**Git commit:** `feat(m6): full integration, scheduling, e2e validation`

### Milestone 7: Boss Interface (Bridge) + Autonomous Board Review

Read NLSpec Sections 16-21 (from the merged addendum).

**7A — Bridge CLI:**
- Build `factory` CLI tool at `bridge/cli/factory`
- Symlink to `/usr/local/bin/factory`
- Implement all commands from NLSpec Section 16.2.1: `bridge`, `status`, `status --detail`, `costs`, `schedule`, `output`, `board`, `roadmap`, `direct`, `feature`, `logs`, `pause`, `resume`, `stop`, `kill`, `rollback`
- Interactive `factory bridge` mode with status header, conversational input, and intent classification
- Intent classification via Claude Haiku (STATUS, INQUIRY, DIRECTIVE, FEATURE, OVERRIDE, EMERGENCY)
- Directive processing: config-level (immediate) vs spec-level (queue for board)

**7B — Bridge Async Channels:**
- File drop monitor: poll `bridge/inbox/` per schedule in NLSpec Section 16.2.2
- Response writer: structured responses to `bridge/outbox/`
- Email monitor: IMAP polling on aifactory.ops@outlook.com for `[BRIDGE]` subject prefix
- Email whitelist enforcement from `BRIDGE_BOSS_EMAIL_WHITELIST` env var
- Security: reject and log non-whitelisted email senders

**7C — Push Notifications:**
- Run summary email (after each pipeline run)
- Daily Operations Report: comprehensive 9-section report (see NLSpec Section 16.5.2) covering executive summary (Sonnet-generated, $0.05 cap), pipeline activity, costs/usage breakdown by model and stage, KB health, content quality, system health, board/roadmap activity, alerts/incidents, and tomorrow's outlook. All non-summary sections compiled from local data at zero LLM cost. Delivered via email + file drop + archived to `docs/reports/daily/`. Historical reports retrievable via `factory report --daily [date]`.
- Weekly report (email + file drop to outbox)
- Monthly report (email + file drop to outbox)
- Real-time alerts (budget thresholds, errors, board completions, security events)
- Alert subject format: `[AI-FACTORY] [SEVERITY] description`
- Report CLI: `factory report --daily`, `factory report --daily YYYY-MM-DD`, `factory report --daily --last N`, `factory report --weekly`, `factory report --monthly`

**7D — Autonomous Board Review System:**
- Phase 1: Automated data gathering (zero LLM cost) — compile run logs, costs, errors, quality scores, KB metrics into `board-review-input.md`
- Phase 2: Parallel individual reviews — send input + NLSpec + role-specific prompt to each board member (Opus, GPT-5.2, DeepSeek, Gemini)
- Phase 3: Synthesis — Opus as Chair reads all reviews, resolves conflicts, classifies recommendations (AUTO-IMPLEMENT / BOSS-APPROVE / DEFER)
- Phase 4: Implementation — auto-implement within authority boundaries (NLSpec Section 17.5), queue others for Boss approval via Bridge
- Phase 5: Notification — email Boss with summary, file report to `docs/board-reviews/`
- Board prompt templates in `orchestrator/config/board-prompts/` (one per role + synthesis prompt)
- Weekly schedule: Thursday 02:00, budget capped at 10% of weekly budget
- Monthly strategic review: 1st Thursday, higher budget cap (15%)
- Post-incident review: triggered automatically after emergencies

**7E — Roadmap Management:**
- Living roadmap at `docs/roadmap.md` with Now / Next / Later / Completed / Rejected sections
- Accessible via `factory roadmap` CLI commands
- Updated by board reviews, Boss directives, and automatic completion tracking

**7F — Bridge Data Persistence:**
- All Bridge interactions stored in CXDB (ChromaDB + SQLite)
- All directives logged in `docs/directives/`
- All reports archived in `docs/reports/`
- Board reviews archived in `docs/board-reviews/review-NNN/`

**Holdout scenarios:** B-01 through B-12 (Bridge + Daily Ops Report), BR-01 through BR-10 (Board Review) from scenarios.md
**Git commit:** `feat(m7): bridge interface, board review, roadmap management`

### Post-Build: First Real Run

After all 7 milestones pass:

1. Execute a real pipeline run (not test data)
2. Review the output — save to `outputs/first-edition.md`
3. Push website content to live site
4. Send first newsletter as DRAFT (Boss reviews before first auto-send)
5. Cross-post to Substack
6. Post to X/Twitter (if keys available)
7. Verify Bridge is operational: `factory status` returns valid output
8. Verify push notifications: run summary email sent after this run
9. Seed the roadmap: populate `docs/roadmap.md` with initial items
10. Log final build summary to `logs/as-built.md`
11. Email Boss: "Factory build complete. First edition ready for review. Bridge operational — run `factory bridge` to interact."

## CRITICAL RULES DURING BUILD

- **Log every significant action** to `logs/as-built.md` with timestamps
- **Track every LLM cost** via cost_logger — build phase budget ~$50
- **Git commit after every milestone** with conventional commit messages
- **Run scenarios before proceeding** — ≥90% pass rate required
- **If stuck on a problem for >30 minutes**, log what you tried, move to next task, circle back
- **If an API key is missing or invalid**, log it, skip that integration, continue with what works
- **If budget is exhausted**, log state, email Boss, stop gracefully
- **Never hardcode API keys** — always from environment variables
- **Test on real data before declaring milestone complete** — not just mocks

## YOUR FIRST COMMAND

Start by reading CLAUDE.md, then verify the environment:

```bash
# Check all keys are present
env | grep -E 'ANTHROPIC|OPENAI|DEEPSEEK|GOOGLE_API|BUTTONDOWN|PORKBUN|SMTP' | sed 's/=.*/=***/'

# Check tools
python3 --version && node --version && docker --version && git remote -v && rclone listremotes

# Check NLSpec and addendum exist
wc -l projects/the-llm-report/nlspec.md 2>/dev/null || echo "NLSpec not yet at final path — check Planning/Archive MDs/"
ls -la NLSPEC-ADDENDUM.md
```

Then begin the Pre-Build scaffold. Go.
