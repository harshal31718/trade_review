"""Descriptive trade statistics (SPEC section 14). Pure pandas/Python, no Streamlit.

Set = completed trips excluding ``possible_multi_leg`` trips, ordered by exit time.
A metric that cannot be computed (no losers, no trips) is ``None``.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TradeStats:
    trades: int
    n_multi_leg_excluded: int
    win_rate: float
    net_pnl: float
    avg_win: float
    avg_loss: float | None               # mean |pnl| of losers; None when no losers
    largest_win: float
    largest_loss: float                  # shown as a positive loss figure
    expectancy: float
    payoff_ratio: float | None
    payoff_ratio_after_charges: float | None   # only when the file has fees
    profit_factor: float | None
    breakeven_win_rate: float | None
    max_drawdown: float
    longest_losing_streak: int
    longest_winning_streak: int
    avg_trade_size: float


def _longest_run(flags: list[bool]) -> int:
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def _max_drawdown(pnls: pd.Series) -> float:
    equity = pnls.cumsum()
    peak = pd.concat([pd.Series([0.0]), equity], ignore_index=True).cummax().iloc[1:].reset_index(drop=True)
    return float((peak - equity.reset_index(drop=True)).max())


def _payoff(pnls: pd.Series) -> float | None:
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    if losses.empty:
        return None
    return float(wins.mean() / losses.abs().mean()) if len(wins) else 0.0


def compute_stats(trips: pd.DataFrame, *, has_fees: bool = False) -> TradeStats | None:
    """Statistics for ``trips`` (needs pnl, exit_ts, size, possible_multi_leg); None when there are no trips."""
    multi = trips["possible_multi_leg"] if "possible_multi_leg" in trips else pd.Series(False, index=trips.index)
    used = trips[~multi].sort_values("exit_ts", kind="stable")
    if used.empty:
        return None
    pnl = used["pnl"].astype(float).reset_index(drop=True)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.abs().mean()) if len(losses) else None
    gross_pnl = pnl + used["fees"].astype(float).reset_index(drop=True) if has_fees and "fees" in used else pnl
    payoff = _payoff(gross_pnl)
    payoff_net = _payoff(pnl) if has_fees else None
    breakeven = None if payoff is None else 1.0 / (1.0 + payoff)
    profit_factor = None if losses.empty else float(wins.sum() / losses.abs().sum())
    return TradeStats(
        trades=len(pnl), n_multi_leg_excluded=int(multi.sum()), win_rate=len(wins) / len(pnl),
        net_pnl=float(pnl.sum()), avg_win=avg_win, avg_loss=avg_loss,
        largest_win=float(pnl.max()), largest_loss=float(abs(pnl.min())),
        expectancy=float(pnl.mean()), payoff_ratio=payoff, payoff_ratio_after_charges=payoff_net,
        profit_factor=profit_factor, breakeven_win_rate=breakeven, max_drawdown=_max_drawdown(pnl),
        longest_losing_streak=_longest_run([p < 0 for p in pnl]),
        longest_winning_streak=_longest_run([p > 0 for p in pnl]),
        avg_trade_size=float(used["size"].astype(float).mean()),
    )
