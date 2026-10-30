"""The eval table cases must stay green (tools/run_evals.py is the full report)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import run_evals  # noqa: E402


def test_every_eval_case_passes():
    results = [case() for case in run_evals.CASES]
    failed = [(i + 1, r[0], r[3]) for i, r in enumerate(results) if not r[4]]
    assert failed == []
    assert 6 <= len(results) + 1 <= 11
