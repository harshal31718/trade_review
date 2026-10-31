# Post-trade review: from a month of orders to the habits that cost money

**Problem chosen:** 03, Post-trade review. The data already exists in the order book, and the output can be checked in rupees instead of opinion.

## Problem statement
A retail options trader cannot see which of their own habits cost them money, because the only way to find out is to read a month of order history, and almost nobody does. This matters because close to nine in ten individual F&O traders lost money in SEBI's FY26 study, and the same behaviours repeat unnoticed.

## Why Nubra should solve it
- **User impact:** "Five oversized trades cost you ₹26,595" gives a trader one behaviour to change.
- **Business impact:** Traders who blow up leave, so a review that keeps them solvent protects retention. I am betting that outweighs the volume lost from fewer impulsive trades. I have no Nubra data to prove it.
- **Why Nubra:** it owns its OMS and RMS, so it already holds clean order data. My CSV is a stand-in. The real product needs no upload.

## Scope
**In scope:** a CSV of executed single-leg options trades; FIFO pairing into round trips; four habit checks (quick re-entry after a loss, oversizing, cheap expiry-day buying, holding losers long); the top three ranked by rupees lost; one plain-English nudge each; a preloaded sample; a collapsed trade-statistics panel.

**Out of scope, and why:**
- Multi-leg strategies: a spread leg reads as a separate loss. The app detects these trades, excludes them and says so.
- Futures and equity: different habits, different maths.
- Live broker connection: Nubra already owns that data.
- Advice on what to trade: nudges describe behaviour only.
- An LLM at runtime: not reproducible, not checkable against ground truth.
- Charges: P&L is gross unless the file includes fees.

## Solution space
1. **Upload-and-review report (built).**
2. **Automatic review inside the platform,** pushed after a bad day or each month. Better, because it reaches traders who never open a report, but it needs Nubra's data. This is the next version.
3. **LLM-written narrative.** Reads well, but cannot be reproduced or checked against rupee ground truth, and can drift into advice. Rejected.

I chose option 1 with deterministic rules: the same file gives the same answer, every rupee figure is checkable by hand, and the tool never says what to trade.

## How I tested it
**Ship bar, fixed before the first run:** every test case passes; a clean trader surfaces zero habits on every seed; at least 80% of planted habits surface; at most one false habit across three decoy traders.

**Results:** 12 of 12 cases pass, including rupee and ratio figures I calculated by hand before any code existed. The clean control surfaced 0 false habits across 10 seeds, and the decoys (late re-entry, consistently large size, profitable expiry trades) surfaced 0. Planted-habit recall is 63 of 70 (0.90).

**What changed:** reviewing the live app, I found an expiry-day card whose flagged trades lost less per trade than the rest. A "habit costing money" that beats your average is an invented finding, so I now report a habit only when its flagged trades do worse than the rest. Recall fell from 70/70 to 63/70. The misses are the cheap-premium habit inside a mixed trader, since rupees per trade penalise small premiums. I kept the rule. A second bug showed only on the deployed app, which kept serving old results after a push. Tests missed it; loading the live page caught it.

**Limits:** my synthetic traders come from rules I wrote, so scores show the code does what I specified, not that real traders behave this way. I have not yet run the clarity test with non-traders, so that row stays NOT RUN.

## What I'd do next
1. Compare return on premium instead of rupees per trade.
2. Test on real broker exports, labelled by hand before the app sees them.
3. Move the review inside the platform and track one number: do traders flagged this month repeat the behaviour less next month?

*Source: SEBI, FY26 individual derivatives-trader study.*
