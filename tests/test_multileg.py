"""Multi-leg tagging tests (SPEC section 6). F9 expected values from docs/FIXTURES.md."""
from engine.multileg import flag_trips, tag_multileg
from engine.pairing import pair_trips
from tests.conftest import fill, fills_df


def test_f9_two_strikes_opposite_sides_within_60s_are_tagged():
    fills = fills_df(
        fill("10:00:05", "BUY", 75, 100, strike=24500),
        fill("10:00:20", "SELL", 75, 40, strike=24800),
    )
    result = tag_multileg(fills)
    assert result.fills["possible_multi_leg"].tolist() == [True, True]
    assert result.n_groups == 1
    assert len([w for w in result.warnings if "multi-leg" in w]) == 1
    assert "1 possible multi-leg group" in result.warnings[0]


def test_gap_over_60s_is_not_tagged():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100, strike=24500),
        fill("10:01:01", "SELL", 75, 40, strike=24800),
    )
    result = tag_multileg(fills)
    assert not result.fills["possible_multi_leg"].any()
    assert result.n_groups == 0 and result.warnings == []


def test_exactly_60s_gap_is_tagged():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100, strike=24500),
        fill("10:01:00", "SELL", 75, 40, strike=24800),
    )
    assert tag_multileg(fills).n_groups == 1


def test_mixed_option_types_are_tagged_straddle():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100, option_type="CE"),
        fill("10:00:10", "BUY", 75, 90, option_type="PE"),
    )
    assert tag_multileg(fills).n_groups == 1


def test_same_strike_same_type_exit_and_reentry_is_not_multi_leg():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100),
        fill("10:00:30", "SELL", 75, 101),
    )
    assert tag_multileg(fills).n_groups == 0


def test_same_side_different_strikes_same_type_is_not_multi_leg():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100, strike=24500),
        fill("10:00:10", "BUY", 75, 60, strike=24800),
    )
    assert tag_multileg(fills).n_groups == 0


def test_different_expiry_or_underlying_is_not_multi_leg():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100, strike=24500),
        fill("10:00:10", "SELL", 75, 40, strike=24800, expiry="2026-11-11"),
        fill("10:00:15", "SELL", 75, 40, strike=24800, underlying="BANKNIFTY"),
    )
    assert tag_multileg(fills).n_groups == 0


def test_chained_legs_form_one_group_and_separate_clusters_count_separately():
    fills = fills_df(
        fill("10:00:00", "BUY", 75, 100, strike=24500),
        fill("10:00:30", "SELL", 75, 60, strike=24700),
        fill("10:01:20", "BUY", 75, 30, strike=24900),
        fill("12:00:00", "BUY", 75, 100, strike=24500),
        fill("12:00:10", "SELL", 75, 60, strike=24700),
    )
    result = tag_multileg(fills)
    assert result.n_groups == 2
    assert result.fills["possible_multi_leg"].all()


def test_trip_containing_a_tagged_fill_is_flagged_and_others_are_not():
    fills = fills_df(
        fill("10:00:05", "BUY", 75, 100, strike=24500),
        fill("10:00:20", "SELL", 75, 40, strike=24800),
        fill("10:30:00", "SELL", 75, 120, strike=24500),
        fill("10:31:00", "BUY", 75, 30, strike=24800),
        fill("13:00:00", "BUY", 75, 50, strike=24000),
        fill("13:30:00", "SELL", 75, 60, strike=24000),
    )
    tagged = tag_multileg(fills)
    trips = flag_trips(pair_trips(tagged.fills).trips, tagged.fills)
    by_strike = trips.set_index("strike")["possible_multi_leg"]
    assert by_strike[24500] and by_strike[24800]
    assert not by_strike[24000]


def test_tagging_does_not_mutate_input():
    fills = fills_df(
        fill("10:00:05", "BUY", 75, 100, strike=24500),
        fill("10:00:20", "SELL", 75, 40, strike=24800),
    )
    tag_multileg(fills)
    assert "possible_multi_leg" not in fills.columns
