# AI Factory — Living Roadmap

Updated by: board reviews, Boss directives, automatic completion tracking.
Accessible via: `factory roadmap` CLI command.

Last updated: 2026-02-27

---

## Now (Active)

**Factory is LIVE and running.** Pipeline producing editions. Bridge operational.

Next scheduled run: **Saturday 2026-02-28 at 06:00 UTC** (deep-dive)

---

## Next (Queued)

- Enable auto-send in Buttondown (after Boss reviews first few editions — Boss directive required)
- **[BOSS ACTION REQUIRED]** X/Twitter: enable Read+Write in Twitter Developer Portal → regenerate access token/secret → update .env. Code is built and wired in, just needs the permission.
- **[BOSS ACTION REQUIRED]** Substack: configure RSS import in Substack settings to pull from https://thellmreport.com/rss.xml. No code needed — Substack handles it.

---

## Later (Backlog)

- Phase 2: Breaking news express path (event-driven pipeline)
- Batch API optimization (50% cost reduction on non-real-time stages)
- Multi-project expansion (pending Boss directive)
- Lighthouse >95 score verification (deploy and test)
- Google Analytics or privacy-friendly alternative
- **[LOW PRIORITY]** Switch SMTP alerts back to Outlook (smtp-mail.outlook.com:587) — currently using Gmail as working fallback. Requires enabling "Authenticated SMTP" in Microsoft account settings (https://aka.ms/smtp_auth_disabled). No urgency; Gmail is stable.

---

## Completed

### Build Phase (2026-02-25)
- **Pre-Build Scaffold**: Directory structure, NLSpec merge, orchestrator core, Docker config, Python env
- **Milestone 1**: Knowledge Base + Collection (ChromaDB, SQLite, semantic cache, KB-First Pattern, RSS/web/GitHub collector)
- **Milestone 2**: Triage + Deduplication (4-dimension scoring, tier promotion, vector similarity dedup)
- **Milestone 3**: Analysis Agent + KB Integration (multi-source synthesis, KB context injection, cache)
- **Milestone 4**: Editorial + Compliance (Reuters/Ars Technica register, copyright, 3-loop rewrite)
- **Milestone 5**: Website + Newsletter + Cost Control (Astro, Buttondown, budget gate, framework separation)
- **Milestone 6**: Full Integration + Scheduling (pipeline runner, cron, graceful degradation)
- **Milestone 7**: Bridge + Board Review (factory CLI, file drop, daily ops report, autonomous board review)
- **Post-Build**: First edition produced (2026-02-25), Bridge operational

**Total scenarios passing**: 13+11+7+21+19+9+20 = **100/100 (100%)**

### Queued Tasks Completed (2026-02-27)
- **Website live**: thellmreport.com serving via Cloudflare Pages (was already deployed, confirmed active)
- **X/Twitter publisher built**: `x_publisher.py` + wired into pipeline — posts on every edition with real articles. Blocked on Boss enabling Read+Write permissions in Twitter Developer Portal.
- **Substack**: No code needed — uses RSS import. Blocked on Boss configuring it in Substack settings.

### Bug Fixes (2026-02-27)
- **Pipeline lock**: Added `flock` to `run-pipeline.sh` — prevents duplicate concurrent runs
- **Website git push**: Cleaned duplicate SSH config entry, hardened publisher subprocess env (`GIT_SSH_COMMAND`), pending commits pushed to GitHub
- **SMTP**: Confirmed working via Gmail (smtp.gmail.com) — Outlook fallback deferred to Later backlog

---

## Rejected

*(None)*
