"""FIFO pairing of fills into flat-to-flat round trips (SPEC section 5)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

INSTRUMENT_KEY = ("underlying", "expiry", "strike", "option_type")

TRIP_COLUMNS = (
    "trip_id", "underlying", "expiry", "strike", "option_type", "direction",
    "entry_ts", "exit_ts", "entry_price", "exit_price", "qty", "size",
    "fees", "pnl", "hold_minutes", "fill_ids",
)
OPEN_COLUMNS = (
    "underlying", "expiry", "strike", "option_type", "direction", "qty", "avg_price",
)
MAX_WARNING_DETAILS = 5


@dataclass(frozen=True)
class PairingResult:
    trips: pd.DataFrame
    open_positions: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Lot:
    qty: int
    price: float


@dataclass
class _Trip:
    direction: str
    entry_ts: pd.Timestamp
    open_qty: int = 0
    open_notional: float = 0.0
    close_qty: int = 0
    close_notional: float = 0.0
    gross_pnl: float = 0.0
    fees: float = 0.0
    exit_ts: pd.Timestamp | None = None
    fill_ids: list[int] = field(default_factory=list)

    def add_fill_id(self, fill_id: int) -> None:
        if fill_id not in self.fill_ids:
            self.fill_ids.append(fill_id)


def _pair_instrument(rows) -> tuple[list[_Trip], _Trip | None, deque[_Lot]]:
    """Walk one instrument's fills in time order. Returns closed trips and any open remainder."""
    lots: deque[_Lot] = deque()
    trips: list[_Trip] = []
    current: _Trip | None = None
    for row in rows:
        direction = "long" if row.side == "BUY" else "short"
        fee_per_unit = (getattr(row, "fees", 0.0) or 0.0) / row.qty
        remaining = row.qty
        while remaining > 0:
            if current is None or current.direction == direction:
                if current is None:
                    current = _Trip(direction=direction, entry_ts=row.ts)
                lots.append(_Lot(remaining, row.price))
                current.open_qty += remaining
                current.open_notional += remaining * row.price
                current.fees += fee_per_unit * remaining
                current.add_fill_id(row.fill_id)
                remaining = 0
                continue
            lot = lots[0]
            matched = min(remaining, lot.qty)
            sign = 1 if current.direction == "long" else -1
            current.gross_pnl += sign * (row.price - lot.price) * matched
            current.close_qty += matched
            current.close_notional += matched * row.price
            current.fees += fee_per_unit * matched
            current.exit_ts = row.ts
            current.add_fill_id(row.fill_id)
            lot.qty -= matched
            remaining -= matched
            if lot.qty == 0:
                lots.popleft()
            if not lots:
                trips.append(current)
                current = None
    return trips, current, lots


def _trip_record(key: tuple, trip: _Trip) -> dict:
    underlying, expiry, strike, option_type = key
    entry_price = trip.open_notional / trip.open_qty
    return {
        "underlying": underlying, "expiry": expiry, "strike": strike,
        "option_type": option_type, "direction": trip.direction,
        "entry_ts": trip.entry_ts, "exit_ts": trip.exit_ts,
        "entry_price": entry_price,
        "exit_price": trip.close_notional / trip.close_qty,
        "qty": trip.open_qty, "size": trip.open_qty * entry_price,
        "fees": trip.fees, "pnl": trip.gross_pnl - trip.fees,
        "hold_minutes": (trip.exit_ts - trip.entry_ts).total_seconds() / 60.0,
        "fill_ids": tuple(trip.fill_ids),
    }


def _open_record(key: tuple, trip: _Trip, lots: deque[_Lot]) -> dict:
    underlying, expiry, strike, option_type = key
    qty = sum(lot.qty for lot in lots)
    avg_price = sum(lot.qty * lot.price for lot in lots) / qty
    return {
        "underlying": underlying, "expiry": expiry, "strike": strike,
        "option_type": option_type, "direction": trip.direction,
        "qty": qty, "avg_price": avg_price,
    }


def _open_warning(opens: pd.DataFrame) -> list[str]:
    if opens.empty:
        return []
    head = (
        f"{len(opens)} open/unmatched position(s) (may be a position opened before this period), "
        "not counted as trips"
    )
    details = [
        f"{r.underlying} {r.strike:g} {r.option_type} exp {r.expiry} "
        f"({r.direction}, {r.qty} @ {r.avg_price:.2f})"
        for r in opens.head(MAX_WARNING_DETAILS).itertuples()
    ]
    more = len(opens) - MAX_WARNING_DETAILS
    suffix = f"; and {more} more" if more > 0 else ""
    return [f"{head}: {'; '.join(details)}{suffix}."]


def pair_trips(fills: pd.DataFrame) -> PairingResult:
    """Pair canonical fills into flat-to-flat trips, FIFO per instrument.

    A sell-first fill opens a short. Positions still open at the end of the
    file (including closing fills whose opener is not in the file, which look
    like opposite-direction opens) are returned in ``open_positions`` and
    warned about; they are not trips.
    """
    ordered = fills.sort_values(["ts", "fill_id"], kind="stable")
    trip_rows: list[dict] = []
    open_rows: list[dict] = []
    for key, group in ordered.groupby(list(INSTRUMENT_KEY), sort=False):
        trips, current, lots = _pair_instrument(group.itertuples(index=False))
        trip_rows.extend(_trip_record(key, t) for t in trips)
        if current is not None and lots:
            open_rows.append(_open_record(key, current, lots))

    trips_df = pd.DataFrame(trip_rows, columns=[c for c in TRIP_COLUMNS if c != "trip_id"])
    trips_df = trips_df.sort_values("entry_ts", kind="stable").reset_index(drop=True)
    trips_df.insert(0, "trip_id", range(len(trips_df)))
    opens_df = pd.DataFrame(open_rows, columns=list(OPEN_COLUMNS))
    return PairingResult(trips=trips_df, open_positions=opens_df, warnings=_open_warning(opens_df))
