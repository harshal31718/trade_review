# PROMPTS: what I sent to the build agent (Claude Code, "OPS"), as-is

I worked with two Claude sessions. BRAIN wrote the spec, hand-calculated test fixtures and docs, and drafted the prompts below. OPS wrote code, tests and deployment. I pasted each prompt into OPS. BRAIN's longer instructions also reached OPS as dated entries in `docs/HANDOFF.md` (SPEC v0.2, the multi-leg ruling, SPEC s13).

**Not captured here:** the prompts that produced the synthetic data generator, the Streamlit app, the eval script, the deployment and the keep-warm job. I sent those straight to OPS and have not exported them yet. They are not in this file, and I have not reconstructed them.

| # | Prompt (as-is) | What happened | What I changed next |
|---|---|---|---|
| P-001 | See below | Folder layout, .gitignore, pinned deps, venv, hello-world app, first push. | Wrote the spec (SPEC.md) and hand-calculated fixtures (FIXTURES.md) before asking for any real code. |
| P-002 | See below | Schema, mapper registry, FIFO pairing and multi-leg tagging built; 51 tests passed. OPS raised 4 spec ambiguities. One was a real flaw in my spec: a roll (close one strike, open another within 60 s) was tagged as a multi-leg spread and dropped from analysis. | Changed the rule so a pair counts as multi-leg only if both fills open or both close. Added fixture F9b. |
| P-003 | See below | Detectors, ranking, nudge templates and lint tests built; 185 tests passed. | Reviewed the live app myself. Found a card that contradicted itself (see P-004). |
| P-004 | See below | **Failed my own standard first:** the live app reported an expiry-day habit whose trades lost less per trade than the rest. After the rule change, recall fell from 70/70 to 63/70 and 4 tests failed. | Kept the rule. Did not tune thresholds to recover the score. See P-005. |
| P-005 | See below | The 4 failing tests marked as known limitations with a reason; eval script now prints a Known limitations section; 184 passed, 4 xfailed. | Listed "compare return on premium" as the next fix in the one-pager. |
| P-006 | See below | Docs committed; keep-warm workflow ran once and passed. | Not tested: the wake-a-sleeping-app path. |

## P-001
~~~
You are OPS. You own app/, engine/, data/, tests/, git, and deploy. You never edit docs/ except to APPEND dated entries to docs/HANDOFF.md. Read docs/HANDOFF.md and docs/SPEC.md first.
Project: post-trade review tool (Python + Streamlit). engine/ is pure Python with no Streamlit imports; app/ only calls engine/. Do now: (1) create the folder layout app/, engine/, data/synthetic/, data/real/, tests/; (2) add .gitignore (ignore data/real/, .venv, __pycache__, .env); (3) create requirements.txt with streamlit, pandas, pytest; (4) set up a .venv; (5) add a hello-world Streamlit app in app/main.py; (6) commit and push to origin main. Report what you did by appending to docs/HANDOFF.md.
~~~

## P-002
~~~
Read docs/HANDOFF.md, docs/SPEC.md (v0.2, esp. sections 4-7 and 12) and docs/FIXTURES.md. Do NOT edit anything in docs/ except appending a dated entry to docs/HANDOFF.md.

Task, in this order, stopping after each step to run tests:
1. engine/schema.py: canonical schema + validation per SPEC section 4. Clear errors for missing columns or empty file (fixture F10).
2. engine/mappers/: registry with only the `canonical` mapper for now. No groww mapper yet.
3. engine/pairing.py: FIFO pairing into flat-to-flat trips per SPEC section 5, long and short, with the unmatched/open-position warnings (fixtures F1, F2, F3, F5).
4. engine/multileg.py: multi-leg tagging per SPEC section 6 (fixture F9).
5. tests/test_pairing.py etc.: turn FIXTURES.md into pytest cases using the exact expected values given. If a test fails, fix the code, never the expected value. If you believe a fixture itself is wrong, append the question to docs/HANDOFF.md and wait.

Rules: engine/ has no Streamlit imports. Pandas only, no heavy deps. Commit after each passing step with a clear message and push to origin main. When done, append to docs/HANDOFF.md: what passed, what you assumed, anything in SPEC that was ambiguous.
~~~

## P-003
~~~
Read docs/HANDOFF.md (latest BRAIN entry), docs/SPEC.md sections 7-9 and 12, and docs/FIXTURES.md. Do NOT edit docs/ except appending to docs/HANDOFF.md.

First: apply BRAIN's multi-leg change (same-role rule, roll is not multi-leg), add fixture F9b, keep all 51 tests green. Commit.

Then build, one commit per step, tests after each:
1. engine/detectors.py: D1 revenge_reentry, D2 expiry_day_cheap_premium, D3 oversizing, D5 loser_holding. D4 fee_drag only if a fees column is present. One CONFIG dict holds every threshold (W, R, P, K, N, H). Each detector returns flagged trip ids, n_flagged, observed_pnl, baseline pnl per unflagged trip, evidence rows, and which method was used (price proxy vs spot).
2. engine/review.py: ranking per SPEC s7. Report a habit only if n_flagged >= 3 AND observed_pnl < 0. Sort by |observed_pnl|, max 3. Zero qualifying habits returns an explicit "no costly habit found" result. Output object per SPEC s8, including the warnings list.
3. engine/nudges.py: one fixed template per detector. Tone is kind and non-judgmental. Describe behaviour only, never an instrument or direction. Any counterfactual rupee figure includes the word "estimate". Template example in SPEC s9.
4. tests: F4, F4b, F4c, F6, F6b, F6c, F7, F8 with the exact expected values in FIXTURES.md; a nudge lint test enforcing the banned-token list in SPEC s9; a test that a clean trader returns "no costly habit found"; a test that n_flagged < 3 is never reported.

Rules: engine/ has no Streamlit imports. If a fixture seems wrong, append the question to HANDOFF and wait; never change expected values. When done, append to HANDOFF: tests passed, assumptions made, SPEC ambiguities.
~~~

## P-004
~~~
Read docs/HANDOFF.md (latest BRAIN entry) and docs/SPEC.md section 13. Do NOT edit docs/ except appending to docs/HANDOFF.md.
1. In engine/review.py add the third reporting condition (flagged avg pnl < unflagged avg pnl; skip if no unflagged trips) for D1, D2, D3, D5.
2. Add the overlap caption under the habit cards in app/main.py: "Habits can overlap, so these rupee figures should not be added together."
3. Tests: a case where flagged trips beat the rest is NOT reported; a normal case still is.
4. Re-run tools/run_evals.py, regenerate data/synthetic/eval_results.md, and report the new numbers honestly even if recall drops. Do not change fixtures or thresholds to rescue a score.
5. Commit, push, confirm the deploy, and append to HANDOFF what the sample now shows.
~~~

## P-005
~~~
Read docs/HANDOFF.md (latest BRAIN entry). Do NOT edit docs/ except appending to docs/HANDOFF.md.
Keep the SPEC s13 rule and all thresholds and fixtures unchanged.
1. For the 4 failing tests (combined archetype, expiry-day habit, seeds 0,1,3,4): mark them xfail with reason "known limitation: rupees-per-trade comparison under-measures cheap-premium habits in a mixed trader; fix = compare return on premium". Do not delete them.
2. Make tools/run_evals.py print a "Known limitations" section listing this, and show recall as 63/70 with the 7 misses attributed to it.
3. Full pytest must be green (xfails allowed). Commit, push, confirm deploy, append to HANDOFF.
~~~

## P-006
~~~
Commit docs/ exactly as it is now (ONE_PAGER, SPEC, EVALS, FIXTURES, PROMPTS, HANDOFF) with message "docs: BRAIN updates" and push. Do not edit them. If APP_URL is set as a repo variable, trigger the keepwarm workflow once with workflow_dispatch and report whether it passed. Append the result to docs/HANDOFF.md.
~~~
