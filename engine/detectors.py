"""Habit detectors D1-D5 (SPEC section 7). Deterministic; every threshold lives in CONFIG.

Detectors take the trips frame from pairing (optionally with the
``possible_multi_leg`` column from multileg) and ignore multi-leg trips.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CONFIG: dict[str, float | int] = {
    "W": 15,              # D1: minutes after a losing exit
    "R": 1.0,             # D1: min size ratio vs the prior (losing) trip
    "P": 30.0,            # D2: max entry premium, INR (price proxy)
    "OTM_PCT": 0.01,      # D2: min moneyness when spot is available
    "K": 2.0,             # D3: size multiple of the median
    "N": 20,              # D3: look-back trips
    "MIN_PRIOR": 10,      # D3: below this many prior trips use whole-period median
    "H": 2.0,             # D5: hold multiple of winners' median hold
    "MIN_WINNERS": 3,     # D5: winners needed to define a median hold
    "FEE_RATIO": 0.2,     # D4: fees / gross pnl turnover at or above this is a habit
    "MIN_FLAGGED": 3,     # review: a habit needs at least this many flagged trips
}

REVENGE = "revenge_reentry"
EXPIRY_CHEAP = "expiry_day_cheap_premium"
OVERSIZING = "oversizing"
LOSER_HOLDING = "loser_holding"
FEE_DRAG = "fee_drag"

EVIDENCE_COLUMNS = ("trip_id", "entry_ts", "instrument", "size", "pnl")


@dataclass(frozen=True)
class DetectorResult:
    name: str
    status: str                         # "ok" or "skipped" (reason in notes)
    flagged_trip_ids: tuple[int, ...]
    n_flagged: int
    n_total: int                        # trips the detector looked at (multi-leg excluded)
    observed_pnl: float
    baseline_pnl_per_trip: float | None  # mean pnl of unflagged trips
    flagged_avg_pnl: float | None        # mean pnl of flagged trips
    evidence: pd.DataFrame
    method: str
    notes: tuple[str, ...] = ()


def _config(overrides: dict | None) -> dict:
    return {**CONFIG, **(overrides or {})}


def eligible_trips(trips: pd.DataFrame) -> pd.DataFrame:
    if "possible_multi_leg" in trips.columns:
        trips = trips[~trips["possible_multi_leg"].astype(bool)]
    return trips.sort_values(["entry_ts", "trip_id"], kind="stable").reset_index(drop=True)


def _evidence(rows: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    out["instrument"] = [
        f"{r.underlying} {r.strike:g} {r.option_type} exp {r.expiry}" for r in out.itertuples()
    ]
    return out[list(EVIDENCE_COLUMNS)].reset_index(drop=True)


def _result(name: str, trips: pd.DataFrame, mask, method: str, notes=(),
            status: str = "ok", observed_pnl: float | None = None) -> DetectorResult:
    mask = pd.Series(np.asarray(mask, dtype=bool), index=trips.index)
    flagged, rest = trips[mask], trips[~mask]
    return DetectorResult(
        name=name, status=status,
        flagged_trip_ids=tuple(int(i) for i in flagged["trip_id"]),
        n_flagged=int(mask.sum()), n_total=len(trips),
        observed_pnl=float(flagged["pnl"].sum()) if observed_pnl is None else float(observed_pnl),
        baseline_pnl_per_trip=float(rest["pnl"].mean()) if len(rest) else None,
        flagged_avg_pnl=float(flagged["pnl"].mean()) if len(flagged) else None,
        evidence=_evidence(flagged), method=method, notes=tuple(notes),
    )


def _skipped(name: str, trips: pd.DataFrame, method: str, note: str) -> DetectorResult:
    return _result(name, trips, np.zeros(len(trips), dtype=bool), method, (note,), "skipped")


def detect_revenge_reentry(trips: pd.DataFrame, config: dict | None = None) -> DetectorResult:
    """D1: entered within W min of the latest losing exit on the same underlying, at >= R x its size."""
    cfg = _config(config)
    t = eligible_trips(trips)
    mask = np.zeros(len(t), dtype=bool)
    window = cfg["W"] * 60.0
    for _, grp in t.groupby("underlying"):
        losers = grp[grp["pnl"] < 0].sort_values("exit_ts", kind="stable")
        if losers.empty:
            continue
        exits = losers["exit_ts"].map(pd.Timestamp.timestamp).to_numpy()
        sizes = losers["size"].to_numpy()
        for idx, entry in grp["entry_ts"].map(pd.Timestamp.timestamp).items():
            pos = np.searchsorted(exits, entry, side="right") - 1
            while pos >= 0 and losers.index[pos] == idx:  # a zero-length trip is not its own prior
                pos -= 1
            if pos < 0 or entry - exits[pos] > window:
                continue
            if t.at[idx, "size"] >= cfg["R"] * sizes[pos]:
                mask[idx] = True
    return _result(REVENGE, t, mask, "time_gap_and_size")


def _is_otm(row, min_pct: float) -> bool:
    if row.option_type == "CE":
        return (row.strike - row.entry_spot) / row.entry_spot >= min_pct
    return (row.entry_spot - row.strike) / row.entry_spot >= min_pct


def detect_expiry_cheap_premium(trips: pd.DataFrame, config: dict | None = None) -> DetectorResult:
    """D2 (PROXY): long entry on expiry day with a cheap premium, or >= 1% OTM if spot is known."""
    cfg = _config(config)
    t = eligible_trips(trips)
    on_expiry = np.array([
        r.direction == "long" and r.entry_ts.date() == r.expiry for r in t.itertuples()
    ], dtype=bool)
    candidates = t[on_expiry]
    has_spot = candidates["entry_spot"].notna() & (candidates["entry_spot"] > 0)
    notes: list[str] = []
    if len(candidates) and has_spot.all():
        method = "spot_moneyness"
        hit = [_is_otm(r, cfg["OTM_PCT"]) for r in candidates.itertuples()]
    else:
        method = "price_proxy"
        hit = (candidates["entry_price"] <= cfg["P"]).tolist()
        if has_spot.any():
            notes.append("Spot was missing for some expiry-day entries; the price proxy was used for all.")
    mask = np.zeros(len(t), dtype=bool)
    if len(candidates):
        mask[np.flatnonzero(on_expiry)[np.asarray(hit, dtype=bool)]] = True
    return _result(EXPIRY_CHEAP, t, mask, method, notes)


def detect_oversizing(trips: pd.DataFrame, config: dict | None = None) -> DetectorResult:
    """D3: size above K x the median size of the previous N trips (whole period if < MIN_PRIOR priors)."""
    cfg = _config(config)
    t = eligible_trips(trips)
    sizes = t["size"].to_numpy()
    whole_median = float(np.median(sizes)) if len(sizes) else 0.0
    mask = np.zeros(len(t), dtype=bool)
    n_fallback = 0
    for i in range(len(t)):
        prior = sizes[max(0, i - int(cfg["N"])):i]
        if i < cfg["MIN_PRIOR"]:
            reference = whole_median
            n_fallback += 1
        else:
            reference = float(np.median(prior))
        mask[i] = sizes[i] > cfg["K"] * reference
    notes = []
    if n_fallback:
        notes.append(
            f"{n_fallback} trip(s) had fewer than {int(cfg['MIN_PRIOR'])} prior trips; "
            "the whole-period median size was used for them."
        )
    return _result(OVERSIZING, t, mask, "median_size", notes)


def detect_loser_holding(trips: pd.DataFrame, config: dict | None = None) -> DetectorResult:
    """D5: losing trips held longer than H x the median hold of winning trips."""
    cfg = _config(config)
    t = eligible_trips(trips)
    winners = t[t["pnl"] > 0]
    if len(winners) < cfg["MIN_WINNERS"]:
        return _skipped(
            LOSER_HOLDING, t, "hold_time",
            f"Needs at least {int(cfg['MIN_WINNERS'])} winning trips; found {len(winners)}.",
        )
    limit = cfg["H"] * float(winners["hold_minutes"].median())
    mask = (t["pnl"] < 0) & (t["hold_minutes"] > limit)
    return _result(LOSER_HOLDING, t, mask, "hold_time")


def detect_fee_drag(trips: pd.DataFrame, config: dict | None = None) -> DetectorResult:
    """D4: total fees as a share of gross pnl turnover. The cost is exact (fees paid), not an estimate."""
    cfg = _config(config)
    t = eligible_trips(trips)
    total_fees = float(t["fees"].sum())
    turnover = float((t["pnl"] + t["fees"]).abs().sum())
    ratio = total_fees / turnover if turnover > 0 else float("inf") if total_fees > 0 else 0.0
    note = f"Fees were {ratio:.0%} of gross profit-and-loss turnover."
    if ratio < cfg["FEE_RATIO"]:
        return _result(FEE_DRAG, t, np.zeros(len(t), dtype=bool), "fees_ratio", (note,))
    return _result(FEE_DRAG, t, (t["fees"] > 0).to_numpy(), "fees_ratio", (note,),
                   observed_pnl=-total_fees)


def run_detectors(trips: pd.DataFrame, config: dict | None = None,
                  has_fees: bool = False) -> dict[str, DetectorResult]:
    """All detectors keyed by name. D4 runs only when the file had a fees column."""
    results = {
        REVENGE: detect_revenge_reentry(trips, config),
        EXPIRY_CHEAP: detect_expiry_cheap_premium(trips, config),
        OVERSIZING: detect_oversizing(trips, config),
        LOSER_HOLDING: detect_loser_holding(trips, config),
    }
    if has_fees:
        results[FEE_DRAG] = detect_fee_drag(trips, config)
    return results
