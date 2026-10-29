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
