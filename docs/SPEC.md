# SPEC v0.2 — Post-trade review (Nubra Problem 03)
Owner: BRAIN. Status: draft for OPS to build against. Changes go in HANDOFF.md as dated entries.

## 1. Problem (one paragraph, for the one-pager later)
Most retail options traders never review their trades, so repeat behavioural leaks go unseen. A report they must
go and fetch does not fix a population that does not fetch. Nubra already holds order data in its OMS, so the real
product is an automatic review. This prototype takes a CSV as a stand-in for that data. Goal: from one month of
executed trades, surface the 2-3 habits costing the most money, with evidence, in rupees, honestly labelled.

## 2. Principles (non-negotiable)
- Deterministic rules engine. No LLM at runtime. Same input -> same output.
- Behaviour only. Nudges never name an instrument, direction, or say what to trade (SEBI advice line).
- Observed rupees are facts. "If avoided" rupees are estimates and are always labelled "estimate".
- Say "no costly habit found" when true. Never invent a finding.
- Small-sample honesty: a habit needs n_flagged >= 3 to be reported.

## 3. Scope (v1)
IN: options (CE/PE) executed trades, long and short single-leg, one broker file per run.
OUT: multi-leg strategy analysis, futures/equity analysis, instrument advice, live broker connection, accounts/login.
Non-option rows are dropped and counted in the warnings panel. Multi-leg is detected and excluded, not analysed.

## 4. Input contract
Canonical schema (what engine/ accepts). One row per executed fill:
  ts (tz-aware IST datetime), underlying, option_type (CE|PE), strike (float), expiry (date),
  side (BUY|SELL), qty (int, units not lots), price (float, per unit)
Optional: fees (float, per fill, INR), spot (float, underlying price at fill).
Engine rejects the file with a clear message if a required column is missing or unparseable.

Mapper layer (engine/mappers/): registry {name -> function(raw_df) -> canonical_df}.
v1 ships exactly two: `canonical` (passthrough/validate) and `groww` (only if a real export is available;
build from the real header, never from guesses). Mapper parses the symbol string into underlying/expiry/strike/type.
No other brokers in v1.

## 5. Round trips
- FIFO match per instrument (underlying, expiry, strike, option_type). Sell-first opens a short.
- A "trip" = position cycle from flat to flat on one instrument: entry_ts = first open fill, exit_ts = last close fill,
  entry_price/exit_price = quantity-weighted averages, size = qty * entry_price (premium notional), pnl = gross FIFO pnl
  minus fees if fees present, hold_minutes = exit_ts - entry_ts.
- Positions still open at period end, and closing fills with no opener in the file, are NOT trips. List them in warnings.
- If fees column absent: pnl is gross and the UI says "gross, before charges".

## 6. Multi-leg detection (warn, do not analyse)
Fills on the same underlying+expiry within 60 seconds that mix option types or opposite sides at different strikes
are tagged `possible_multi_leg`. Trips containing them are excluded from detectors. Warnings show the count.

## 7. Detectors (all thresholds live in one config dict; UI exposes sliders; evals sweep them)
Each detector returns: flagged trips, n_flagged, observed_pnl (sum of flagged trip pnl), baseline_pnl_per_trip
(mean of unflagged trips), evidence rows, and a status.

D1 revenge_reentry: trip T entered within W minutes (default 15) after a LOSING trip exit (any instrument,
  same underlying) AND size(T) >= R * size(prior) (default R = 1.0).
D2 expiry_day_cheap_premium: BUY trip entered on expiry date, entry_price <= P (default INR 30).
  If `spot` present: use moneyness >= 1% OTM instead of the price proxy. UI states which was used. This is a PROXY.
D3 oversizing: size(T) > K * median(size of previous N trips) (defaults K = 2.0, N = 20; if fewer than 10 prior
  trips use whole-period median and say so).
D4 fee_drag (only if fees present): total fees / gross profit-and-loss turnover. observed_cost = total fees (exact, not estimate).
D5 loser_holding (PROMOTED in v0.2): losing trips held longer than H x median hold of winning trips (default H = 2.0, needs >= 3 winners). Rupee figure = observed pnl of those trips (no price path, so no counterfactual).

Cost definition: observed_pnl = sum pnl of flagged trips (can be positive). A habit is REPORTED only if
n_flagged >= 3 AND observed_pnl < 0. Estimate shown as "if avoided (estimate): +INR |observed_pnl|, assuming nothing else changes".
Ranking: by |observed_pnl| descending. Output top 3 at most. Zero qualifying habits -> "No costly habit found this period."

## 8. Output contract (per reported habit)
name, one-line plain description, n_flagged of n_total, observed INR, estimate INR (labelled), up to 5 evidence rows
(time, instrument, size, pnl), flagged-vs-unflagged avg pnl per trip, a behavioural nudge from a fixed template per detector.
Page header: period, trips, net pnl (gross/net label), win rate. Warnings panel: dropped rows, unmatched fills,
multi-leg exclusions, missing fees, proxy used, small-sample notes.

## 9. Nudge rules (lint-testable)
Banned tokens in nudges: buy, sell, short, long, call, put, bullish, bearish, "should trade", "avoid trading", any ticker/underlying.
Required: describes what the user did; any rupee counterfactual contains the word "estimate".
Example: "7 trades were opened within 15 minutes of a loss, at equal or larger size, and lost INR 8,400 net. A fixed pause after a loss is one way people interrupt this pattern."

## 10. App
Streamlit. engine/ has no Streamlit imports. Upload CSV or "Load sample" (bundled synthetic file). Row/size caps on upload.
No real data committed. Free tier only.

## 11. Evals contract (BRAIN writes EVALS.md from OPS output; OPS produces numbers via pytest + eval script)
- Synthetic generator, seeded: archetypes = revenge trader, expiry gambler, oversizer, combined, CLEAN CONTROL,
  plus hard negatives (re-entry after loss but beyond W; consistently large size across the month; profitable expiry-day trades).
- Metrics: per-detector trade-level precision/recall; user-level "habit surfaced or not"; control must surface 0 habits.
- Threshold sensitivity: sweep W, K, P, R and report how surfaced habits change.
- Real-data case (if Groww export has timestamps): labels written BEFORE running engine, stored outside git (data/real/).
  Label file frozen with a timestamp. Report honestly; n = 1.
- Nudge lint test per section 9.
- Pre-stated bar: control surfaces 0 habits; user-level recall >= 0.8 across planted archetypes; <= 1 false habit across hard negatives.
  Caveat to state: synthetic data tests implementation correctness, not real-world validity.

## 12. v0.2 changes from the Nubra Candidate Reference Guide (these override earlier sections)
Source: Nubra Product Manager Assignment Candidate Reference Guide (Notion). Grader-facing requirements:
1. Habit set: guide lists loser-holding as its flagship example with a rupee figure, so D5 is core. Core = D1, D2, D3, D5. D4 (fees) optional, only if fees present.
2. "Insights with no money impact" is a named trap: every reported habit MUST carry a rupee figure.
3. Full review fits on ONE screen. Max 3 habits. Kind, non-judgmental tone (no "you gambled", "reckless", "stupid"). One simple fix per habit.
4. App must show: "For demo purposes only. Not investment advice." No login. Sample preloaded. Test in incognito and on a phone.
5. Evals use the guide's format: 6-10 cases, columns # | Type | Input | Expected | Actual | Pass/Fail | Fix. Types: Correctness, Clarity, Edge, Safety.
   Ship bar written BEFORE running. Must include >=3 hand-calculated fixtures (rupee cost matches manual calc) and a clean-data case.
   Clarity: 1-2 non-traders try the app, note where they get stuck.
   The sweep / precision-recall work is a supplement, not the headline. Real-data labelling is optional bonus (guide: sample data is fine).
6. Prompts log format: # | Prompt (as-is) | What happened | What I changed next.
7. One-pager follows the guide template: Problem Statement ("[User] struggles with [problem] because [reason]. This matters because [impact]."),
   Why Nubra (user impact / business impact / why well placed), Scope (in/out with reasons), Solution Space (2-3 options compared),
   How I Tested It, What I'd Do Next. 300-700 words, checked with a word counter.
   Solution-space options to compare: (a) uploaded CSV report [built], (b) in-platform automatic weekly push using Nubra's own OMS data [next version],
   (c) LLM-written narrative review [rejected: not reproducible, cannot be evaluated against ground truth].
8. Why-Nubra facts from the guide: institutional-grade tools for retail, own OMS/RMS, 25,000+ retail demat accounts. SEBI loss statistic must be re-checked on sebi.gov.in and cited with source before use.
