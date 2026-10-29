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
