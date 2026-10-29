"""Canonical trade schema and validation (SPEC section 4).

Input: one row per executed fill. Output: a clean DataFrame with typed columns,
sorted by time, plus human-readable warnings for anything dropped.
"""
from __future__ import annotations

from datetime import timedelta, timezone

import pandas as pd

IST = timezone(timedelta(hours=5, minutes=30))

REQUIRED_COLUMNS = (
    "ts", "underlying", "option_type", "strike", "expiry", "side", "qty", "price",
)
OPTIONAL_COLUMNS = ("fees", "spot")
OPTION_TYPES = ("CE", "PE")
SIDES = ("BUY", "SELL")


class SchemaError(ValueError):
    """Raised when an input file cannot be used. The message is user-facing."""


def _require_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {', '.join(REQUIRED_COLUMNS)}."
        )


def _fail_if_bad(column: str, bad: pd.Series) -> None:
    if bad.any():
        rows = ", ".join(str(i + 1) for i in bad[bad].index[:5])
        more = "" if bad.sum() <= 5 else f" (and {bad.sum() - 5} more)"
        raise SchemaError(
            f"Column '{column}' has {int(bad.sum())} missing or unparseable value(s); "
            f"first bad data row(s): {rows}{more}."
        )


def _parse_ts(raw: pd.Series) -> pd.Series:
    try:
        parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
    except (ValueError, TypeError):
        parsed = pd.to_datetime(raw, errors="coerce")
    _fail_if_bad("ts", parsed.isna())
    if parsed.dt.tz is None:
        return parsed.dt.tz_localize(IST)
    return parsed.dt.tz_convert(IST)


def _parse_number(df: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(df[column], errors="coerce")
    _fail_if_bad(column, values.isna())
    return values.astype(float)


def validate_trades(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise a canonical-schema frame.

    Raises SchemaError for an empty frame, missing required columns, or
    unparseable required values. Rows that are not CE/PE options are dropped
    and counted in the returned frame's ``attrs["warnings"]``.
    """
    if raw is None or len(raw.columns) == 0 or len(raw) == 0:
        raise SchemaError("The file is empty: no trade rows were found.")
    raw = raw.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    _require_columns(raw)

    warnings: list[str] = []
    raw = raw.reset_index(drop=True)
    option_type = raw["option_type"].astype("string").str.strip().str.upper()
    is_option = option_type.isin(OPTION_TYPES)
    n_dropped = int((~is_option).sum())
    if n_dropped:
        warnings.append(
            f"{n_dropped} non-option row(s) were dropped (only CE/PE options are analysed)."
        )
    raw = raw[is_option].copy()
    raw["option_type"] = option_type[is_option]
    if raw.empty:
        raise SchemaError("No option (CE/PE) rows were found in the file.")
    raw = raw.reset_index(drop=True)

    out = pd.DataFrame(index=raw.index)
    out["ts"] = _parse_ts(raw["ts"])
    underlying = raw["underlying"].astype("string").str.strip().str.upper()
    _fail_if_bad("underlying", underlying.isna() | (underlying == ""))
    out["underlying"] = underlying.astype(object)
    out["option_type"] = raw["option_type"].astype(object)
    out["strike"] = _parse_number(raw, "strike")

    expiry = pd.to_datetime(raw["expiry"], errors="coerce")
    _fail_if_bad("expiry", expiry.isna())
    out["expiry"] = expiry.dt.date

    side = raw["side"].astype("string").str.strip().str.upper()
    _fail_if_bad("side", ~side.isin(SIDES))
    out["side"] = side.astype(object)

    qty = _parse_number(raw, "qty")
    _fail_if_bad("qty", (qty <= 0) | (qty != qty.round()))
    out["qty"] = qty.astype(int)

    price = _parse_number(raw, "price")
    _fail_if_bad("price", price < 0)
    out["price"] = price

    if "fees" in raw.columns:
        out["fees"] = pd.to_numeric(raw["fees"], errors="coerce").fillna(0.0).astype(float)
    else:
        warnings.append("No fees column: pnl is gross, before charges.")
    if "spot" in raw.columns:
        out["spot"] = pd.to_numeric(raw["spot"], errors="coerce").astype(float)

    out = out.sort_values("ts", kind="stable").reset_index(drop=True)
    out.insert(0, "fill_id", range(len(out)))
    out.attrs["warnings"] = warnings
    return out
