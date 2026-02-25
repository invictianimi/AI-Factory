# The LLM Report — Scenario Holdout Set

## Purpose

This file contains end-to-end scenarios that validate the pipeline works correctly.
Following the StrongDM Software Factory methodology, these scenarios function as a
"holdout set" — they are stored OUTSIDE the codebase so the coding agent cannot
optimize against them trivially.

**IMPORTANT:** Do not store this file in the same repository as the pipeline code.
The coding agent should not have access to these scenarios during implementation.
They are used only for evaluation after each milestone.

---

## Evaluation Method

For each scenario:
1. Set up the preconditions (mock data, KB state, source fixtures).
2. Run the relevant pipeline stage(s).
3. Verify all assertions.
4. A scenario PASSES only if ALL assertions pass.
5. Record: pass/fail, run cost, output quality notes.

**Satisfaction metric:** Of all scenarios for a milestone, what fraction pass? Target: >= 90% before proceeding to the next milestone.

---

## Milestone 1 Scenarios: Knowledge Base + Collection

### Scenario 1.1: Fresh collection from mock RSS feed

**Precondition:** Empty KB. Mock RSS feed with 5 items (3 model releases, 1 pricing change, 1 blog post).

**Input:** Collector runs against mock feed.

**Assertions:**
- [ ] All 5 items stored in KB structured store (`source_items` table).
- [ ] All 5 items have non-null content_hash.
- [ ] All 5 items have non-empty tags lists.
- [ ] All 5 items embedded in vector store.
- [ ] No LLM calls for items where regex tagging was sufficient.

### Scenario 1.2: Deduplication on re-run

**Precondition:** KB contains the 5 items from Scenario 1.1. Mock feed unchanged.

**Input:** Collector runs again.

**Assertions:**
- [ ] Zero new items stored (all content_hashes match existing).
- [ ] Zero LLM calls made.
- [ ] Collector output is empty list.

### Scenario 1.3: Incremental collection

**Precondition:** KB contains 5 items. Mock feed now has 7 items (2 new).

**Input:** Collector runs.

**Assertions:**
- [ ] Exactly 2 new items stored.
- [ ] Original 5 items unchanged.
- [ ] New items have embeddings in vector store.

### Scenario 1.4: Malformed source handling

**Precondition:** Empty KB. One mock source returns HTTP 500. Another returns invalid HTML.

**Input:** Collector runs against all sources including broken ones.

**Assertions:**
- [ ] Collector does not crash.
- [ ] Errors logged with source name and error type.
- [ ] Valid sources still collected successfully.
- [ ] No partial/corrupt items in KB.

### Scenario 1.5: GitHub API source collection

**Precondition:** Empty KB. Mock GitHub API returns 3 recent releases for a repository.

**Input:** Collector runs against mock GitHub source.

**Assertions:**
- [ ] All 3 releases stored as CollectedItems.
- [ ] Release notes extracted as raw_content.
- [ ] Tags include repository name and "release" category.

---

## Milestone 2 Scenarios: Triage + Deduplication

### Scenario 2.1: Significance scoring accuracy

**Precondition:** KB with 10 diverse mock items:
- 2 major model releases (should score 8+)
- 3 minor API patches (should score 3-5)
- 2 security advisories (should score 6-8)
- 1 partnership announcement (should score 5-7)
- 1 trivial blog post (should score 1-3)
- 1 pricing change (should score 5-7)

**Input:** Triage Agent processes all 10 items.

**Assertions:**
- [ ] Major model releases score >= 8.
- [ ] Minor API patches score <= 5.
- [ ] No item scores are null.
- [ ] All items have a valid category from the defined list.
- [ ] Each item has a non-empty rationale.
- [ ] Each item has a suggested_headline.

### Scenario 2.2: Tier promotion

**Precondition:** KB with a Tier 2 item (DeepSeek) describing a model release that surpasses GPT-5 on key benchmarks.

**Input:** Triage Agent processes the item.

**Assertions:**
- [ ] Significance score >= 8.
- [ ] `promoted` field is `true`.
- [ ] Item passes to downstream stages with full Tier 1 treatment.

### Scenario 2.3: Story clustering

**Precondition:** 4 items in KB:
- Item A: "OpenAI releases GPT-5.3" (from OpenAI blog)
- Item B: "GPT-5.3 announced with improved reasoning" (from TechCrunch)
- Item C: "Anthropic updates Claude pricing" (unrelated story)
- Item D: "OpenAI's new model: first impressions" (from The Verge)

**Input:** Deduplication runs on all 4 triaged items.

**Assertions:**
- [ ] Items A, B, D clustered into one StoryGroup.
- [ ] Item C is in its own StoryGroup.
- [ ] The highest-significance item in the A/B/D cluster is designated as primary.
- [ ] Zero or near-zero LLM calls (vector similarity only).

### Scenario 2.4: Threshold filtering

**Precondition:** 6 items with pre-assigned significance scores: 2, 4, 5, 7, 8, 10.

**Input:** Triage filtering applied.

**Assertions:**
- [ ] Score-2 item archived (not passed downstream).
- [ ] Score-4 and score-5 items routed to roundup section.
- [ ] Score-7, 8, 10 items routed as individual stories.
- [ ] Score-10 item flagged as potential lead.

### Scenario 2.5: All-low-significance run

**Precondition:** 5 items, all scoring 2-3 (minor patches, routine updates).

**Input:** Triage + downstream.

**Assertions:**
- [ ] Pipeline does not crash or produce an empty newsletter.
- [ ] All items archived.
- [ ] Pipeline produces a minimal output: "No significant AI news for this period" or equivalent graceful handling.
- [ ] Cost for this run is minimal (< $1).

---

## Milestone 3 Scenarios: Analysis + KB Integration

### Scenario 3.1: Analysis with KB context

**Precondition:** KB contains:
- A structured entry for "GPT-5.2" in the models table (release date, benchmarks, pricing).
- 3 previous articles about GPT-5 series.

New story: "OpenAI releases GPT-5.3 with 20% improved reasoning benchmarks."

**Input:** Analysis Agent processes the story.

**Assertions:**
- [ ] Output brief references GPT-5.2 as the predecessor (from KB, not hallucinated).
- [ ] Output includes comparison to GPT-5.2 benchmarks (from KB structured store).
- [ ] Output does not contain hallucinated benchmark numbers.
- [ ] KB context tokens are logged in cost_log (proving KB was queried).
- [ ] The brief has all required sections: what happened, why it matters, key details, sources.

### Scenario 3.2: Semantic cache hit

**Precondition:** Semantic cache contains a response for "What is the current pricing for Claude Sonnet?" from 2 days ago.

New triage query: "What does Claude Sonnet cost currently?"

**Input:** KB-first query pattern executes.

**Assertions:**
- [ ] Semantic cache returns a hit (cosine similarity >= 0.92).
- [ ] No LLM call is made for this query.
- [ ] Cost log shows cache_hit = true, cost_usd = 0.
- [ ] The cached response is used in the analysis.

### Scenario 3.3: Multi-source synthesis

**Precondition:** StoryGroup with 3 items from different sources covering the same event, with slightly different details:
- Source A: "Model released with 128K context window"
- Source B: "New model supports 128K tokens, pricing at $5/M input"
- Source C: "Model launched, benchmarks show 15% improvement over predecessor"

**Input:** Analysis Agent processes the StoryGroup.

**Assertions:**
- [ ] Output brief includes all three details (context window, pricing, benchmark improvement).
- [ ] Each detail is attributed to its source.
- [ ] No detail is presented as if from a different source than it came from.
- [ ] Output notes that all three sources corroborate the release (high confidence).

### Scenario 3.4: Single-source claim handling

**Precondition:** StoryGroup with 1 item containing a bold claim: "CEO states company will open-source all future models."

**Input:** Analysis Agent processes the story.

**Assertions:**
- [ ] The claim is included but flagged as single-source.
- [ ] Output contains language like "according to [source]" without amplifying confidence.
- [ ] No corroboration is fabricated.

### Scenario 3.5: KB context reduces token usage

**Precondition:** Run the same analysis task twice:
- Run A: KB is empty (no context available).
- Run B: KB has rich context for the story's entities.

**Input:** Same story processed in both runs.

**Assertions:**
- [ ] Run B uses fewer total tokens (input + output) than Run A.
- [ ] Run B cost is lower than Run A cost.
- [ ] Run B output quality is equal or better than Run A (has more accurate historical context).

---

## Milestone 4 Scenarios: Editorial + Compliance

### Scenario 4.1: Journalist voice verification

**Precondition:** Analyzed brief about a model release.

**Input:** Editorial Agent produces the article.

**Assertions:**
- [ ] No first person ("I", "we", "our").
- [ ] No promotional language ("exciting", "amazing", "revolutionary", "game-changing").
- [ ] No emoji.
- [ ] No bullet points in the body (flowing paragraphs only).
- [ ] Headline is under 80 characters.
- [ ] Lead paragraph contains who, what, when.
- [ ] Article length is within spec (300-600 words for standard).
- [ ] Reads like a technology journalist wrote it (subjective but evaluated by scoring model).

### Scenario 4.2: Copyright compliance — quote limits

**Precondition:** Analyzed brief containing a source that includes a notable quote from a CEO: "We believe this represents the most significant advancement in reasoning capabilities since the transformer architecture was introduced."

**Input:** Editorial Agent + Compliance Check.

**Assertions:**
- [ ] If the quote appears in the article, it is under 14 words.
- [ ] The quote is paraphrased, not reproduced verbatim.
- [ ] No more than one direct quote from this source in the entire article.
- [ ] Compliance Check passes on first attempt (no rewrite needed).

### Scenario 4.3: Compliance rejection and rewrite

**Precondition:** Editorial Agent deliberately produces an article with:
- A 20-word direct quote.
- An unattributed claim.
- Promotional language ("this groundbreaking release").

**Input:** Compliance Check runs.

**Assertions:**
- [ ] Compliance Check returns FAIL with specific reasons for each violation.
- [ ] Article is returned to Editorial Agent for rewrite.
- [ ] Second version fixes all flagged issues.
- [ ] Second version passes Compliance Check.
- [ ] Total rewrite cycles <= 3.

### Scenario 4.4: Analysis section placement

**Precondition:** Analyzed brief with significance = 9 and an identified forward-looking angle.

**Input:** Editorial Agent produces the article.

**Assertions:**
- [ ] Article contains an "Analysis:" section.
- [ ] Analysis section appears AFTER the factual body, not interleaved.
- [ ] Analysis section contains forward-looking commentary (industry implications).
- [ ] Analysis section does NOT contain unqualified predictions ("will" without "may" or "could").
- [ ] Analysis section is clearly distinguishable from the factual reporting.

### Scenario 4.5: Newsletter assembly — full edition

**Precondition:** 8 analyzed stories:
- 1 lead (significance 10)
- 2 standard (significance 7-8)
- 5 roundup (significance 4-6)

**Input:** Editorial Agent assembles full newsletter.

**Assertions:**
- [ ] Newsletter opens with 2-3 sentence overview.
- [ ] Lead story appears first and is longest (600-1000 words).
- [ ] Standard stories follow, ordered by significance.
- [ ] Roundup section contains all 5 lower-significance items as short paragraphs.
- [ ] No story is missing from the output.
- [ ] Newsletter ends with a brief sign-off (no call to action).
- [ ] Total newsletter length is reasonable (2000-5000 words depending on story count).

---

## Milestone 5 Scenarios: Website + Publishing + Cost Control

### Scenario 5.1: Website publishing — git commit and deploy trigger

**Precondition:** Complete newsletter content. Website git repo initialized and connected to deployment platform (Vercel/Netlify/Cloudflare Pages).

**Input:** Website Publisher runs.

**Assertions:**
- [ ] Markdown file created at `website/src/content/editions/YYYY-MM-DD.md`.
- [ ] Front matter includes: title ("The LLM Report — [date]"), date, tags, description, author.
- [ ] File committed to git with conventional commit message.
- [ ] Push to `main` branch succeeds.
- [ ] Published article logged in KB (`published_articles` table).

### Scenario 5.2: Budget enforcement — normal run

**Precondition:** Per-run budget set to $15. Run processes 10 items.

**Input:** Full pipeline run.

**Assertions:**
- [ ] Total cost logged in run_log.
- [ ] Cost breakdown available per stage.
- [ ] Total cost is under $15.
- [ ] No budget alerts triggered.

### Scenario 5.3: Budget enforcement — runaway cost

**Precondition:** Per-run budget set to $5 (artificially low). Run with many items that would normally cost $8+.

**Input:** Full pipeline run.

**Assertions:**
- [ ] Pipeline hits budget cap during processing.
- [ ] Pipeline stops gracefully (completes current stage, does not start new stages).
- [ ] Whatever content was ready gets published (partial edition).
- [ ] Alert is generated with cost details.
- [ ] No API calls made after budget exhaustion.

### Scenario 5.4: Cost anomaly detection

**Precondition:** 12-run rolling average is $6/run. Current run is on track for $14.

**Input:** Pipeline detects anomaly mid-run.

**Assertions:**
- [ ] Anomaly alert triggered (current > 2x rolling average).
- [ ] Pipeline pauses before publishing.
- [ ] Operator notification generated.
- [ ] Pipeline can be resumed after operator review.

### Scenario 5.5: Newsletter API integration

**Precondition:** Mock Buttondown API. Complete newsletter content.

**Input:** Newsletter Publisher runs.

**Assertions:**
- [ ] API call made with correct HTML-formatted content.
- [ ] Email subject includes "The LLM Report" and edition date.
- [ ] Email header displays "The LLM Report" branding.
- [ ] Email footer includes physical address, unsubscribe link, and disclosure text.
- [ ] Draft created (not sent) in Phase 1.
- [ ] Subscriber tags updated based on content topics.
- [ ] API errors handled gracefully (retry once, then log and continue).

### Scenario 5.6: Website scaffold — Astro project structure

**Precondition:** Empty `/workspace/website/` directory.

**Input:** Coding agent builds the website as part of Milestone 5A.

**Assertions:**
- [ ] Valid Astro project created (`package.json` with astro dependency, `astro.config.mjs`).
- [ ] `astro build` completes without errors.
- [ ] Output in `dist/` directory contains HTML files.
- [ ] All required pages exist: index, archive, about, subscribe, 404.
- [ ] RSS feed generated at `dist/rss.xml` with valid XML.
- [ ] JSON feed generated at `dist/feed.json` with valid JSON.

### Scenario 5.7: Website design — responsive layout

**Precondition:** Website built with sample edition content.

**Input:** Inspect the generated HTML/CSS.

**Assertions:**
- [ ] Content area max-width is approximately 680px.
- [ ] "The LLM Report" appears in the site header on every page.
- [ ] Newsletter signup form/link appears on every page.
- [ ] Body text line-height is between 1.6 and 1.8.
- [ ] No external font loading (system font stack only).
- [ ] `prefers-color-scheme: dark` media query present.
- [ ] Viewport meta tag present for mobile.

### Scenario 5.8: Website content — sample edition rendering

**Precondition:** Mock edition with: 1 lead story, 2 standard stories, 3 roundup items, 1 analysis section.

**Input:** Sample edition rendered on the website.

**Assertions:**
- [ ] Lead story displays with headline, subheadline, and full body.
- [ ] Analysis section visually distinct (border or background tint, "Analysis" label).
- [ ] Source links are clickable and present.
- [ ] Roundup items are shorter than lead story.
- [ ] Edition date displayed prominently.
- [ ] Open Graph meta tags populated (og:title, og:description, og:type="article").

### Scenario 5.9: Website deployment — auto-deploy on push

**Precondition:** Website repo connected to deployment platform. Deployment config file present.

**Input:** New edition committed and pushed to `main`.

**Assertions:**
- [ ] Deployment triggers automatically (verified by checking deployment status API or log).
- [ ] Site is accessible at the platform's default URL within 120 seconds of push.
- [ ] New edition page returns HTTP 200.
- [ ] RSS feed includes the new edition entry.
- [ ] Previous editions still accessible (no content loss).

### Scenario 5.10: Website — About page and transparency

**Precondition:** Website built.

**Input:** Load the About page.

**Assertions:**
- [ ] Page contains explicit AI-generated content disclosure.
- [ ] Page describes the methodology (pipeline stages, multi-source verification).
- [ ] Page mentions "The LLM Report" by name.
- [ ] Page does NOT claim content is human-written.
- [ ] Error reporting contact information present.

### Scenario 5.11: Security — private repos and HTTPS

**Precondition:** Website deployed. GitHub repos configured.

**Input:** Inspect deployment configuration and access controls.

**Assertions:**
- [ ] Website GitHub repo is set to private (or the factory instructions specify private).
- [ ] Pipeline GitHub repo is set to private.
- [ ] Website is served over HTTPS (check response headers).
- [ ] HTTP requests redirect to HTTPS.
- [ ] Security headers present: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`.
- [ ] No API keys, tokens, or secrets present in any committed file.
- [ ] `.env` is in `.gitignore`.
- [ ] Source maps disabled in production build (`sourcemap: false`).

### Scenario 5.12: Security — JavaScript obfuscation

**Precondition:** Website built with `astro build`.

**Input:** Inspect the `dist/` output directory.

**Assertions:**
- [ ] Client-side JavaScript files (if any) are obfuscated (variable names mangled, code not human-readable).
- [ ] No HTML comments in production output.
- [ ] CSS and JS are minified and bundled.
- [ ] No source map files (`.map`) in the `dist/` directory.

### Scenario 5.13: SEO — structured data and sitemaps

**Precondition:** Website built with sample edition.

**Input:** Inspect generated HTML and sitemaps.

**Assertions:**
- [ ] `sitemap.xml` exists and contains URLs for all pages.
- [ ] `news-sitemap.xml` exists and contains only recent articles (< 48 hours old).
- [ ] `robots.txt` exists and references both sitemaps.
- [ ] Article pages contain JSON-LD structured data with `@type: NewsArticle`.
- [ ] JSON-LD includes: headline, datePublished, author (Organization), publisher with logo.
- [ ] Homepage contains `WebSite` schema.
- [ ] Article pages contain `BreadcrumbList` schema.
- [ ] Open Graph meta tags present on article pages (og:title, og:description, og:type, og:image).
- [ ] Canonical URL present on every page.

### Scenario 5.14: SEO — page performance

**Precondition:** Website built and deployed.

**Input:** Load a sample article page.

**Assertions:**
- [ ] Zero JavaScript shipped to client (unless explicitly required by an interactive component).
- [ ] No external font requests.
- [ ] All images have `loading="lazy"` attribute.
- [ ] Total page weight < 100KB (excluding images).
- [ ] Content width approximately 680px on desktop viewport.

### Scenario 5.15: Monetization — infrastructure scaffolding

**Precondition:** Website built. Pipeline config directory exists.

**Input:** Inspect config files and page templates.

**Assertions:**
- [ ] `affiliate_links.yaml` exists (can be empty).
- [ ] `sponsors.yaml` exists (can be empty).
- [ ] Newsletter template includes sponsor slot that renders nothing when config is empty.
- [ ] Website edition template includes sponsor slot that renders nothing when config is empty.
- [ ] `/support` page exists (or route defined, can have placeholder content).
- [ ] `/jobs` page template exists (hidden from nav when empty).
- [ ] No monetization elements visible to readers when configs are empty.

### Scenario 5.16: Reusability — framework separation

**Precondition:** Pipeline code built.

**Input:** Inspect project structure.

**Assertions:**
- [ ] `src/framework/` directory exists with domain-agnostic pipeline code.
- [ ] `src/stages/` directory exists with The LLM Report's specific stage implementations.
- [ ] `config/` directory contains all project-specific configuration (sources, editorial guidelines, budget).
- [ ] `FRAMEWORK.md` exists documenting the stage interface and extension points.
- [ ] No hardcoded source URLs, brand names, or editorial guidelines in the framework layer.

---

## Milestone 6 Scenarios: Full Integration

### Scenario 6.1: End-to-end Monday run

**Precondition:** Real sources (or high-fidelity mocks). KB with 2 weeks of historical data. Website deployed and accessible.

**Input:** Full pipeline triggered as Monday batch run.

**Assertions:**
- [ ] Collector fetches from Tier 1 + Tier 2 sources.
- [ ] Does NOT fetch Tier 3 sources (not Friday).
- [ ] Triage scores all items.
- [ ] Deduplication clusters related stories.
- [ ] Analysis produces briefs with KB context.
- [ ] Editorial produces journalist-quality content.
- [ ] Compliance passes all articles.
- [ ] Edition published to theLLMreport.com (git push → auto-deploy → HTTP 200 verified).
- [ ] Newsletter draft created in Buttondown with correct branding.
- [ ] Total cost within budget.
- [ ] Run time < 30 minutes.
- [ ] All costs logged per stage.

### Scenario 6.2: End-to-end Friday run with Tier 3

**Precondition:** Same as 6.1 but Friday.

**Input:** Full pipeline triggered as Friday batch run.

**Assertions:**
- [ ] All assertions from 6.1.
- [ ] PLUS: Tier 3 sources are collected (Mistral, Qwen, HuggingFace, arXiv, etc.).
- [ ] Weekly roundup section includes Tier 3 content.

### Scenario 6.3: Graceful degradation — no significant news

**Precondition:** All sources return only minor updates (significance < 4).

**Input:** Full pipeline run.

**Assertions:**
- [ ] Pipeline completes without error.
- [ ] Output is a minimal edition (roundup only, or "quiet week" notice).
- [ ] Cost is well below average (fewer LLM calls for analysis/editorial).
- [ ] Newsletter is still professional and worth reading (even if short).
- [ ] Website still receives the edition (even a short one).
- [ ] No empty or broken output.

### Scenario 6.4: End-to-end with tier promotion

**Precondition:** Normal Monday run. One Tier 2 source (DeepSeek) has published a major model release.

**Input:** Full pipeline run.

**Assertions:**
- [ ] DeepSeek story scored >= 8 by Triage.
- [ ] Story promoted to Tier 1 coverage depth.
- [ ] Analysis includes competitive context (comparison to Tier 1 equivalents).
- [ ] Story appears as individual article, not buried in roundup.
- [ ] Standalone article page created on website (`/articles/deepseek-...`).

### Scenario 6.5: Website and newsletter content consistency

**Precondition:** Full pipeline run completes.

**Input:** Compare website edition content with newsletter draft content.

**Assertions:**
- [ ] Same stories appear in both outputs.
- [ ] Same headlines and lead paragraphs.
- [ ] Newsletter links back to website article URLs.
- [ ] No content appears in newsletter that doesn't appear on website.
- [ ] Newsletter includes "Read the full edition at theLLMreport.com" link.
