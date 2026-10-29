"""End-to-end through CSV -> mapper -> multi-leg -> pairing, using FIXTURES.md values."""
import io

import pandas as pd
import pytest

from engine.mappers import map_to_canonical
from engine.multileg import flag_trips, tag_multileg
from engine.pairing import pair_trips

CSV = """ts,underlying,option_type,strike,expiry,side,qty,price
2026-10-28 10:00:00,NIFTY,CE,24500,2026-11-04,BUY,100,50
2026-10-28 10:05:00,NIFTY,CE,24500,2026-11-04,BUY,100,60
2026-10-28 10:20:00,NIFTY,CE,24500,2026-11-04,SELL,150,70
2026-10-28 10:40:00,NIFTY,CE,24500,2026-11-04,SELL,50,40
2026-10-28 11:00:00,NIFTY,CE,24500,2026-11-04,SELL,75,200
2026-10-28 11:20:00,NIFTY,CE,24500,2026-11-04,BUY,75,150
2026-10-28 12:00:00,NIFTY,CE,24500,2026-11-04,BUY,75,100
"""


def test_csv_to_trips_matches_fixtures_f2_f3_f5():
    fills = map_to_canonical(pd.read_csv(io.StringIO(CSV)))
    tagged = tag_multileg(fills)
    paired = pair_trips(tagged.fills)
    trips = flag_trips(paired.trips, tagged.fills)

    assert trips["pnl"].tolist() == [pytest.approx(1500), pytest.approx(3750)]  # F2, F3
    assert not trips["possible_multi_leg"].any()
    assert len(paired.open_positions) == 1  # F5: trailing BUY has no closer
    assert any("open/unmatched" in w for w in paired.warnings)
