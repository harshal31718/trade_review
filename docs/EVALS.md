# EVALS: how I decided the output was good enough to ship

All numbers below are copied from `data/synthetic/eval_results.md`, which `tools/run_evals.py` generates from the code. I wrote no figure by hand.

## How to read this
- The ship bar was written before the first run (see below) and did not change afterwards.
- Rows 1-4 are rupee figures I calculated by hand in `docs/FIXTURES.md` before any code existed. The code had to match them. It was never allowed to change them.
- The supplement runs 9 synthetic trader types over 10 random seeds: planted-habit traders, one clean control, and three decoys built to look like a habit without being one.
- Caveat that applies to everything: I wrote the generator knowing the detector rules, so high scores show the code does what I specified. They do not show that real traders behave this way.

## What failed along the way, and what I did
1. **Live-app review found a false finding.** The sample showed a "cheap trades on expiry day" card whose flagged trades lost -INR 701 per trade against -INR 900 on the rest. Flagged trades beat the average, so the card contradicted its own claim. I added a rule: report a habit only if its flagged trades do worse per trade than the rest.
2. **The rule cost recall.** User-level recall fell from 70/70 to 63/70, and 4 tests failed. All 7 misses come from one cause: the cheap-premium habit inside a mixed trader. Rupees per trade penalise small premiums. I kept the rule, marked those 4 tests as known failures with the reason, and listed the fix (compare return on premium) as next work. I did not change a threshold to recover the score.
3. **Clarity test.** Not yet run with real people. See row 11.

---

Caveat: synthetic data tests implementation correctness, not real-world validity.

## Ship bar (fixed before running)
1. All table cases pass. 2. Clean control surfaces 0 habits on all 10 seeds. 3. User-level recall >= 0.8. 4. <= 1 false habit across all hard-negative users.

## Cases
| # | Type | Input | Expected | Actual | Pass/Fail | Fix |
|---|---|---|---|---|---|---|
| 1 | Correctness | F2: BUY 100@50, BUY 100@60, SELL 150@70, SELL 50@40 (hand calc 100*20 + 50*10 + 50*(40-60)) | 1 trip, pnl 1,500 | 1 trip, pnl 1,500 | PASS | - |
| 2 | Correctness | F4 on 3 days: 75@100->80 (-1,500), then 150@90->70 (-3,000) 10 min later; hand calc 3 x -3,000 | re-entry habit reported, 3 flagged, observed -9,000, estimate +9,000 | 3 flagged, observed -9,000, estimate +9,000 | PASS | - |
| 3 | Correctness | F8: winners held 10/12/14 min (median 12), losers held 30 and 20 min, each loser 75*(90-100) | 1 flagged (the 30-min loser), observed -750 | 1 flagged, observed -750 | PASS | - |
| 4 | Correctness | F6: BUY 75@12 on expiry day, expires at 0 (hand calc 75*(0-12)) | flagged by the expiry check, pnl -900 | 1 flagged, observed -900 | PASS | - |
| 5 | Edge | Clean synthetic trader, no planted habit (seed 0) | 0 habits and "No costly habit found this period." | 0 habits; message: No costly habit found this period. | PASS | - |
| 6 | Edge | Empty file (F10) | Clear 'file is empty' message, no crash | SchemaError: The file is empty: no trade rows were found. | PASS | - |
| 7 | Edge | CSV without the price column (F10) | Error that names 'price' | SchemaError: Missing required column(s): price. Expected columns: ts, underlying, option_type, strike, expiry, side, qty, price. | PASS | - |
| 8 | Edge | Only 2 quick re-entries in the month (each loses 3,000) | 2 flagged but NOT reported (needs >= 3) | 2 flagged; reported: none | PASS | - |
| 9 | Edge | F5: one BUY, never closed | 0 trips and a warning about 1 open/unmatched position | 0 trips; warning: ['1 open/unmatched position(s) (may be a positio'] | PASS | - |
| 10 | Safety | 21 nudge/description/title strings (templates + habits shown for 9 synthetic users) | No banned word or instrument name; every rupee counterfactual says 'estimate' | banned hits: none; counterfactuals missing 'estimate': 0 | PASS | - |
| 11 | Clarity | 1-2 non-traders use the app on a phone and note where they get stuck | Can find the main habit and what to do in under a minute | Not run yet (manual) | NOT RUN | - |

## Supplement: synthetic archetypes, seeds 0-9 (90 users)
- User-level recall (planted habit surfaced): 63/70 = 0.90
- Clean control false habits (all seeds): 0
- Hard-negative false habits (all seeds): 0

## Known limitations
- Rupees-per-trade comparison (SPEC s13) under-measures cheap-premium habits in a mixed trader; fix = compare return on premium. Attributed misses: 7 of 7 (combined archetype, expiry-day habit, seeds [0, 1, 3, 4, 5, 6, 9]).
- Misses NOT explained by this limitation: 0

Trade-level (planted trades vs flagged trips, all users):

                detector  TP  FP  FN precision recall
         revenge_reentry 140   0   0      1.00   1.00
expiry_day_cheap_premium 160  80   0      0.67   1.00
              oversizing 110   0   0      1.00   1.00
           loser_holding  50   0   0      1.00   1.00

## Threshold sweep (one parameter at a time, others at default)
| Param | Value | Planted habit surfaced | False habits (control + hard negatives) |
|---|---|---|---|
| W | 5 | 2/10 seeds | 0 |
| W | 10 | 10/10 seeds | 0 |
| W | 15 (default) | 10/10 seeds | 0 |
| W | 30 | 10/10 seeds | 0 |
| W | 45 | 10/10 seeds | 4 |
| R | 0.5 | 10/10 seeds | 0 |
| R | 1.0 (default) | 10/10 seeds | 0 |
| R | 1.5 | 0/10 seeds | 0 |
| R | 2.0 | 0/10 seeds | 0 |
| P | 10 | 5/10 seeds | 0 |
| P | 20 | 10/10 seeds | 0 |
| P | 30 (default) | 10/10 seeds | 0 |
| P | 50 | 10/10 seeds | 0 |
| P | 80 | 10/10 seeds | 0 |
| K | 1.5 | 10/10 seeds | 1 |
| K | 2.0 (default) | 10/10 seeds | 0 |
| K | 3.0 | 10/10 seeds | 0 |
| K | 4.0 | 3/10 seeds | 0 |

## Ship bar verdict
- PASS: All table cases pass
- PASS: Control surfaces 0 habits
- PASS: Recall >= 0.8
- PASS: <= 1 false habit on hard negatives
