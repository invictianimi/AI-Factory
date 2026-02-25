# Board Review: Website Design
Date: 2026-02-25

## Chair (Claude Opus) — Initial Priorities

1. Edition page template (blocker)
2. Newsreader serif headings + Inter body
3. Electric blue #2436e8 accent, used in 3 places only
4. Edition cards on homepage
5. Analysis callout blocks with left border


## Adversarial Reviewer (Sonnet)

The credibility trap: premium editorial design creates false authority for AI content.
Newsletter readers don't browse the homepage — they click from email.
Readers care about: scannability in 90 seconds, information density, topic filtering.
Missing: read time on everything, publication frequency signals, topic taxonomy.
Lean into AI transparency and utility, not borrowed Stratechery authority.


## Final Synthesis (Chair)
# Implementation Brief: The Dispatch

## Guiding Principle
**Transparent utility.** Every design choice signals "AI-curated, human-useful." Speed to insight beats editorial prestige.

## Build Now

**Typography:** Inter 400/600 throughout. No serif. Uniform type signals machine origin honestly. Body 17px/1.6, headings 24px/600.

**Color:** Neutral gray system (`#111`, `#555`, `#e5e5e5`) + one accent `#2436e8` used ONLY on: read-time badges, active topic filter pills, callout left borders.

**Edition page template** (blocker):
- Top bar: `AI-generated briefing · [date] · [total read time]`
- Sections as stacked cards, each with: topic tag, headline, read time badge, 2-line summary, expandable full analysis
- No hero image. No byline theater.

**Homepage:** Edition cards in reverse-chron list. Each card: date, edition number, topic count, total read time. One click to full edition. No browse-optimized layout — respect that readers arrive from email.

**Topic filtering:** Defined taxonomy (6-8 tags max). Defined now, not later. Persistent filter bar on edition page.

**Analysis callout blocks:** 4px left border `#2436e8`, `background: #f7f7f9`, labeled "AI Analysis" explicitly.

**Read time:** On every card, every section, every page. Non-negoti
