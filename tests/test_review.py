"""Ranking and output-object tests (SPEC s7-s8)."""
import pandas as pd
import pytest

from engine.detectors import CONFIG, DetectorResult
from engine.review import MAX_HABITS, NO_HABIT_MESSAGE, analyse, is_reportable, rank_results
from tests.conftest import fill, fills_df


def result(name, n, pnl, status="ok"):
    return DetectorResult(
        name=name, status=status, flagged_trip_ids=tuple(range(n)), n_flagged=n, n_total=20,
        observed_pnl=pnl, baseline_pnl_per_trip=50.0, flagged_avg_pnl=pnl / n if n else None,
        evidence=pd.DataFrame(columns=["trip_id", "entry_ts", "instrument", "size", "pnl"]),
        method="x",
    )


def test_needs_three_flagged_and_negative_pnl():
    assert not is_reportable(result("a", 2, -9000), CONFIG)       # n < 3
    assert not is_reportable(result("a", 5, 400), CONFIG)         # profitable
    assert not is_reportable(result("a", 5, 0), CONFIG)           # break-even is not a cost
    assert not is_reportable(result("a", 5, -100, status="skipped"), CONFIG)
    assert is_reportable(result("a", 3, -1), CONFIG)


def test_ranked_by_abs_pnl_desc_and_capped_at_three():
    rs = {n: result(n, 3, p) for n, p in [("a", -100), ("b", -900), ("c", -500), ("d", -700)]}
    ranked = rank_results(rs, CONFIG)
    assert [r.name for r in ranked] == ["b", "d", "c"]
    assert len(ranked) == MAX_HABITS


def test_ties_break_by_name_for_determinism():
    rs = {n: result(n, 3, -500) for n in ("z", "a")}
    assert [r.name for r in rank_results(rs, CONFIG)] == ["a", "z"]


def revenge_day(start_hour, n_pairs):
    """n_pairs of (small loser, immediate bigger loser re-entry); returns fill rows."""
    rows = []
    for i in range(n_pairs):
        h = start_hour + i
        rows += [
            fill(f"{h}:00", "BUY", 75, 100), fill(f"{h}:10", "SELL", 75, 90),     # -750, size 7500
            fill(f"{h}:15", "BUY", 150, 100), fill(f"{h}:30", "SELL", 150, 90),   # -1500, size 15000, 5 min gap
        ]
    return rows


def test_analyse_reports_revenge_with_rupees_and_header():
    review = analyse(fills_df(*revenge_day(9, 3)))
    assert review.n_trips == 6
    assert review.net_pnl == pytest.approx(-(750 + 1500) * 3)
    assert review.pnl_label == "gross, before charges"
    assert review.win_rate == 0.0
    habit = next(h for h in review.habits if h.name == "revenge_reentry")
    assert habit.n_flagged == 3 and habit.n_total == 6
    assert habit.observed_pnl == pytest.approx(-4500)
    assert habit.estimate_pnl == pytest.approx(4500)
    assert habit.flagged_avg_pnl == pytest.approx(-1500)
    assert habit.unflagged_avg_pnl == pytest.approx(-750)
    assert len(habit.evidence) <= 5
    assert review.no_habit_message is None


def test_two_flagged_trips_are_never_reported():
    review = analyse(fills_df(*revenge_day(9, 2)))
    assert "revenge_reentry" not in [h.name for h in review.habits]


def clean_trader_fills():
    rows = []
    for i in range(12):
        day = f"2026-10-{1 + i:02d}"
        rows += [fill("10:00", "BUY", 75, 100, day=day), fill("10:30", "SELL", 75, 104 if i % 3 else 97, day=day)]
    return rows


def test_clean_trader_gets_explicit_no_costly_habit():
    review = analyse(fills_df(*clean_trader_fills()))
    assert review.habits == ()
    assert review.no_habit_message == NO_HABIT_MESSAGE == "No costly habit found this period."
    assert not review.has_habits


def test_warnings_collected_including_proxy_and_gross_label():
    review = analyse(fills_df(*clean_trader_fills(), fill("15:00", "BUY", 75, 100, day="2026-10-20")))
    text = " ".join(review.warnings)
    assert "open/unmatched" in text
    assert "gross" in text
    assert "price proxy" in text


def test_fees_present_labels_net_and_drops_gross_warning():
    review = analyse(fills_df(fill("10:00", "BUY", 75, 100, fees=10), fill("10:30", "SELL", 75, 110, fees=10)))
    assert review.pnl_label == "net of charges"
    assert review.net_pnl == pytest.approx(750 - 20)
    assert not any("gross" in w for w in review.warnings)


def test_no_trips_is_handled():
    review = analyse(fills_df(fill("10:00", "BUY", 75, 100)))
    assert review.n_trips == 0 and review.win_rate is None and review.period_start is None
    assert review.no_habit_message == NO_HABIT_MESSAGE


def test_config_override_changes_outcome():
    fills = fills_df(*revenge_day(9, 3))
    assert any(h.name == "revenge_reentry" for h in analyse(fills).habits)
    assert not any(h.name == "revenge_reentry" for h in analyse(fills, {"W": 1}).habits)
