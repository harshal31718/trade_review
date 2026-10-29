"""Nudge lint (SPEC s9, s12.3): banned tokens, tone, 'estimate' on every rupee counterfactual."""
import re

import pandas as pd
import pytest

from engine.detectors import (
    CONFIG, EXPIRY_CHEAP, FEE_DRAG, LOSER_HOLDING, OVERSIZING, REVENGE, DetectorResult,
)
from engine.nudges import DESCRIPTIONS, NO_COUNTERFACTUAL, TEMPLATES, render_nudge
from engine.review import analyse
from tests.conftest import fill, fills_df

NAMES = [REVENGE, EXPIRY_CHEAP, OVERSIZING, LOSER_HOLDING, FEE_DRAG]
BANNED_WORDS = ["buy", "sell", "short", "long", "call", "put", "bullish", "bearish"]
BANNED_PHRASES = ["should trade", "avoid trading"]
TONE_BANNED = ["gambled", "gambling", "reckless", "stupid", "revenge", "foolish", "greedy"]
UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "MIDCPNIFTY", "BANKEX"]


def result(name, method="price_proxy", notes=()):
    return DetectorResult(
        name=name, status="ok", flagged_trip_ids=(1, 2, 3, 4, 5, 6, 7), n_flagged=7, n_total=30,
        observed_pnl=-8400.0, baseline_pnl_per_trip=10.0, flagged_avg_pnl=-1200.0,
        evidence=pd.DataFrame(), method=method, notes=tuple(notes),
    )


def all_rendered():
    out = []
    for name in NAMES:
        notes = ("Fees were 34% of gross profit-and-loss turnover.",) if name == FEE_DRAG else ()
        methods = ["price_proxy", "spot_moneyness"] if name == EXPIRY_CHEAP else ["x"]
        for method in methods:
            res = result(name, method, notes)
            estimate = None if name in NO_COUNTERFACTUAL else 8400.0
            out.append(render_nudge(res, CONFIG, estimate))
    return out


def lint(text):
    problems = []
    for word in BANNED_WORDS + TONE_BANNED + UNDERLYINGS:
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            problems.append(word)
    problems += [p for p in BANNED_PHRASES if p in text.lower()]
    return problems


def test_every_detector_has_a_template_and_description():
    assert set(TEMPLATES) == set(NAMES) == set(DESCRIPTIONS)


@pytest.mark.parametrize("text", all_rendered() + list(TEMPLATES.values()) + list(DESCRIPTIONS.values()))
def test_no_banned_tokens_or_unkind_words(text):
    assert lint(text) == []


@pytest.mark.parametrize("text", all_rendered())
def test_no_digit_free_or_empty_nudges(text):
    assert re.search(r"INR [\d,]+", text)


def test_rupee_counterfactual_always_says_estimate():
    for name in NAMES:
        text = render_nudge(result(name, notes=("Fees were 34% of x",)), CONFIG,
                            None if name in NO_COUNTERFACTUAL else 8400.0)
        has_plus = "+INR" in text or "if avoided" in text.lower()
        assert has_plus == (name not in NO_COUNTERFACTUAL)
        if has_plus:
            assert "estimate" in text


def test_matches_spec_example_for_revenge():
    text = render_nudge(result(REVENGE), CONFIG, 8400.0)
    assert text.startswith(
        "7 trades were opened within 15 minutes of a loss, at equal or larger size, and lost INR 8,400 net. "
        "A fixed pause after a loss is one way people interrupt this pattern."
    )


def test_lint_catches_violations():
    assert lint("You should buy NIFTY calls") != []
    assert lint("This was reckless") == ["reckless"]


def test_nudges_from_a_real_review_pass_lint_and_have_rupees():
    rows = []
    for i in range(3):
        h = 9 + i
        rows += [fill(f"{h}:00", "BUY", 75, 100), fill(f"{h}:10", "SELL", 75, 90),
                 fill(f"{h}:15", "BUY", 150, 100), fill(f"{h}:30", "SELL", 150, 90)]
    review = analyse(fills_df(*rows))
    assert review.habits
    for habit in review.habits:
        assert lint(habit.nudge) == []
        assert "INR" in habit.nudge
        assert "estimate" in habit.nudge or habit.estimate_pnl is None
