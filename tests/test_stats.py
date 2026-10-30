"""Trade statistics (SPEC s14) against hand-calculated FIXTURES S1-S5."""
import pandas as pd
import pytest

from engine.review import analyse_detailed
from engine.stats import compute_stats
from tests.conftest import fill, fills_df


def trips_of(*pnls, size=1000.0, multi=False):
    return pd.DataFrame({
        "pnl": [float(p) for p in pnls], "fees": 0.0, "size": size,
        "exit_ts": pd.date_range("2026-10-01", periods=len(pnls), freq="h"),
        "possible_multi_leg": multi,
    })


S1 = (3000, 1500, -1500, -3000, -900, 3750, -600)


def test_s1_full_statistics():
    s = compute_stats(trips_of(*S1))
    assert (s.trades, s.net_pnl, s.avg_win, s.avg_loss) == (7, 2250, 2750, 1500)
    assert s.win_rate == pytest.approx(3 / 7)
    assert s.payoff_ratio == pytest.approx(2750 / 1500)
    assert s.profit_factor == pytest.approx(8250 / 6000)
    assert s.expectancy == pytest.approx(2250 / 7)
    assert s.breakeven_win_rate == pytest.approx(1 / (1 + 2750 / 1500))
    assert s.max_drawdown == 5400
    assert (s.longest_losing_streak, s.longest_winning_streak) == (3, 2)
    assert (s.largest_win, s.largest_loss) == (3750, 3000)


def test_s1_is_ordered_by_exit_time_not_input_order():
    shuffled = trips_of(*S1).sample(frac=1, random_state=1)
    assert compute_stats(shuffled).max_drawdown == 5400


def test_s2_no_losers():
    s = compute_stats(trips_of(100, 200))
    assert s.win_rate == 1.0 and s.expectancy == 150 and s.max_drawdown == 0
    assert s.avg_loss is None and s.payoff_ratio is None
    assert s.profit_factor is None and s.breakeven_win_rate is None


def test_s3_no_winners():
    s = compute_stats(trips_of(-100, -200))
    assert s.win_rate == 0 and s.avg_win == 0 and s.payoff_ratio == 0.0 and s.profit_factor == 0.0
    assert s.expectancy == -150 and s.max_drawdown == 300 and s.longest_losing_streak == 2


def test_s4_zero_pnl_counts_as_trade_only():
    s = compute_stats(trips_of(100, 0, -50))
    assert s.trades == 3 and s.win_rate == pytest.approx(1 / 3)
    assert s.avg_win == 100 and s.avg_loss == 50


def test_s5_no_trips_gives_no_stats():
    assert compute_stats(trips_of()) is None


def test_multi_leg_trips_are_excluded_and_counted():
    both = pd.concat([trips_of(100, -50), trips_of(999, multi=True)], ignore_index=True)
    s = compute_stats(both)
    assert s.trades == 2 and s.n_multi_leg_excluded == 1 and s.net_pnl == 50
    assert compute_stats(trips_of(5, multi=True)) is None


def test_payoff_after_charges_only_with_fees():
    t = trips_of(110, -90)
    t["fees"] = 10.0                      # gross +120 / -80, net +110 / -90
    s = compute_stats(t, has_fees=True)
    assert s.payoff_ratio == pytest.approx(120 / 80)
    assert s.payoff_ratio_after_charges == pytest.approx(110 / 90)
    assert compute_stats(t).payoff_ratio_after_charges is None


def _trips(*rows):
    return analyse_detailed(fills_df(*rows))[1]


F1 = (fill("10:00", "BUY", 150, 100), fill("10:30", "SELL", 150, 120))
F2 = (fill("10:00", "BUY", 100, 50, strike=24600), fill("10:05", "BUY", 100, 60, strike=24600),
      fill("10:20", "SELL", 150, 70, strike=24600), fill("10:40", "SELL", 50, 40, strike=24600))


def test_avg_trade_size_f1_and_f1_plus_f2():
    assert compute_stats(_trips(*F1)).avg_trade_size == 15000
    assert compute_stats(_trips(*F1, *F2)).avg_trade_size == 13000
