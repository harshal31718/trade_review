"""FIFO pairing tests. Expected values are copied from docs/FIXTURES.md; never adjust them to fit the code."""
import pytest

from engine.pairing import TRIP_COLUMNS, pair_trips
from tests.conftest import fill, fills_df


def one_trip(*rows):
    result = pair_trips(fills_df(*rows))
    assert len(result.trips) == 1
    return result.trips.iloc[0], result


def test_f1_simple_long():
    trip, result = one_trip(fill("10:00", "BUY", 150, 100), fill("10:30", "SELL", 150, 120))
    assert trip["pnl"] == pytest.approx(3000)
    assert trip["size"] == pytest.approx(15000)
    assert trip["hold_minutes"] == pytest.approx(30)
    assert trip["direction"] == "long"
    assert result.open_positions.empty


def test_f2_fifo_with_partial_exits():
    trip, _ = one_trip(
        fill("10:00", "BUY", 100, 50), fill("10:05", "BUY", 100, 60),
        fill("10:20", "SELL", 150, 70), fill("10:40", "SELL", 50, 40),
    )
    assert trip["pnl"] == pytest.approx(1500)
    assert trip["entry_ts"].strftime("%H:%M") == "10:00"
    assert trip["exit_ts"].strftime("%H:%M") == "10:40"
    assert trip["hold_minutes"] == pytest.approx(40)
    assert trip["entry_price"] == pytest.approx(55)
    assert trip["exit_price"] == pytest.approx(62.5)
    assert trip["size"] == pytest.approx(11000)
    assert trip["qty"] == 200


def test_f3_short_first():
    trip, _ = one_trip(fill("11:00", "SELL", 75, 200), fill("11:20", "BUY", 75, 150))
    assert trip["direction"] == "short"
    assert trip["pnl"] == pytest.approx(3750)
    assert trip["hold_minutes"] == pytest.approx(20)
    assert trip["size"] == pytest.approx(15000)


def test_f4_revenge_pairing_gives_two_trips():
    # Pairing part only; the D1 flag itself belongs to the detector step.
    result = pair_trips(fills_df(
        fill("10:00", "BUY", 75, 100), fill("10:10", "SELL", 75, 80),
        fill("10:20", "BUY", 150, 90), fill("10:50", "SELL", 150, 70),
    ))
    a, b = result.trips.iloc[0], result.trips.iloc[1]
    assert len(result.trips) == 2
    assert (a["pnl"], a["size"]) == (pytest.approx(-1500), pytest.approx(7500))
    assert a["exit_ts"].strftime("%H:%M") == "10:10"
    assert (b["pnl"], b["size"]) == (pytest.approx(-3000), pytest.approx(13500))


def test_f5_open_position_is_not_a_trip():
    result = pair_trips(fills_df(fill("10:00", "BUY", 75, 100)))
    assert len(result.trips) == 0
    assert list(result.trips.columns) == list(TRIP_COLUMNS)
    assert len(result.open_positions) == 1
    assert len([w for w in result.warnings if "open/unmatched" in w]) == 1
    assert result.warnings[0].startswith("1 open/unmatched position")


def test_f6_expired_worthless_pairing():
    result = pair_trips(fills_df(
        fill("10:00", "BUY", 75, 12, day="2026-11-04"),
        fill("14:00", "SELL", 75, 0, day="2026-11-04"),
    ))
    assert result.trips.iloc[0]["pnl"] == pytest.approx(-900)
    assert result.trips.iloc[0]["entry_price"] == pytest.approx(12)


# Beyond the fixtures: structural behaviour of flat-to-flat pairing --------
def test_partially_closed_position_at_end_is_open_not_a_trip():
    result = pair_trips(fills_df(fill("10:00", "BUY", 100, 50), fill("10:10", "SELL", 40, 60)))
    assert len(result.trips) == 0
    assert result.open_positions.iloc[0]["qty"] == 60


def test_two_separate_cycles_make_two_trips():
    result = pair_trips(fills_df(
        fill("10:00", "BUY", 75, 100), fill("10:10", "SELL", 75, 110),
        fill("11:00", "BUY", 75, 100), fill("11:10", "SELL", 75, 90),
    ))
    assert result.trips["pnl"].tolist() == [pytest.approx(750), pytest.approx(-750)]
    assert result.trips["trip_id"].tolist() == [0, 1]


def test_position_flip_closes_one_trip_and_opens_another():
    result = pair_trips(fills_df(
        fill("10:00", "BUY", 75, 100), fill("10:10", "SELL", 150, 110),
        fill("10:20", "BUY", 75, 100),
    ))
    assert len(result.trips) == 2
    assert result.trips.iloc[0]["pnl"] == pytest.approx(750)
    short = result.trips.iloc[1]
    assert short["direction"] == "short"
    assert short["pnl"] == pytest.approx(75 * 10)
    assert short["qty"] == 75


def test_instruments_are_paired_independently():
    result = pair_trips(fills_df(
        fill("10:00", "BUY", 75, 100, strike=24500), fill("10:01", "BUY", 75, 50, strike=24600),
        fill("10:10", "SELL", 75, 110, strike=24500), fill("10:11", "SELL", 75, 40, strike=24600),
    ))
    by_strike = result.trips.set_index("strike")["pnl"]
    assert by_strike[24500] == pytest.approx(750)
    assert by_strike[24600] == pytest.approx(-750)


def test_fees_reduce_pnl_and_are_split_across_a_flip():
    trip, _ = one_trip(
        fill("10:00", "BUY", 100, 50, fees=10), fill("10:10", "SELL", 100, 60, fees=10),
    )
    assert trip["pnl"] == pytest.approx(1000 - 20)
    assert trip["fees"] == pytest.approx(20)


def test_fills_in_trip_are_recorded():
    trip, _ = one_trip(fill("10:00", "BUY", 75, 100), fill("10:10", "SELL", 75, 110))
    assert tuple(trip["fill_ids"]) == (0, 1)


def test_scale_in_after_partial_exit_stays_one_trip():
    trip, _ = one_trip(
        fill("10:00", "BUY", 100, 50), fill("10:05", "SELL", 50, 60),
        fill("10:10", "BUY", 50, 70), fill("10:20", "SELL", 100, 80),
    )
    # FIFO: 50*(60-50) + 50*(80-50) + 50*(80-70) = 500+1500+500
    assert trip["pnl"] == pytest.approx(2500)
    assert trip["qty"] == 150
