"""Ranking and the output object (SPEC sections 7-8).

``analyse(fills)`` runs the whole engine: multi-leg tagging, FIFO pairing,
detectors, then reports the costliest habits (at most 3, each with a rupee figure).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from engine.detectors import (
    CONFIG, EXPIRY_CHEAP, FEE_DRAG, LOSER_HOLDING, DetectorResult, run_detectors,
)
from engine.multileg import flag_trips, tag_multileg
from engine.nudges import DESCRIPTIONS, render_nudge
from engine.pairing import pair_trips

MAX_HABITS = 3
MAX_EVIDENCE_ROWS = 5
NO_HABIT_MESSAGE = "No costly habit found this period."
# Habits whose rupee figure is exact (fees) or observed-only (no price path), so no "if avoided" estimate.
NO_ESTIMATE = frozenset({FEE_DRAG, LOSER_HOLDING})


@dataclass(frozen=True)
class Habit:
    name: str
    description: str
    n_flagged: int
    n_total: int
    observed_pnl: float                  # INR, negative = money lost
    estimate_pnl: float | None           # "if avoided (estimate)", INR; None when not applicable
    flagged_avg_pnl: float | None
    unflagged_avg_pnl: float | None
    evidence: pd.DataFrame               # up to 5 worst flagged trips
    method: str
    notes: tuple[str, ...]
    nudge: str = ""


@dataclass(frozen=True)
class Review:
    period_start: object | None
    period_end: object | None
    n_trips: int
    net_pnl: float
    pnl_label: str                       # "gross, before charges" or "net of charges"
    win_rate: float | None
    habits: tuple[Habit, ...]
    no_habit_message: str | None
    warnings: tuple[str, ...]
    config: dict = field(default_factory=dict)

    @property
    def has_habits(self) -> bool:
        return bool(self.habits)


def is_reportable(result: DetectorResult, config: dict) -> bool:
    return (
        result.status == "ok"
        and result.n_flagged >= config["MIN_FLAGGED"]
        and result.observed_pnl < 0
    )


def rank_results(results: dict[str, DetectorResult], config: dict) -> list[DetectorResult]:
    """Reportable detectors by |observed_pnl| descending (name breaks ties), at most MAX_HABITS."""
    qualifying = [r for r in results.values() if is_reportable(r, config)]
    qualifying.sort(key=lambda r: (-abs(r.observed_pnl), r.name))
    return qualifying[:MAX_HABITS]


def _habit(result: DetectorResult, config: dict) -> Habit:
    worst = result.evidence.sort_values("pnl", kind="stable").head(MAX_EVIDENCE_ROWS)
    estimate = None if result.name in NO_ESTIMATE else abs(result.observed_pnl)
    return Habit(
        name=result.name, description=DESCRIPTIONS[result.name],
        n_flagged=result.n_flagged, n_total=result.n_total,
        observed_pnl=result.observed_pnl, estimate_pnl=estimate,
        flagged_avg_pnl=result.flagged_avg_pnl, unflagged_avg_pnl=result.baseline_pnl_per_trip,
        evidence=worst.reset_index(drop=True), method=result.method, notes=result.notes,
        nudge=render_nudge(result, config, estimate),
    )


def _method_warning(results: dict[str, DetectorResult], config: dict) -> list[str]:
    d2 = results[EXPIRY_CHEAP]
    if d2.method == "spot_moneyness":
        return [f"Expiry-day check used moneyness (>= {config['OTM_PCT']:.0%} out of the money), a proxy for cheap lottery-style premium."]
    return [f"Expiry-day check used a price proxy (entry premium <= INR {config['P']:g}), not moneyness. This is a proxy."]


def _notes_and_skips(results: dict[str, DetectorResult], reported: set[str]) -> list[str]:
    out = []
    for r in results.values():
        if r.status == "skipped":
            out.extend(f"{r.name}: skipped. {n}" for n in r.notes)
        elif r.name in reported or r.name == "oversizing":
            out.extend(n for n in r.notes if "whole-period" in n)
    return out


def build_review(trips: pd.DataFrame, results: dict[str, DetectorResult], *,
                 has_fees: bool, warnings: list[str] | None = None,
                 config: dict | None = None) -> Review:
    cfg = {**CONFIG, **(config or {})}
    top = rank_results(results, cfg)
    habits = tuple(_habit(r, cfg) for r in top)
    all_warnings = list(warnings or [])
    all_warnings += _method_warning(results, cfg)
    all_warnings += _notes_and_skips(results, {r.name for r in top})
    n = len(trips)
    if n == 0:
        all_warnings.append("No completed round trips were found, so there is nothing to review.")
    return Review(
        period_start=trips["entry_ts"].min().date() if n else None,
        period_end=trips["exit_ts"].max().date() if n else None,
        n_trips=n, net_pnl=float(trips["pnl"].sum()) if n else 0.0,
        pnl_label="net of charges" if has_fees else "gross, before charges",
        win_rate=float((trips["pnl"] > 0).mean()) if n else None,
        habits=habits, no_habit_message=None if habits else NO_HABIT_MESSAGE,
        warnings=tuple(dict.fromkeys(all_warnings)), config=cfg,
    )


def analyse(fills: pd.DataFrame, config: dict | None = None) -> Review:
    """Full pipeline from validated canonical fills to a Review."""
    has_fees = "fees" in fills.columns
    tagged = tag_multileg(fills)
    paired = pair_trips(tagged.fills)
    trips = flag_trips(paired.trips, tagged.fills)
    warnings = list(fills.attrs.get("warnings", [])) + tagged.warnings + paired.warnings
    n_excluded = int(trips["possible_multi_leg"].sum()) if len(trips) else 0
    if n_excluded:
        warnings.append(f"{n_excluded} trip(s) excluded from habit detection as possible multi-leg.")
    results = run_detectors(trips, config, has_fees=has_fees)
    return build_review(trips, results, has_fees=has_fees, warnings=warnings, config=config)
