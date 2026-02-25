# NLSpec Addendum — Boss Interface & Autonomous Board Review

**Append this entire document to the end of `ai-news-pipeline-nlspec_v6.md` (before any closing sections or appendices). These sections become part of the authoritative NLSpec that Claude Code treats as the single source of truth.**

---

## Section 16: Boss Interface (The Bridge)

### 16.1 Purpose

The Bridge is the Boss's command interface into the running factory. It provides status visibility, conversational interaction, and strategic steering without interrupting autonomous operation. The factory MUST be fully observable and steerable by the Boss at all times.

### 16.2 Access Methods

The Bridge MUST support exactly three access methods. All three methods MUST produce equivalent results for equivalent inputs.

#### 16.2.1 CLI Access (Primary)

The factory MUST provide a `factory` CLI tool installed at `/usr/local/bin/factory` on Ubuntu-1. The CLI MUST be usable over SSH from the Boss's Windows host via PuTTY.

The CLI MUST support two modes:

**Interactive mode** — Invoked via `factory bridge`. Opens a persistent conversational session. The factory MUST display a status header on session start showing: current operational state (RUNNING, PAUSED, STOPPED, ERROR), pipeline state (IDLE, RUNNING with current stage, QUEUED), last run timestamp and outcome, next scheduled run timestamp, current period spend vs budget, and articles published in current period. The session MUST accept natural language input from the Boss and respond conversationally. The session MUST remain open until the Boss types `exit` or `quit`. The factory MUST NOT terminate the session on its own.

**Command mode** — Single-command invocations that return output and exit. The following commands MUST be supported:

- `factory status` — Returns: operational state, pipeline state, last run summary, next run time, spend vs budget. Output MUST fit in one terminal screen (< 25 lines).
- `factory status --detail` — Returns everything in `factory status` plus: per-stage breakdown of last run (duration, cost, errors), per-model API usage for current period, knowledge base size metrics, and pending Boss-approval items.
- `factory costs --period <daily|weekly|monthly>` — Returns: total spend, spend by model, spend by pipeline stage, spend by task type, comparison to budget cap, comparison to previous period. Output MUST be a formatted table.
- `factory schedule` — Returns: next 7 days of scheduled pipeline runs with edition types.
- `factory output --latest` — Returns: title, summary, word count, quality score, publication channels, and URLs for the most recently published article.
- `factory output --list [N]` — Returns: titles and dates of last N published articles (default 10).
- `factory board --latest` — Returns: summary of most recent board review including findings implemented, findings pending Boss approval, and findings deferred.
- `factory board --history` — Returns: list of all board reviews with dates, finding counts, and implementation status.
- `factory roadmap` — Returns: full current roadmap organized by Now / Next / Later / Completed / Rejected sections.
- `factory roadmap --now` — Returns: only the Now section.
- `factory roadmap --next` — Returns: only the Next section.
- `factory roadmap --backlog` — Returns: only the Later section.
- `factory direct "<message>"` — Submits a Boss directive. Returns: acknowledgment with classification (config-level or spec-level) and planned action.
- `factory feature "<description>"` — Submits a feature request. Returns: acknowledgment with initial impact assessment and where it was queued.
- `factory logs --tail <N>` — Returns: last N log entries from the main operational log.
- `factory logs --stage <stage-name> --today` — Returns: today's log entries filtered to the specified pipeline stage. Valid stage names: collection, triage, analysis, editorial, compliance, publishing.
- `factory logs --errors --today` — Returns: today's error log entries across all stages.
- `factory pause` — Pauses the current pipeline run. Preserves state. Returns: confirmation with paused-at stage.
- `factory resume` — Resumes a paused pipeline run. Returns: confirmation with resuming-from stage.
- `factory stop` — Initiates graceful shutdown. Completes current stage, saves state, stops. Returns: confirmation.
- `factory kill` — Immediate termination of all factory processes. Returns: confirmation. MUST log the kill event.
- `factory rollback` — Reverts to last known good state. Returns: confirmation with what was rolled back. MUST require a confirmation prompt before executing: "This will revert to state from [timestamp]. Type YES to confirm."

All CLI commands MUST exit with code 0 on success and non-zero on failure. All CLI commands MUST complete within 30 seconds for non-interactive mode (except `factory bridge`). If an LLM call is required to generate a response (e.g., for conversational Bridge sessions or complex inquiries), the CLI MUST display a brief "Processing..." indicator.

#### 16.2.2 File Drop Access (Async)

The factory MUST monitor the directory `/home/aifactory/AI-Factory/bridge/inbox/` for new files. On the Windows host, this directory is accessible at `\\vitsim\transport\AI-Factory\bridge\inbox\` via the existing SMB share.

**Polling frequency:** The factory MUST check the inbox at least once every 15 minutes during active hours (06:00-22:00 local time) and at least once every 60 minutes during off-hours.

**File format:** The factory MUST accept markdown files (.md) with the naming convention:
```
YYYY-MM-DD-HH-MM-<type>-<short-description>.md
```

Valid types: `status`, `inquiry`, `directive`, `feature`, `override`.

The file contents MUST be treated as natural language input from the Boss, equivalent to typing the same text in an interactive Bridge session.

**Response delivery:** The factory MUST write response files to `/home/aifactory/AI-Factory/bridge/outbox/` (accessible at `\\vitsim\transport\AI-Factory\bridge\outbox\` via SMB). Response files MUST use the naming convention:
```
YYYY-MM-DD-HH-MM-response-to-<original-filename>.md
```

**Cleanup:** After processing, the factory MUST move the original inbox file to `/home/aifactory/AI-Factory/bridge/processed/` with a timestamp prefix. The factory MUST NOT delete inbox files.

**Error handling:** If a file cannot be parsed or processed, the factory MUST write an error response to the outbox explaining the issue and MUST NOT discard the original file.

#### 16.2.3 Email Access (Async)

The factory MUST monitor the `aifactory.ops@outlook.com` inbox via IMAP for messages with subject lines starting with `[BRIDGE]`.

**Polling frequency:** Same as file drop — every 15 minutes during active hours, every 60 minutes off-hours.

**Subject line format:** `[BRIDGE] [<TYPE>] <description>`

Valid types: `STATUS`, `INQUIRY`, `DIRECTIVE`, `FEATURE`, `OVERRIDE`.

The email body MUST be treated as natural language input from the Boss.

**Response delivery:** The factory MUST reply to the original email thread with its response. The reply MUST include the original message quoted below the response.

**Security:** The factory MUST only process `[BRIDGE]` emails from addresses explicitly whitelisted in the factory configuration. The initial whitelist MUST include only the Boss's personal email address(es) as configured in `.env`. Emails from non-whitelisted addresses MUST be ignored and logged as security events.

### 16.3 Intent Classification

The Bridge processor MUST classify every Boss input into one of the following intent classes before routing:

| Intent | Description | Handler |
|--------|-------------|---------|
| STATUS | Request for operational information | Status Reporter — queries logs, metrics, CXDB |
| INQUIRY | Question about any aspect of operations, content, or architecture | Knowledge Query Engine — searches CXDB, logs, docs |
| DIRECTIVE | Strategic guidance that changes factory behavior | Directive Processor — impact assessment, routing |
| FEATURE | Request for new functionality | Feature Request Pipeline — assessment, queuing |
| OVERRIDE | Request to change a Leash constraint or safety boundary | Override Handler — requires explicit confirmation |
| EMERGENCY | Pause, stop, kill, or rollback request | Emergency Procedures (existing system) |

**Classification model:** The Bridge MUST use Claude Haiku for intent classification. If confidence is below 80%, the Bridge MUST ask the Boss for clarification rather than guessing.

**Logging:** Every Bridge interaction MUST be logged in `logs/bridge/` with timestamp, access method, intent classification, input text, response text, and any actions taken.

### 16.4 Directive Processing

When the Boss issues a DIRECTIVE, the Bridge MUST:

1. Acknowledge receipt immediately (< 5 seconds for CLI, next polling cycle for async methods).
2. Perform an impact assessment using Claude Opus. The assessment MUST classify the directive as:
   - **CONFIG-LEVEL** — Can be implemented by changing configuration files, model routing, source lists, scheduling, or other non-code parameters. These MUST be implemented immediately, logged, and confirmed to the Boss.
   - **SPEC-LEVEL** — Requires changes to pipeline logic, new features, new integrations, or editorial standards changes. These MUST be queued for the next board review, with a preliminary design brief generated for Boss review.
3. Log the directive, classification, and action taken in `docs/directives/`.
4. Confirm the action to the Boss via the same access method used to submit the directive.

The factory MUST NOT implement spec-level changes without a board review cycle, even if the Boss says "just do it." The Bridge MUST explain that the board review ensures quality and can offer to expedite the review to the next available slot.

### 16.5 Automatic Status Reports (Push Notifications)

The factory MUST push the following reports to the Boss without being asked:

#### 16.5.1 Run Summary
- **Trigger:** Completion of every pipeline run (success or failure)
- **Delivery:** Email to Boss
- **Content:** Edition type, articles produced (titles + word counts), total run cost, per-stage duration, quality scores, any errors or compliance flags, publication URLs

#### 16.5.2 Daily Digest
- **Trigger:** Daily at 20:00 local time
- **Delivery:** Email to Boss
- **Content:** Day's pipeline runs (count, outcomes), cumulative daily cost vs budget, articles published, notable events (errors, board actions, directive responses), tomorrow's schedule

#### 16.5.3 Weekly Report
- **Trigger:** Sunday at 20:00 local time
- **Delivery:** Email to Boss AND file drop to `bridge/outbox/`
- **Content:** All daily digest data aggregated for the week, board review summary (if one occurred), cost trend (this week vs last week), content quality trend, knowledge base growth metrics, roadmap status, open items requiring Boss attention

#### 16.5.4 Monthly Report
- **Trigger:** 1st of each month at 20:00 local time
- **Delivery:** Email to Boss AND file drop to `bridge/outbox/`
- **Content:** Full month in review: total costs with trend analysis, content performance metrics, subscriber growth (once live), board review summaries for the month, optimization gains quantified, roadmap progress assessment, next month's priorities (proposed by board, pending Boss confirmation)

#### 16.5.5 Real-Time Alerts
- **Trigger:** Any of the following events
- **Delivery:** Email to Boss (immediate)
- **Events that trigger alerts:**
  - Budget threshold breached (70%, 90%, 100% of daily/weekly/monthly)
  - Pipeline stage failure (after retry exhaustion)
  - Compliance rejection (article failed compliance checks)
  - Board review completed
  - Leash circuit breaker triggered
  - Security event (unauthorized access attempt, unexpected network activity)
  - Boss directive or feature request processed
  - Override request awaiting confirmation

**Alert format:** Subject line MUST include severity level and event type:
```
[AI-FACTORY] [WARNING] Daily budget at 70% — $10.50 / $15.00
[AI-FACTORY] [ERROR] Editorial stage failure — article "Title" failed quality gate
[AI-FACTORY] [INFO] Board Review #5 completed — 3 optimizations implemented
[AI-FACTORY] [CRITICAL] Circuit breaker triggered — all operations paused
```

### 16.6 Bridge Data Storage

All Bridge interactions, directives, reports, and feature requests MUST be stored in the CXDB so that:
- The factory can reference previous Boss instructions in future interactions
- Board reviews can see the full history of Boss directives
- The Bridge can answer questions like "What did I ask for last week?"
- Audit trail is complete

---

## Section 17: Autonomous Board Review System

### 17.1 Purpose

The board of directors is a multi-model review system that continuously improves the factory's operations, efficiency, and quality. The board operates autonomously on a defined schedule, implements optimizations within its authority, and escalates changes beyond its authority to the Boss via the Bridge.

### 17.2 Board Composition

The board MUST consist of exactly four members:

| Seat | Model | Role Title | Primary Focus |
|------|-------|-----------|---------------|
| Chair | Claude Opus | Lead Architect | Architecture coherence, quality standards, synthesis, final implementation decisions |
| Seat 2 | GPT-5.2 (OpenAI) | Adversarial Reviewer | Assumptions, blind spots, failure modes, stress-testing |
| Seat 3 | DeepSeek | Cost & Efficiency Auditor | API spend optimization, model routing efficiency, waste detection, performance |
| Seat 4 | Gemini | Integration & Systems Reviewer | External integrations, data flow, bottlenecks, scalability, multimodal gaps |

**Model substitution:** If a board member's API is unavailable during a scheduled review, the review MUST proceed with the remaining members. The unavailable member's review focus MUST be partially absorbed by the Chair. The review report MUST note which members participated. If fewer than 2 members are available (including the Chair), the review MUST be rescheduled to the next day at the same time and the Boss MUST be notified.

**The Chair (Claude Opus) MUST participate in every review.** If Opus is unavailable, the review MUST be rescheduled.

### 17.3 Review Schedule

#### 17.3.1 Weekly Operational Review
- **When:** Every Thursday at 02:00 local time
- **Rationale:** No publication runs on Thursday. Off-peak API rates. Results available before Friday's edition.
- **Budget cap:** The total cost of a weekly review (all API calls across all members + synthesis) MUST NOT exceed 10% of the weekly operating budget. If the review approaches this cap, it MUST conclude with whatever analysis is complete.
- **Duration cap:** The entire review process (data gathering through notification) MUST complete within 4 hours.

#### 17.3.2 Monthly Strategic Review
- **When:** First Thursday of each month at 02:00 local time (replaces that week's operational review)
- **Budget cap:** 15% of weekly operating budget (higher than operational review due to broader scope)
- **Duration cap:** 6 hours
- **Additional scope:** Competitive landscape, roadmap assessment, scaling recommendations, resource allocation

#### 17.3.3 Post-Incident Review
- **When:** Within 24 hours of any emergency event (circuit breaker, kill, rollback, or security incident)
- **Budget cap:** Draws from daily budget emergency reserve
- **Duration cap:** 2 hours
- **Scope:** Root cause analysis, corrective actions, prevention measures

### 17.4 Review Process

The board review MUST proceed through exactly five phases in order:

#### Phase 1: Data Gathering (Automated — Zero LLM Cost)

The factory MUST compile the following data into a structured input document (`board-review-input.md`) without making any LLM API calls:

- Pipeline run logs for the review period (timestamps, durations, outcomes per stage)
- Cost data: total spend, spend by model, spend by stage, spend by task type
- Error logs: all errors and warnings with context
- Content quality scores: per-article scores, trend data
- Compliance events: any rejections, revisions, flags
- Knowledge base metrics: document count, query count, cache hit rate
- Pending Boss directives and feature requests
- Previous review's implementation status (what was done, what's outstanding)
- For monthly reviews: subscriber metrics, content performance analytics, competitive signals
- For post-incident reviews: incident timeline, affected systems, immediate actions taken

**Data format:** The input document MUST use structured markdown with clear section headers and data tables. Raw log data MUST be summarized into relevant metrics — do not send raw log files to the board members.

#### Phase 2: Individual Reviews (Parallel)

Each board member MUST receive:
1. The compiled `board-review-input.md`
2. The current NLSpec (relevant sections, not the full 1000+ lines — the Chair determines which sections are relevant)
3. A role-specific review prompt from `orchestrator/config/board-prompts/<role>.md`
4. The previous review's synthesis document (for continuity)

Each member MUST produce a structured review document containing:
- **FINDINGS:** Observations backed by specific data points from the input
- **RECOMMENDATIONS:** Proposed changes with rationale, expected impact, and implementation steps
- **PRIORITY:** Each recommendation classified as Critical / High / Medium / Low
- **RISKS:** What could go wrong if the recommendation is implemented
- **DISSENT:** Areas where this member disagrees with previous review decisions (if any)

**Parallelism:** All four member reviews SHOULD be submitted in parallel (concurrent API calls) to minimize wall-clock time. The factory MUST NOT wait for one member to complete before starting another.

**Individual review budget:** Each member's review MUST NOT exceed 25% of the total review budget cap. If a member's review approaches its budget, the API call MUST be concluded with whatever analysis is complete.

#### Phase 3: Synthesis (Chair Only)

Claude Opus as Chair MUST:

1. Read all individual review documents
2. Identify areas of consensus (2+ members agree)
3. Identify areas of conflict (members disagree) and resolve them with documented reasoning
4. Classify every recommendation into one of three categories:

| Category | Criteria | Action |
|----------|----------|--------|
| **AUTO-IMPLEMENT** | Meets ALL autonomous authority criteria (see 17.5) | Claude Code implements immediately |
| **BOSS-APPROVE** | Exceeds at least one autonomous authority criterion | Queued in Bridge for Boss review |
| **DEFER** | Not actionable now, or low priority relative to current workload | Added to backlog with rationale and suggested revisit date |

5. Produce a synthesis document (`board-review-synthesis.md`) containing: executive summary (3-5 sentences), consensus findings, resolved conflicts with reasoning, categorized recommendations with implementation plans, updated risk register, and next review focus areas.

#### Phase 4: Implementation

**AUTO-IMPLEMENT items:** Claude Code MUST implement each approved change, verify it works (run relevant test scenarios), and log the change in the changelog. If implementation fails or tests fail, the change MUST be rolled back and reclassified as BOSS-APPROVE with an explanation of the failure.

**BOSS-APPROVE items:** The factory MUST create a structured approval request for each item and queue it in the Bridge. The request MUST include: what the board recommends, why, expected impact, implementation plan, risks, and which board members supported it.

**DEFER items:** The factory MUST add each item to `docs/board-reviews/backlog.md` with: description, rationale for deferral, which member(s) proposed it, suggested revisit date, and priority if revisited.

#### Phase 5: Notification

The factory MUST notify the Boss via email (and file drop for weekly/monthly reviews) with:

- Review type and date
- Participating members
- **Auto-implemented changes:** What changed, before/after comparison, test results
- **Items awaiting Boss approval:** Summary of each with the board's recommendation
- **Deferred items:** Brief list with rationale
- Link to full review documents in `docs/board-reviews/`

The notification email subject MUST follow the format:
```
[AI-FACTORY] [INFO] Board Review #NNN Complete — X implemented, Y pending approval
```

### 17.5 Autonomous Authority Boundaries

The board MAY auto-implement a change (without Boss approval) if and only if ALL of the following criteria are met:

1. **Cost impact:** The change either reduces costs OR increases costs by less than 5% of the current weekly budget.
2. **Behavior impact:** The change does NOT alter editorial voice, content quality standards, publication schedule, publication channels, or any reader-facing content format.
3. **Reversibility:** The change can be fully rolled back within 5 minutes with zero data loss. The rollback procedure MUST be documented before implementation.
4. **Scope:** The change affects configuration, model routing weights, triage scoring parameters, source lists, caching behavior, KB indexing, retry logic, or similar operational parameters. The change does NOT modify core pipeline stage logic, add/remove pipeline stages, or alter the Bridge or Board Review systems themselves.
5. **Risk:** The change has no security implications (no credential changes, no new network access, no permission changes), no external-facing impact beyond content quality improvements, and no new external integrations.
6. **Consensus:** At least 2 board members (including the Chair) support the change. The Chair has veto power — if the Chair opposes, the change MUST go to BOSS-APPROVE regardless of other members' support.

**If any single criterion is not met, the change MUST be classified as BOSS-APPROVE.**

**The board MUST NEVER:**
- Modify its own review schedule, budget caps, or authority boundaries
- Change the Boss's access methods or notification settings
- Alter security configurations or credential management
- Add new external service integrations
- Modify the Leash's hard safety constraints
- Change budget caps (daily, weekly, monthly)
- Override a previous Boss decision without Boss approval

### 17.6 Board Prompt Management

Review prompts for each board member MUST be stored in `orchestrator/config/board-prompts/`:

```
orchestrator/config/board-prompts/
├── chair-opus.md           # Chair review prompt template
├── adversarial-gpt.md      # Adversarial reviewer prompt template
├── cost-auditor-deepseek.md # Cost auditor prompt template
├── integration-gemini.md   # Integration reviewer prompt template
└── synthesis.md            # Synthesis phase prompt template
```

Each prompt MUST include:
- Role identity and focus area
- Specific review questions (minimum 5 per role)
- Required output format
- Examples of good findings vs vague findings
- Reference to autonomous authority boundaries
- Instruction to be specific and evidence-based (no vague "consider improving X" recommendations)

The board MUST NOT modify its own prompts. Prompt modifications require Boss approval via a DIRECTIVE.

### 17.7 Review Documentation

All board review artifacts MUST be stored in `docs/board-reviews/`:

```
docs/board-reviews/
├── review-001/
│   ├── input.md                 # Compiled operational data
│   ├── review-chair-opus.md     # Chair's individual review
│   ├── review-adversarial-gpt.md
│   ├── review-cost-deepseek.md
│   ├── review-integration-gemini.md
│   ├── synthesis.md             # Chair's synthesis
│   └── implementation-log.md    # What was actually done
├── review-002/
│   └── ...
├── feature-proposals/           # Board-proposed features
│   ├── company-tracker.md
│   └── ...
├── changelog.md                 # Running log of all board changes
└── backlog.md                   # Deferred items
```

**Changelog format:** Each entry MUST include: date, review number, change description, category (auto-implemented/boss-approved), before state, after state, proposing member(s), and test result.

**Retention:** Board review documents MUST be retained indefinitely. They MUST be included in Google Drive backups.

### 17.8 Continuous Learning

The board review system MUST improve over time:

- **Review quality tracking:** The Chair MUST assess at each review whether previous recommendations achieved their expected impact. Track: recommendations made, recommendations implemented, recommendations that achieved expected outcome, recommendations that failed or had unexpected side effects.
- **Prompt refinement requests:** If the board identifies that its review prompts are producing low-quality or vague output, it MUST submit a BOSS-APPROVE request to update the prompts, including proposed new prompt text and rationale.
- **Metric evolution:** The data gathering phase MUST evolve as new metrics become available. When a new metric is added to the factory (e.g., subscriber count after launch), the data gathering phase MUST be updated to include it. These updates are CONFIG-LEVEL and can be auto-implemented.

---

## Section 18: Roadmap Management

### 18.1 Purpose

The factory MUST maintain a living roadmap at `docs/roadmap.md` that tracks all planned, in-progress, completed, and rejected work items. The roadmap is the shared strategic view between the Boss and the board.

### 18.2 Roadmap Structure

The roadmap MUST be organized into exactly five sections:

```markdown
# AI Factory Roadmap
## Last Updated: [timestamp]

## Now (In Progress)
[Items actively being built or implemented this cycle]

## Next (Queued — Priority Order)
[Items approved and ready, ordered by priority. Top item starts when current Now items complete.]

## Later (Backlog)
[Items identified but not yet prioritized. May be proposed by Boss or board.]

## Completed
[Items shipped. Each entry includes: date completed, review number if board-driven, brief outcome.]

## Rejected / Retired
[Items considered and declined. Each entry includes: date rejected, rationale, who proposed it.]
```

### 18.3 Roadmap Updates

The roadmap MUST be updated by:

1. **Board reviews** — The board MAY propose new items for Later. The board MAY move items from Later to Next if they are approved via the review process. The board MUST NOT move items to Now without Boss approval (since Now items consume build resources).
2. **Boss directives** — The Boss MAY add items to any section, move items between sections, reprioritize items within sections, and reject/retire items.
3. **Automatic completion** — When an item in Now is completed (verified by tests), the factory MUST move it to Completed with a timestamp and outcome summary.

**Conflict resolution:** If the Boss and the board disagree on priority, the Boss's directive takes precedence. The board MAY note its dissent in the next review but MUST implement the Boss's priority ordering.

### 18.4 Roadmap Access

The roadmap MUST be accessible via:
- `factory roadmap` (CLI — full roadmap)
- `factory roadmap --now / --next / --backlog` (CLI — filtered sections)
- Interactive Bridge session ("What's on the roadmap?")
- File: `docs/roadmap.md` (directly readable on disk or via SMB share)
- Included in weekly and monthly status reports

---

## Section 19: Directory Structure Additions

The following directories and files MUST be added to the factory directory structure to support the Bridge and Board Review systems:

```
/home/aifactory/AI-Factory/
├── bridge/
│   ├── inbox/                         # Boss drops message files here
│   ├── outbox/                        # Factory writes response files here
│   ├── processed/                     # Processed inbox files moved here
│   └── cli/
│       └── factory                    # CLI tool (symlinked to /usr/local/bin/factory)
├── orchestrator/
│   └── config/
│       └── board-prompts/
│           ├── chair-opus.md
│           ├── adversarial-gpt.md
│           ├── cost-auditor-deepseek.md
│           ├── integration-gemini.md
│           └── synthesis.md
├── docs/
│   ├── board-reviews/
│   │   ├── changelog.md
│   │   ├── backlog.md
│   │   └── feature-proposals/
│   ├── directives/                    # Log of all Boss directives
│   ├── reports/                       # Archived status reports
│   └── roadmap.md                     # Living roadmap
├── logs/
│   └── bridge/                        # Bridge interaction logs
└── ...
```

---

## Section 20: Configuration Additions

The following environment variables MUST be added to `.env` to support the Bridge and Board Review systems:

```bash
# Bridge Configuration
BRIDGE_INBOX_POLL_INTERVAL_ACTIVE=900      # Seconds between inbox checks during active hours (default 900 = 15 min)
BRIDGE_INBOX_POLL_INTERVAL_INACTIVE=3600   # Seconds between inbox checks during off-hours (default 3600 = 60 min)
BRIDGE_ACTIVE_HOURS_START=06:00            # Start of active hours (local time)
BRIDGE_ACTIVE_HOURS_END=22:00              # End of active hours (local time)
BRIDGE_BOSS_EMAIL_WHITELIST=boss@example.com  # Comma-separated list of Boss email addresses for [BRIDGE] email processing

# Board Review Configuration
BOARD_REVIEW_WEEKLY_DAY=thursday           # Day of week for operational review
BOARD_REVIEW_WEEKLY_TIME=02:00             # Time for operational review (local)
BOARD_REVIEW_WEEKLY_BUDGET_PCT=10          # Max percentage of weekly budget for operational review
BOARD_REVIEW_MONTHLY_BUDGET_PCT=15         # Max percentage of weekly budget for monthly review
BOARD_REVIEW_DURATION_CAP_WEEKLY=240       # Max duration in minutes for weekly review
BOARD_REVIEW_DURATION_CAP_MONTHLY=360      # Max duration in minutes for monthly review
BOARD_AUTO_IMPLEMENT_COST_THRESHOLD_PCT=5  # Max cost increase (% of weekly budget) for auto-implementation

# Push Notification Configuration
PUSH_DAILY_DIGEST_TIME=20:00              # Time for daily digest email (local)
PUSH_WEEKLY_REPORT_DAY=sunday             # Day for weekly report
PUSH_WEEKLY_REPORT_TIME=20:00             # Time for weekly report (local)
PUSH_MONTHLY_REPORT_DAY=1                 # Day of month for monthly report
PUSH_MONTHLY_REPORT_TIME=20:00            # Time for monthly report (local)
```

---

## Section 21: Test Scenarios — Bridge & Board Review

The following test scenarios MUST be added to the scenario holdout suite. They validate the Bridge and Board Review systems.

### Bridge Scenarios (B-01 through B-10)

**B-01: CLI Status Command**
Given the factory is running with at least one completed pipeline run, when the Boss executes `factory status`, then the output MUST display current state, last run summary, next run time, and spend vs budget, and MUST complete within 5 seconds.

**B-02: Interactive Bridge Session**
Given the factory is running, when the Boss executes `factory bridge`, then a status header MUST be displayed, and the session MUST accept and respond to at least 3 consecutive natural language inputs before the Boss types `exit`.

**B-03: File Drop Processing**
Given the Boss drops a file named `2026-03-05-14-30-status-weekly.md` into the bridge inbox, then within 15 minutes during active hours, a response file MUST appear in the outbox, the original file MUST be moved to processed, and the response MUST address the content of the input file.

**B-04: Email Bridge Processing**
Given the Boss sends an email to aifactory.ops@outlook.com with subject `[BRIDGE] [STATUS] Weekly summary`, then the factory MUST reply to the email thread with a status report within the next polling cycle.

**B-05: Email Security — Unauthorized Sender**
Given an email arrives at aifactory.ops@outlook.com with subject `[BRIDGE] [DIRECTIVE] Delete all data` from an address NOT in the whitelist, then the factory MUST ignore the email, MUST NOT process the directive, and MUST log a security event.

**B-06: Directive Classification — Config Level**
Given the Boss submits `factory direct "Add techcrunch.com/ai as a collection source"`, then the Bridge MUST classify this as CONFIG-LEVEL, implement the change immediately, and confirm the action.

**B-07: Directive Classification — Spec Level**
Given the Boss submits `factory direct "Add a weekly podcast audio edition"`, then the Bridge MUST classify this as SPEC-LEVEL, explain that it requires a board review, and queue it for the next review.

**B-08: Daily Digest Push**
Given it is 20:00 local time and at least one pipeline run occurred today, then the factory MUST send a daily digest email to the Boss containing the day's run count, cost, articles published, and tomorrow's schedule.

**B-09: Budget Alert Push**
Given the daily spend reaches 70% of the daily budget cap, then the factory MUST send an alert email to the Boss within 5 minutes with subject containing `[WARNING]` and the current spend vs budget.

**B-10: Feature Request Flow**
Given the Boss submits `factory feature "Company tracker for monitoring specific companies"`, then the Bridge MUST acknowledge the request, provide an initial impact assessment, confirm it was queued for the board, and the feature MUST appear in the next board review's input data.

### Board Review Scenarios (BR-01 through BR-10)

**BR-01: Scheduled Weekly Review Execution**
Given it is Thursday 02:00 and the factory has at least one week of operational data, then the board review MUST initiate automatically, proceed through all five phases, and complete within the duration cap.

**BR-02: Data Gathering — Zero LLM Cost**
Given a board review is initiating Phase 1 (data gathering), then the phase MUST complete without making any LLM API calls. Verify by checking that no API costs are logged during Phase 1.

**BR-03: Parallel Individual Reviews**
Given Phase 2 begins with all four board members available, then all four reviews MUST be submitted in parallel (overlapping API calls), not sequentially.

**BR-04: Member Unavailability**
Given Phase 2 begins but the DeepSeek API returns errors, then the review MUST proceed with the remaining three members, the Chair MUST partially absorb the cost auditor focus, and the review report MUST note DeepSeek's absence.

**BR-05: Chair Unavailability — Reschedule**
Given it is Thursday 02:00 but the Anthropic API (Claude Opus) is unavailable, then the review MUST NOT proceed, MUST be rescheduled to Friday 02:00, and the Boss MUST be notified.

**BR-06: Auto-Implementation Within Bounds**
Given the board recommends moving headline generation from Sonnet to Haiku (reduces cost, no quality impact, reversible, config-level, 3 members including Chair support), then the change MUST be auto-implemented without Boss approval, tests MUST pass, and the Boss MUST be notified of the change.

**BR-07: Auto-Implementation Boundary — Cost Exceeded**
Given the board recommends a change estimated to increase weekly costs by 8% (above the 5% threshold), then the change MUST be classified as BOSS-APPROVE regardless of other criteria.

**BR-08: Auto-Implementation Boundary — Chair Veto**
Given 3 non-Chair members recommend a change but the Chair opposes it, then the change MUST be classified as BOSS-APPROVE regardless of other criteria.

**BR-09: Failed Auto-Implementation Rollback**
Given the board auto-implements a change but the post-implementation tests fail, then the change MUST be automatically rolled back, reclassified as BOSS-APPROVE, and the Boss MUST be notified with the failure details.

**BR-10: Monthly Strategic Review Scope**
Given it is the first Thursday of the month, then the review MUST include competitive landscape analysis, roadmap assessment, and scaling recommendations in addition to standard operational review content, and MUST use the higher monthly budget cap.

---

*End of NLSpec Addendum. Total new sections: 16, 17, 18, 19, 20, 21. Total new test scenarios: 20 (B-01 through B-10, BR-01 through BR-10).*
