# HANDOFF (append-only, dated entries; never edit past entries)
# BRAIN owns docs/. OPS owns app/, engine/, data/, tests/, git, deploy.

## 2026-10-29 — BRAIN
- docs/ scaffolded: SPEC.md, ONE_PAGER.md, EVALS.md, PROMPTS.md, HANDOFF.md.
- Submission deadline: 2026-10-31 14:00 IST. Internal submit target: 2026-10-31 12:00 IST.
- OPS: nothing assigned yet. SPEC.md will define engine input schema and detector contracts first.

## 2026-10-29 — BRAIN -> OPS: deployment constraints (zero spend)
- Target: Streamlit Community Cloud (free). Repo public. Entry point app/main.py. requirements.txt at repo root, pinned versions.
- No paid APIs. Engine is deterministic. No LLM calls at runtime; nudge text is template-based. No secrets needed.
- Ship a bundled sample CSV (data/synthetic/) with a "Load sample" button so graders need no file of their own.
- No real trade data in the repo (data/real/ is gitignored).
- Keep memory small (free tier ~1 GB RAM): no heavy deps, no large files. Cap upload size and row count in the app.
- Deploy a hello-world FIRST (tonight), real app later, so deploy risk is retired early.
- Fallback if Streamlit Cloud fails: Hugging Face Spaces (Docker, free). Decide by 17:00 IST Oct 30.

## 2026-10-29 — BRAIN -> OPS: SPEC v0.1 is in docs/SPEC.md
- Build order: (1) engine/schema.py + validation, (2) mappers registry (canonical now, groww later when header is known),
  (3) FIFO pairing -> trips, (4) multi-leg tagging, (5) detectors D1-D4 behind one config, (6) ranking + output object,
  (7) nudge templates + lint test, (8) synthetic generator + eval script, (9) Streamlit app.
- Deploy hello-world tonight (see deployment entry above). Do not start the UI before engine tests pass.
- Questions/ambiguities: append here, BRAIN answers in a dated entry.

## 2026-10-29 — OPS
- Scaffolded layout: app/, engine/, data/synthetic/, data/real/, tests/ (.gitkeep in empty tracked dirs; data/real/ is gitignored so it exists locally only).
- .gitignore: data/real/, .venv/, __pycache__/, .env.
- requirements.txt: streamlit, pandas, pytest (unpinned). Installed in .venv (Python 3.13.12): streamlit 1.66.1, pandas 3.1.0, pytest 9.2.0.
- app/main.py: hello-world Streamlit page; verified headless via streamlit AppTest (no exceptions). Run: `.venv\Scripts\streamlit run app/main.py`.
- Rule held: engine/ has no Streamlit imports (empty for now); app/ will only call engine/.
- Note: first pip install hung with no network progress; killed and re-ran, succeeded.
- Committed and pushed to origin main.
- Waiting on: SPEC.md input schema + detector contracts before any engine work.

## 2026-10-29 — BRAIN -> OPS: SPEC v0.2 (Nubra reference guide received)
- Read SPEC.md section 12. D5 loser_holding is now core. Every habit needs a rupee figure. One-screen layout, max 3 habits.
- Add disclaimer text in app: "For demo purposes only. Not investment advice."
- Eval output must be a table: # | Type | Input | Expected | Actual | Pass/Fail | Fix. Include >=3 hand-calculated fixtures (I will supply expected values).
- Real-data (Groww) path is now OPTIONAL. Do not spend build time on the groww mapper until engine + app + deploy are done.

## 2026-10-29 — BRAIN -> OPS: keep-warm job (do AFTER app deploys, low priority)
- Streamlit Cloud sleeps apps after ~12h without visitors; commits do not count and cannot wake a sleeping app.
- Add .github/workflows/keepwarm.yml: cron every 6 hours + workflow_dispatch. Job uses Playwright (headless Chromium) to open the app URL,
  wait for the page to render, and if the text "get this app back up" is present, click that button and wait for the app to load.
  Fail the job if the app title is not found after wake. URL stored as a repo variable, not hard-coded. Public repo = free Actions minutes.
- Keep the script in tests/ or a tools/ folder, not engine/. Do not add any in-app threads or timers: they do not prevent sleep.

## 2026-10-29 — OPS: engine steps 1-4 done (schema, mappers, pairing, multi-leg)
Passed: 51 pytest cases, all green (`.venv\Scripts\python -m pytest`). One commit per step, pushed to origin main.
- engine/schema.py `validate_trades(df)`: F10 covered (empty/header-only -> "file is empty"; missing column -> error names it; unparseable value -> names column + first bad rows).
- engine/mappers/: registry with `canonical` only. `get_mapper(name)`, `map_to_canonical(df, mapper="canonical")`. No groww.
- engine/pairing.py `pair_trips(fills)`: F1, F2, F3, F5 exact values; F4 and F6 pairing parts (2 trips; pnl -900). Returns trips, open_positions, warnings.
- engine/multileg.py `tag_multileg`, `flag_trips`: F9 (1 group, both fills tagged).
- tests/: test_schema, test_mappers, test_pairing, test_multileg, test_pipeline. No fixture expected value was changed; no fixture appears wrong.
- NOT yet tested (need detectors, next step): F4 D1 flags and variants F4b/F4c, F6 D2 flags and F6b/F6c, F7 (D3), F8 (D5).

Assumptions:
- Timestamps: naive -> treated as IST; tz-aware -> converted to IST (fixed +05:30, no tzdata dependency).
- Schema adds `fill_id` (row order after stable time sort); validate returns warnings in `df.attrs["warnings"]` (dropped non-option rows; "no fees column, gross pnl").
- Non-CE/PE rows are dropped and counted; if none remain, error. Column names are lower-cased/stripped; side and option_type upper-cased.
- qty must be a positive whole number; price >= 0 (0 allowed for expired-worthless, F6). Missing fee values in a fees column are treated as 0.
- Multi-leg: a pair of fills (same underlying+expiry, <= 60 s apart, inclusive) qualifies if option types differ, or sides differ AND strikes differ. Groups are connected components of qualifying pairs; trips containing any tagged fill get `possible_multi_leg=True`.
- A position flip (SELL larger than open long) closes the trip and opens a new short trip with the remainder; fees are split pro rata by qty.
- Trips with a scale-in after a partial exit stay ONE trip (flat to flat); qty/size/entry_price use all opening fills.

SPEC ambiguities for BRAIN:
1. SPEC s5 says "closing fills with no opener in the file are NOT trips" but also "sell-first opens a short". An orphan SELL is indistinguishable from a short opener, so it is reported as an open/unmatched position (warning says "open/unmatched"). Confirm this is acceptable, or say how to tell them apart.
2. s6 "within 60 seconds": I use pairwise gap, not a window anchored at the first fill. A normal exit on one strike followed within 60 s by a new entry on another strike (a roll) will be tagged multi-leg and excluded. Intended?
3. s5 pnl when fees column partly empty: treated as 0 fee for those fills.
4. docs/ has uncommitted BRAIN edits (SPEC, PROMPTS, HANDOFF, FIXTURES). I committed only HANDOFF.md (which includes BRAIN's pending HANDOFF edits); SPEC/PROMPTS/FIXTURES remain uncommitted.

## 2026-10-29 — BRAIN -> OPS: answers to your 4 SPEC questions + next task
1. Orphan SELL = open/unmatched position: ACCEPTED. Warning wording: "open/unmatched (may be a position opened before this period)".
2. Multi-leg vs roll: CHANGED. A pair qualifies as multi-leg only if both fills have the SAME role: both opening a position, or both closing one.
   A close on one strike followed within 60 s by an open on another strike is a ROLL, not a multi-leg, and must NOT be tagged. Add fixture F9b for this.
3. Partly-empty fees column = 0 for missing fills: ACCEPTED.
4. Commit docs/ edits made by BRAIN as-is (SPEC, PROMPTS, FIXTURES, HANDOFF) at your next commit. Never edit them.
Next: detectors D1-D5, ranking, output object, nudge templates + lint (SPEC s7-s9), tests for F4, F6, F7, F8.

## 2026-10-29 — OPS: multi-leg change, detectors, ranking, nudges done
Passed: 119 pytest cases, all green. One commit per step, pushed to origin main.
- Multi-leg same-role rule applied (a close then an open on another strike within 60 s is a roll, not tagged). F9b added. Fill role = whether the fill reduces the running position on its instrument (a flip counts as close). Open/unmatched warning wording updated per BRAIN. BRAIN's docs/ edits committed as-is.
- engine/detectors.py: D1, D2, D3, D5 always; D4 only if the file has a fees column. One CONFIG dict (W, R, P, OTM_PCT, K, N, MIN_PRIOR, H, MIN_WINNERS, FEE_RATIO, MIN_FLAGGED). Each result has flagged ids, n_flagged, n_total, observed_pnl, baseline_pnl_per_trip, flagged_avg_pnl, evidence, method, notes, status.
- engine/review.py: `analyse(fills, config=None) -> Review` (whole pipeline), `rank_results`, `is_reportable`. Reported only if n_flagged >= 3 AND observed_pnl < 0; sorted by |observed_pnl|, ties by name; max 3; zero -> `no_habit_message = "No costly habit found this period."`. Review carries period, trips, net pnl + gross/net label, win rate, warnings.
- engine/nudges.py: one fixed template per detector + descriptions; lint tests enforce SPEC s9 banned tokens, tone words, underlyings, and "estimate" on every counterfactual. The lint caught "as long as" in the D5 template; reworded.
- Tests: F4, F4b, F4c, F6, F6b, F6c, F7 (12 prior, 5 prior), F8 with the exact FIXTURES values, plus clean trader -> no habit, n_flagged < 3 never reported, hard negatives. No fixture expected value changed; no fixture looks wrong.
- Trips now carry `entry_spot` (spot of the first opening fill) so D2 can use moneyness.

Assumptions:
- D1: prior = the MOST RECENT losing trip (same underlying, any strike) whose exit is at or before T's entry and within W min; flagged if size(T) >= R x size(prior). Not "any" losing trip in the window.
- D2: long trips only; entry date (IST) == expiry. Spot method (>= 1% OTM: CE strike above spot, PE below) only if every expiry-day long entry has spot; otherwise price proxy for all, with a note.
- D3: previous N trips are by entry time across all instruments. For a trip with fewer than 10 prior trips the median of ALL eligible trips in the period (including itself) is used; a note says how many trips used it.
- D5: winners = pnl > 0, losers = pnl < 0, strict ">" against H x median winner hold. Skipped with a note if < 3 winners.
- D4: SPEC gives no flagging threshold, and without one any trader with fees would be "flagged". I added CONFIG FEE_RATIO = 0.2 (fees / sum of |gross pnl| per trip >= 20%). Flagged = trips with fees > 0; observed_pnl = -total fees (exact, no estimate). Please confirm or give a number.
- D4 and D5 carry no "if avoided (estimate)" figure (D4 exact cost, D5 no price path, per SPEC s7). Their rupee figure is still shown as observed INR. D1-D3 show estimate = |observed_pnl|.
- Multi-leg trips are excluded from every detector, including as "prior" trips for D1 and D3 history.
- Header (period, trips, net pnl, win rate) uses all trips including multi-leg; the exclusion count is in warnings.

SPEC ambiguities for BRAIN:
1. s7 D4 "gross profit-and-loss turnover" is undefined; I used the sum of |gross pnl per trip|. No threshold given (see above).
2. s7 D1 "a LOSING trip exit": most recent loser vs any loser in the window. I chose most recent (more conservative).
3. s8 asks for an "estimate INR" per habit but s7 D5 says no counterfactual. I show none for D5 and D4.
4. s7 D3 "fewer than 10 prior trips: whole-period median" — I include the trip itself in that median.
5. Not built yet: the app, synthetic generator, eval script, keep-warm job.

## 2026-10-30 — OPS: synthetic data, app, evals built; localhost works
Passed: 185 pytest cases, all green. App verified on http://localhost:8501 (health 200, page text checked in Chrome; screenshot timed out, so no visual layout check yet). Not deployed. Keep-warm job not started (waits for the app URL).
- engine/synthetic.py: seeded generator (9 archetypes per seed: revenge, expiry gambler, oversizer, loser holder, combined (3 habits), clean control, 3 hard negatives: late re-entry, consistently large size, profitable cheap expiry trades). `python -m engine.synthetic` writes data/synthetic/sample_trades.csv (the combined trader, 54 trips, net -INR 47,020 gross; shows 3 habits).
- engine/loader.py: CSV bytes -> canonical fills; caps 2 MB and 5,000 rows; clean SchemaError messages. .streamlit/config.toml sets maxUploadSize = 2.
- app/main.py: one screen; sample preloaded; "Load sample" button; uploader; threshold sliders (W, R, P, K, H) in an expander; header (period, trades, net P&L with gross/net label, win rate); up to 3 habit cards (rupees, n of N, avg flagged vs other, nudge, evidence table); warnings expander; disclaimer at top and bottom. No Streamlit imports in engine/.
- tools/run_evals.py writes data/synthetic/eval_results.md in the guide format (# | Type | Input | Expected | Actual | Pass/Fail | Fix), 10 cases + a Clarity row marked NOT RUN. Ship bar is in the script header. 4 hand-calculated rupee cases (F2 +1,500; F4 x3 -9,000; F8 -750; F6 -900).
Results (seeds 0-9, 90 synthetic users): all 10 cases PASS; control false habits 0; user-level recall 70/70; hard-negative false habits 0. Trade-level precision/recall: revenge 1.00/1.00, oversizing 1.00/1.00, loser-holding 1.00/1.00, expiry-cheap 0.67/1.00 (the 80 "false positives" are the profitable cheap-expiry trades of the hard-negative user: flagged by the detector but, correctly, never reported because their pnl is positive).
Sweep highlights: W=5 surfaces revenge on only 2/10 seeds, W=45 gives 4 false habits; R>=1.5 surfaces 0/10; P=10 gives 5/10; K=1.5 gives 1 false habit, K=4 gives 3/10. Defaults sit in the stable middle.
Honest caveats: (1) I wrote the generator knowing the detector rules, so the perfect scores are partly circular; they show the implementation does what SPEC says, not that the rules match real behaviour. (2) Clarity test with non-traders is not done and needs a human. (3) Combined sample shows 3 habits and the oversizing one dominates (-INR 26.6k of -47k).
Needs from BRAIN: confirm D4 FEE_RATIO = 0.2 (still an assumption); EVALS.md/ONE_PAGER.md can now be written from data/synthetic/eval_results.md.
Next (OPS, after your go): pin requirements.txt, deploy hello-world -> real app, then keep-warm workflow.

## 2026-10-30 — OPS: deployed, public, keep-warm added
- App live at https://tradereview.streamlit.app/ (Streamlit Community Cloud, public). Verified: cookie-following fetch returns 200; an anonymous headless Chrome (fresh profile, no login) finds the "Post-trade review" heading. Phone and incognito checks by a human still to do.
- requirements.txt pinned (streamlit==1.66.1, pandas==3.1.0); pytest moved to requirements-dev.txt.
- .github/workflows/keepwarm.yml: cron every 6 h (minute 17) + workflow_dispatch; runs tools/keepwarm.py with Playwright (pinned in tools/requirements-keepwarm.txt). Needs repo VARIABLE `APP_URL` = https://tradereview.streamlit.app/ (Settings > Secrets and variables > Actions > Variables). The awake path was tested locally; the "get this app back up" click path could not be tested (app was not asleep).

## 2026-10-30 — BRAIN -> OPS: review of live app + one rule change (SPEC s13)
- Live app looks right on desktop. Answers to your SPEC ambiguities are in SPEC s13 (all accepted).
- BUG vs SPEC principle "never invent a finding": expiry-day card shows flagged avg -701 vs others -900 (flagged is better). Add the third reporting condition in SPEC s13 to review.py.
- Add the overlap caption. Add tests: flagged-better-than-rest is NOT reported; a normal case still is.
- Re-run tools/run_evals.py, regenerate data/synthetic/eval_results.md and report the new numbers honestly even if recall drops. Do not change fixtures or thresholds to rescue a score.
- Commit and push (Streamlit redeploys). Then confirm in HANDOFF what the sample now shows.

## 2026-10-30 — OPS -> BRAIN: SPEC s13 implemented
- review.py: third condition (flagged avg < unflagged avg; skipped when no unflagged trips) applied to D1, D2, D3, D5; D4 fee drag exempt (exact fee total, per SPEC s13 list). Overlap caption added under the habit cards. 3 new tests in tests/test_review.py.
- Sample now shows 2 habits: oversizing (5 of 54, -INR 26,595; -5,319/trade vs -417) and quick re-entry (6 of 54, -INR 8,738; -1,456 vs -798). The expiry-day card is gone, as intended.
- Evals regenerated: cases 1-10 PASS, control 0 false habits, hard negatives 0, ship bar still PASS. BUT user-level recall fell 70/70 (1.00) -> 63/70 (0.90). Fixtures and thresholds untouched.
- pytest: 184 pass, 4 FAIL: test_planted_habits_are_surfaced[combined-0,1,3,4] (the combined archetype no longer surfaces its planted expiry-day habit on seeds 0,1,3,4, since its flagged trips are not worse per trade than the rest). Left failing on purpose; BRAIN to decide whether the combined fixture's expectation or the rule needs revisiting.
- Case 10 string count went 22 -> 21 (fewer habits shown); not a regression.

## 2026-10-30 — OPS -> BRAIN: known limitation recorded, tests green
- 4 combined/expiry-day tests (seeds 0,1,3,4) marked xfail (non-strict) with the agreed reason; not deleted. pytest: 184 passed, 4 xfailed.
- tools/run_evals.py now prints a "Known limitations" section; recall stays 63/70 = 0.90. All 7 misses computed (not hardcoded) as combined archetype / expiry-day habit, seeds 0,1,3,4,5,6,9; 0 misses unexplained. Seeds 5,6,9 are covered only by the eval script (pytest runs seeds 0-4).
- SPEC s13 rule, thresholds, fixtures unchanged. Ship bar still PASS.

## 2026-10-30 — OPS -> BRAIN: docs committed, keepwarm verified
- docs/ committed as-is (0dc158a, "docs: BRAIN updates"; EVALS, ONE_PAGER, SPEC changed) and pushed.
- Repo variable APP_URL is set (https://tradereview.streamlit.app/). keepwarm triggered once via workflow_dispatch: PASSED (run 41056793765). Only annotations: Node 20 deprecation and the ubuntu-latest migration notice. Awake path only; the "wake a sleeping app" click path is still untested.

## 2026-10-30 — BRAIN -> OPS: add collapsed Trade statistics panel (SPEC s14, FIXTURES S1-S5)
- FIRST run `git tag submit-safe` on the current main. It is the fallback if this change goes wrong. Do not delete it.
- Add engine/stats.py and one collapsed expander below the habit cards. No charts. No change to detectors, thresholds, ranking or existing fixtures.
- Tests use the exact expected values in FIXTURES.md S1-S5. Never adjust them to fit the code.
- Add 2 rows to tools/run_evals.py output: S1 (Correctness) and S2/S3 edge. Do not change the ship bar.
- Deadline note: if this is not green and deployed by ~23:00 IST, stop and leave main at submit-safe.

## 2026-10-30 — OPS -> BRAIN: SPEC s14 implemented (tag submit-safe = previous main, pushed)
- engine/stats.py (compute_stats, pure pandas) + collapsed "Trade statistics" expander below the habit cards, grouped Performance / Risk and ratios, tooltips, no charts. Hidden when no trips. Multi-leg trips excluded and counted.
- Tests: tests/test_stats.py uses FIXTURES S1-S5 + S1 addendum exact values, avg_trade_size on F1 (15000) and F1+F2 (13000). Full pytest: 193 passed, 4 xfailed (known limitation).
- Eval table: added row 11 (S1) and row 12 (S2/S3); Clarity is now row 13. Ship bar unchanged and still PASS; recall still 63/70.
- DECISION FOR BRAIN: tests/test_evals.py capped the table at 11 rows (my own sanity bound, not in docs); raised to 13 to allow the two requested rows.
- With fees: pnl is already net, so the headline payoff ratio is computed on gross (pnl+fees) and "after charges" on net pnl. Not covered by a SPEC fixture (unit-tested only). No fees in the sample, so not visible there.
- Sample now shows: 54 trades, win rate 27.8%, net -47,020, payoff 0.59, profit factor 0.23, breakeven win rate 63.0%, max drawdown 47,305, streaks L9/W3, avg size 10,013, multi-leg excluded 0
- Not done: no tests of the Streamlit rendering beyond a headless AppTest run (0 exceptions, expander present).
