import pytest

from engine.loader import MAX_ROWS, load_fills, load_path
from engine.schema import SchemaError

HEADER = "ts,underlying,option_type,strike,expiry,side,qty,price\n"
ROW = "2026-10-28 10:00:00,NIFTY,CE,24500,2026-11-04,BUY,75,100\n"


def test_valid_csv_loads():
    assert len(load_fills((HEADER + ROW).encode())) == 1


def test_zero_bytes_and_whitespace_give_empty_message():
    for blob in (b"", b"  \n"):
        with pytest.raises(SchemaError, match="empty"):
            load_fills(blob)


def test_header_only_gives_empty_message():
    with pytest.raises(SchemaError, match="empty"):
        load_fills(HEADER.encode())


def test_missing_column_named():
    with pytest.raises(SchemaError, match="price"):
        load_fills(b"ts,underlying,option_type,strike,expiry,side,qty\n" + ROW.encode())


def test_size_cap():
    with pytest.raises(SchemaError, match="limit"):
        load_fills((HEADER + ROW).encode(), max_bytes=10)


def test_row_cap():
    with pytest.raises(SchemaError, match="rows"):
        load_fills((HEADER + ROW * (MAX_ROWS + 1)).encode(), max_bytes=10**9)


def test_binary_garbage_is_a_clean_error():
    with pytest.raises(SchemaError):
        load_fills(b"\xff\xfe\x00\x01\x02garbage\x80\x81")


def test_bundled_sample_loads():
    from pathlib import Path
    sample = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "sample_trades.csv"
    assert len(load_path(sample)) > 50
