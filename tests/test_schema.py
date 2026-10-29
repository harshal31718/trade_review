import io

import pandas as pd
import pytest

from engine.schema import IST, REQUIRED_COLUMNS, SchemaError, validate_trades
from tests.conftest import fill, fills_df


# F10: empty / invalid input -------------------------------------------------
def test_empty_dataframe_raises_clear_error():
    with pytest.raises(SchemaError, match="empty"):
        validate_trades(pd.DataFrame())


def test_header_only_file_raises_clear_error():
    raw = pd.read_csv(io.StringIO(",".join(REQUIRED_COLUMNS) + "\n"))
    with pytest.raises(SchemaError, match="empty"):
        validate_trades(raw)


def test_zero_byte_csv_raises_clear_error():
    with pytest.raises(pd.errors.EmptyDataError):
        pd.read_csv(io.StringIO(""))
    # the app reads the CSV; a frame with no columns must give our message
    with pytest.raises(SchemaError, match="empty"):
        validate_trades(pd.DataFrame(columns=[]))


@pytest.mark.parametrize("column", REQUIRED_COLUMNS)
def test_missing_required_column_names_the_column(column):
    raw = pd.DataFrame([fill("10:00", "BUY", 75, 100)]).drop(columns=[column])
    with pytest.raises(SchemaError, match=column):
        validate_trades(raw)


def test_unparseable_value_names_column_and_row():
    raw = pd.DataFrame([fill("10:00", "BUY", 75, 100), fill("10:05", "SELL", 75, "abc")])
    with pytest.raises(SchemaError, match=r"'price'.*2"):
        validate_trades(raw)


def test_bad_side_rejected():
    raw = pd.DataFrame([fill("10:00", "HOLD", 75, 100)])
    with pytest.raises(SchemaError, match="side"):
        validate_trades(raw)


def test_non_positive_or_fractional_qty_rejected():
    for bad in (0, -75, 7.5):
        with pytest.raises(SchemaError, match="qty"):
            validate_trades(pd.DataFrame([fill("10:00", "BUY", bad, 100)]))


# Happy path / normalisation -------------------------------------------------
def test_valid_frame_is_typed_sorted_and_ist():
    df = fills_df(fill("10:30", "SELL", 150, 120), fill("10:00", "BUY", 150, 100))
    assert list(df["side"]) == ["BUY", "SELL"]
    assert str(df["ts"].dt.tz) == str(IST)
    assert df["ts"].dt.hour.tolist() == [10, 10]
    assert df["qty"].dtype.kind == "i"
    assert df["fill_id"].tolist() == [0, 1]


def test_tz_aware_input_is_converted_to_ist():
    raw = pd.DataFrame([fill("04:30", "BUY", 75, 100)])
    raw["ts"] = "2026-10-28 04:30:00+00:00"
    df = validate_trades(raw)
    assert df["ts"].iloc[0].hour == 10 and df["ts"].iloc[0].minute == 0


def test_column_names_and_case_are_normalised():
    raw = pd.DataFrame([fill("10:00", "buy", 75, 100, option_type="ce")])
    raw.columns = [c.upper() for c in raw.columns]
    df = validate_trades(raw)
    assert df["side"].iloc[0] == "BUY" and df["option_type"].iloc[0] == "CE"


def test_non_option_rows_dropped_and_counted():
    raw = pd.DataFrame([fill("10:00", "BUY", 75, 100), fill("10:01", "BUY", 50, 100, option_type="FUT")])
    df = validate_trades(raw)
    assert len(df) == 1
    assert any("1 non-option" in w for w in df.attrs["warnings"])


def test_all_non_option_rows_is_an_error():
    raw = pd.DataFrame([fill("10:00", "BUY", 50, 100, option_type="FUT")])
    with pytest.raises(SchemaError, match="No option"):
        validate_trades(raw)


def test_missing_fees_warns_gross_pnl():
    df = fills_df(fill("10:00", "BUY", 75, 100))
    assert "fees" not in df.columns
    assert any("gross" in w for w in df.attrs["warnings"])


def test_fees_present_no_gross_warning():
    df = fills_df(fill("10:00", "BUY", 75, 100, fees=20))
    assert df["fees"].iloc[0] == 20.0
    assert not any("gross" in w for w in df.attrs["warnings"])


def test_zero_price_allowed_for_expired_worthless():
    df = fills_df(fill("14:00", "SELL", 75, 0))
    assert df["price"].iloc[0] == 0.0
