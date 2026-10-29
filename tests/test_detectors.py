"""Detector tests. Expected values are copied from docs/FIXTURES.md; never adjust them to fit the code."""
import pytest

from engine.detectors import (
    CONFIG, detect_expiry_cheap_premium, detect_fee_drag, detect_loser_holding,
    detect_oversizing, detect_revenge_reentry, run_detectors,
)
from engine.multileg import flag_trips, tag_multileg
from engine.pairing import pair_trips
from tests.conftest import fill, fills_df


def trips_from(*rows):
    return pair_trips(fills_df(*rows)).trips


def round_trip(t_in, t_out, qty, p_in, p_out, **kw):
    return [fill(t_in, "BUY", qty, p_in, **kw), fill(t_out, "SELL", qty, p_out, **kw)]


# F4 / F4b / F4c: D1 revenge_reentry -----------------------------------------
def f4_trips(b_entry="10:20", b_qty=150, b_exit="10:50"):
    return trips_from(
        *round_trip("10:00", "10:10", 75, 100, 80),
        *round_trip(b_entry, b_exit, b_qty, 90, 70),
    )


def test_f4_b_flagged_a_not_and_not_reportable():
    trips = f4_trips()
    res = detect_revenge_reentry(trips)
    assert res.n_flagged == 1
    assert res.flagged_trip_ids == (1,)          # B
    assert res.n_total == 2
    assert res.observed_pnl == pytest.approx(-3000)
    assert res.baseline_pnl_per_trip == pytest.approx(-1500)


def test_f4b_twenty_minute_gap_not_flagged():
    res = detect_revenge_reentry(f4_trips(b_entry="10:30", b_exit="11:00"))
    assert res.n_flagged == 0


def test_f4c_smaller_size_not_flagged():
    res = detect_revenge_reentry(f4_trips(b_qty=75))   # size 6750 < 7500
    assert res.n_flagged == 0


def test_d1_threshold_overrides_apply():
    assert detect_revenge_reentry(f4_trips(b_entry="10:30", b_exit="11:00"), {"W": 20}).n_flagged == 1
    assert detect_revenge_reentry(f4_trips(), {"R": 2.0}).n_flagged == 0


def test_d1_prior_must_be_a_loser():
    trips = trips_from(
        *round_trip("10:00", "10:10", 75, 100, 120),
        *round_trip("10:12", "10:30", 150, 90, 70),
    )
    assert detect_revenge_reentry(trips).n_flagged == 0


def test_d1_other_underlying_does_not_count():
    trips = trips_from(
        *round_trip("10:00", "10:10", 75, 100, 80, underlying="BANKNIFTY"),
        *round_trip("10:20", "10:50", 150, 90, 70),
    )
    assert detect_revenge_reentry(trips).n_flagged == 0


def test_d1_other_strike_same_underlying_counts():
    trips = trips_from(
        *round_trip("10:00", "10:10", 75, 100, 80, strike=24000),
        *round_trip("10:20", "10:50", 150, 90, 70, strike=24500),
    )
    assert detect_revenge_reentry(trips).flagged_trip_ids == (1,)


def test_d1_entry_before_prior_exit_is_not_a_reentry():
    trips = trips_from(
        fill("10:00", "BUY", 75, 100, strike=24000), fill("10:05", "BUY", 150, 90),
        fill("10:10", "SELL", 75, 80, strike=24000), fill("10:50", "SELL", 150, 70),
    )
    assert detect_revenge_reentry(trips).n_flagged == 0


# F6 / F6b / F6c: D2 expiry-day cheap premium -----------------------------------
def f6_trips(day="2026-11-04", price=12, sell=0):
    return trips_from(
        fill("10:00", "BUY", 75, price, day=day), fill("14:00", "SELL", 75, sell, day=day),
    )


def test_f6_flagged():
    trips = f6_trips()
    res = detect_expiry_cheap_premium(trips)
    assert res.n_flagged == 1
    assert res.observed_pnl == pytest.approx(-900)
    assert res.method == "price_proxy"


def test_f6b_non_expiry_date_not_flagged():
    assert detect_expiry_cheap_premium(f6_trips(day="2026-11-03")).n_flagged == 0


def test_f6c_entry_price_45_not_flagged():
    assert detect_expiry_cheap_premium(f6_trips(price=45, sell=10)).n_flagged == 0


def test_d2_only_buys_flagged():
    trips = trips_from(
        fill("10:00", "SELL", 75, 12, day="2026-11-04"), fill("14:00", "BUY", 75, 0, day="2026-11-04"),
    )
    assert detect_expiry_cheap_premium(trips).n_flagged == 0


def test_d2_uses_spot_moneyness_when_present():
    day = "2026-11-04"
    trips = trips_from(
        # CE 24500 with spot 24000 -> 2.1% OTM, price 100 (proxy would NOT flag)
        fill("10:00", "BUY", 75, 100, day=day, spot=24000), fill("11:00", "SELL", 75, 50, day=day, spot=24000),
        # CE 24100 with spot 24000 -> 0.4% OTM, price 10 (proxy WOULD flag)
        fill("12:00", "BUY", 75, 10, day=day, strike=24100, spot=24000),
        fill("13:00", "SELL", 75, 5, day=day, strike=24100, spot=24000),
    )
    res = detect_expiry_cheap_premium(trips)
    assert res.method == "spot_moneyness"
    assert res.flagged_trip_ids == (0,)


def test_d2_pe_otm_when_strike_below_spot():
    day = "2026-11-04"
    trips = trips_from(
        fill("10:00", "BUY", 75, 100, day=day, option_type="PE", strike=23700, spot=24000),
        fill("11:00", "SELL", 75, 50, day=day, option_type="PE", strike=23700, spot=24000),
    )
    assert detect_expiry_cheap_premium(trips).n_flagged == 1


# F7: D3 oversizing ------------------------------------------------------------
def f7_trips(n_prior, last_qty):
    rows = []
    for i in range(n_prior):
        rows += round_trip(f"{9 + i // 6}:{(i % 6) * 10:02d}", f"{9 + i // 6}:{(i % 6) * 10 + 5:02d}", 100, 100, 101)
    rows += round_trip("14:00", "14:05", last_qty, 100, 101)
    return trips_from(*rows)


def test_f7_25000_flagged_against_12_prior_of_10000():
    res = detect_oversizing(f7_trips(12, 250))
    assert res.flagged_trip_ids == (12,)
    assert res.n_flagged == 1


def test_f7_19000_not_flagged():
    assert detect_oversizing(f7_trips(12, 190)).n_flagged == 0


def test_f7_only_5_prior_uses_whole_period_median_and_says_so():
    res = detect_oversizing(f7_trips(5, 250))
    assert res.flagged_trip_ids == (5,)
    assert any("whole-period median" in n for n in res.notes)


def test_f7_lookback_is_last_n_trips_only():
    # 30 small trips then 20 large ones: a large trip is judged against the last N=20, not all history.
    rows = []
    for i in range(30):
        rows += round_trip(f"{9 + i // 6}:{(i % 6) * 10:02d}", f"{9 + i // 6}:{(i % 6) * 10 + 5:02d}", 100, 100, 101)
    for i in range(21):
        rows += round_trip(f"{15 + i // 6}:{(i % 6) * 10:02d}", f"{15 + i // 6}:{(i % 6) * 10 + 5:02d}", 300, 100, 101)
    res = detect_oversizing(trips_from(*rows))
    assert res.n_flagged > 0
    assert 50 not in res.flagged_trip_ids   # the 21st large trip: median of previous 20 is large


# F8: D5 loser holding ------------------------------------------------------------
def f8_trips(loser_holds=(30, 20), winner_holds=(10, 12, 14)):
    rows, start = [], 9 * 60
    for hold, win in [(h, True) for h in winner_holds] + [(h, False) for h in loser_holds]:
        t_in, t_out = start, start + hold
        rows += round_trip(f"{t_in // 60}:{t_in % 60:02d}", f"{t_out // 60}:{t_out % 60:02d}",
                           75, 100, 110 if win else 90)
        start += 60
    return trips_from(*rows)


def test_f8_30_min_loser_flagged_20_min_loser_not():
    res = detect_loser_holding(f8_trips())
    assert res.n_flagged == 1
    flagged = res.evidence.iloc[0]
    assert flagged["pnl"] == pytest.approx(-750)
    held = f8_trips().set_index("trip_id").loc[list(res.flagged_trip_ids), "hold_minutes"]
    assert held.tolist() == [30]
    assert res.observed_pnl == pytest.approx(-750)


def test_f8_needs_three_winners():
    res = detect_loser_holding(f8_trips(winner_holds=(10, 12)))
    assert res.status == "skipped" and res.n_flagged == 0
    assert any("3 winning" in n for n in res.notes)


def test_f8_exactly_h_times_median_is_not_flagged():
    assert detect_loser_holding(f8_trips(loser_holds=(24,))).n_flagged == 0


# Multi-leg exclusion and run_detectors --------------------------------------------
def test_multileg_trips_are_excluded_from_detectors():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 12, day="2026-11-04", strike=24500),
        fill("10:00:20", "SELL", 75, 5, day="2026-11-04", strike=24800),
        fill("14:00", "SELL", 75, 0, day="2026-11-04", strike=24500),
        fill("14:00:30", "BUY", 75, 0, day="2026-11-04", strike=24800),
    )
    tagged = tag_multileg(fills).fills
    trips = flag_trips(pair_trips(tagged).trips, tagged)
    assert trips["possible_multi_leg"].all()
    res = detect_expiry_cheap_premium(trips)
    assert res.n_total == 0 and res.n_flagged == 0


def test_run_detectors_skips_fee_drag_without_fees_column():
    names = set(run_detectors(f4_trips()))
    assert names == {"revenge_reentry", "expiry_day_cheap_premium", "oversizing", "loser_holding"}
    assert "fee_drag" in run_detectors(f4_trips(), has_fees=True)


def test_baseline_is_mean_of_unflagged():
    res = detect_loser_holding(f8_trips())
    assert res.baseline_pnl_per_trip == pytest.approx((750 * 3 - 750) / 4)


def test_config_holds_every_threshold():
    assert {"W", "R", "P", "K", "N", "H"} <= set(CONFIG)


def test_fee_drag_flags_only_above_ratio_and_cost_is_exact_fees():
    rows = []
    for i in range(4):
        rows += round_trip(f"10:{i * 10:02d}", f"10:{i * 10 + 5:02d}", 100, 100, 101, fees=40)
    res = detect_fee_drag(trips_from(*rows))      # fees 320 vs gross turnover 400 -> 80%
    assert res.n_flagged == 4 and res.observed_pnl == pytest.approx(-320)
    rows = []
    for i in range(4):
        rows += round_trip(f"10:{i * 10:02d}", f"10:{i * 10 + 5:02d}", 100, 100, 150, fees=20)
    assert detect_fee_drag(trips_from(*rows)).n_flagged == 0  # 80 / 20000
